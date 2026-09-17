"""実行基盤: herdr の tab（既定）か pane 分割でジョブを走らせる。docker sandbox とローカル実行にも切替可"""

from __future__ import annotations

import contextlib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from common import PROJECT_DIR, STATE_DIR, TASKS_DIR, TOOL_DIR

# pj() が claude 起動時に渡す。エージェントの配置元（split モード）に使う
HERDR_PANE_ENV = "HERDR_PANE_ID"
# "tab"（既定）: 仕事ごとに tab を作る / "split": 根 pane を分割する
PLACEMENT_ENV = "AGENT_GRAPH_PLACEMENT"
# "local" にすると herdr を使わずローカルの子プロセスで実行する（テスト・CI 用）
RUNNER_ENV = "AGENT_GRAPH_RUNNER"
# "docker" にすると各ジョブを agent-runner コンテナの中で実行する
SANDBOX_ENV = "AGENT_GRAPH_SANDBOX"
SANDBOX_IMAGE_ENV = "AGENT_GRAPH_IMAGE"
DEFAULT_IMAGE = "agent-runner:latest"
DONE_MARKER = "AGENT_GRAPH_DONE"
# SIGTERM の後に SIGKILL へ切り替えるまでの待ち時間
TERMINATE_GRACE_SEC = 5
LOG_DIR = STATE_DIR / "logs"


def write_job_script(session: str, node_id: str, body: str) -> Path:
    # 本体の後ろに完了マーカーを付ける。pane に送るのはこのスクリプトのパスだけ（クォート事故を防ぐ）
    path = TASKS_DIR / session / f"{node_id}.sh"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env bash\n" + body.rstrip("\n") + "\n" + f'echo "{DONE_MARKER}:{node_id}:$?"\n',
        encoding="utf-8",
    )
    return path


def marker_pattern(node_id: str) -> re.Pattern[str]:
    return re.compile(rf"{DONE_MARKER}:{re.escape(node_id)}:(\d+)")


def sandbox_command(script: Path) -> str:
    # ホストと同じ絶対パスでマウントするので、worktree の gitdir 参照や認証情報の場所がそのまま使える
    if os.environ.get(SANDBOX_ENV) != "docker":
        return f"bash {shlex.quote(str(script))}"
    home = Path.home()
    mounts = [PROJECT_DIR, TOOL_DIR, home / ".claude", home / ".codex", home / ".config" / "gh"]
    volume_args = " ".join(f"-v {shlex.quote(f'{p}:{p}')}" for p in mounts if p.exists())
    uid = os.getuid()
    gid = os.getgid()
    return (
        f"docker run --rm -it --user {uid}:{gid} -e HOME={shlex.quote(str(home))} "
        f"-e AGENT_GRAPH_PROJECT={shlex.quote(str(PROJECT_DIR))} "
        f"-v agent-graph-uv-cache:{shlex.quote(str(home / '.cache' / 'uv'))} {volume_args} "
        f"-w {shlex.quote(str(PROJECT_DIR))} {os.environ.get(SANDBOX_IMAGE_ENV, DEFAULT_IMAGE)} "
        f"bash {shlex.quote(str(script))}"
    )


def run_herdr(*args: str, check: bool = True) -> dict | list | str:
    # herdr CLI は {"result": {...}} 形式の JSON を返す
    proc = subprocess.run(["herdr", *args], capture_output=True, text=True, check=check)
    text = proc.stdout.strip()
    return json.loads(text) if text and text[0] in "{[" else text


def find_key(result: dict | list | str, key: str) -> str:
    # 入れ子のどこかにある key の値を返す（result.pane.pane_id / result.root_pane.pane_id など）
    if isinstance(result, dict):
        if key in result:
            return str(result[key])
        for value in result.values():
            found = find_key(value, key)
            if found:
                return found
    if isinstance(result, list):
        for value in result:
            found = find_key(value, key)
            if found:
                return found
    return ""


class HerdrRunner:
    """herdr に tab（または pane）を作って実行する。sidebar に working / blocked / done が出る"""

    def __init__(self, root_pane: str, placement: str, direction: str) -> None:
        self.root_pane = root_pane
        self.placement = placement
        self.direction = direction

    def start(self, session: str, node_id: str, label: str, script: Path, cwd: Path) -> str:
        if self.placement == "tab":
            result = run_herdr("tab", "create", "--cwd", str(cwd), "--label", label, "--no-focus")
        else:
            result = run_herdr("pane", "split", self.root_pane, "--direction", self.direction, "--cwd", str(cwd), "--no-focus")
        pane = find_key(result, "pane_id")
        if not pane:
            sys.exit(f"herdr の応答から pane_id を取れませんでした: {result!r}")
        if self.placement != "tab":
            run_herdr("pane", "rename", pane, label, check=False)
        run_herdr("pane", "run", pane, sandbox_command(script))
        return pane

    def wait(self, handle: str, node_id: str, timeout_sec: int) -> bool:
        proc = subprocess.run(
            ["herdr", "wait", "output", handle, "--match", f"{DONE_MARKER}:{node_id}:", "--timeout", str(timeout_sec * 1000)],
            capture_output=True,
            text=True,
        )
        return proc.returncode == 0

    def exit_code(self, handle: str, node_id: str) -> int:
        result = run_herdr("pane", "read", handle, "--source", "recent", "--lines", "20", check=False)
        text = result if isinstance(result, str) else json.dumps(result, ensure_ascii=False)
        match = marker_pattern(node_id).search(text)
        return int(match.group(1)) if match else -1

    def close(self, handle: str) -> None:
        run_herdr("pane", "close", handle, check=False)

    def terminate(self, handle: str) -> None:
        # pane を閉じれば中のプロセスも終わる。close と役割が重なるので何もしない
        return


class LocalRunner:
    """herdr なしで動かす。出力は <repo>/.agents/state/logs/<session>/<node>.log に落ちる"""

    def __init__(self) -> None:
        # timeout 時に殺すため、起動したプロセスを handle（ログのパス）で覚えておく
        self.procs: dict[str, subprocess.Popen] = {}
        self.lock = threading.Lock()

    def start(self, session: str, node_id: str, label: str, script: Path, cwd: Path) -> str:
        log_path = LOG_DIR / session / f"{node_id}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("w", encoding="utf-8") as log:
            proc = subprocess.Popen(
                sandbox_command(script).replace("-it ", ""),
                shell=True,
                cwd=cwd,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
            )
        with self.lock:
            self.procs[str(log_path)] = proc
        return str(log_path)

    def wait(self, handle: str, node_id: str, timeout_sec: int) -> bool:
        pattern = marker_pattern(node_id)
        deadline = time.monotonic() + timeout_sec
        log_path = Path(handle)
        while time.monotonic() < deadline:
            if log_path.exists() and pattern.search(log_path.read_text(encoding="utf-8", errors="replace")):
                return True
            time.sleep(1)
        return False

    def exit_code(self, handle: str, node_id: str) -> int:
        match = marker_pattern(node_id).search(Path(handle).read_text(encoding="utf-8", errors="replace"))
        return int(match.group(1)) if match else -1

    def close(self, handle: str) -> None:
        return

    def terminate(self, handle: str) -> None:
        # start_new_session=True で起こしたプロセスグループごと落とし、孫プロセスを残さない
        with self.lock:
            proc = self.procs.pop(handle, None)
        if proc is None or proc.poll() is not None:
            return
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            proc.terminate()
        try:
            proc.wait(timeout=TERMINATE_GRACE_SEC)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)


def create_runner(root_pane: str | None, direction: str) -> HerdrRunner | LocalRunner:
    if os.environ.get(RUNNER_ENV) == "local" or not shutil.which("herdr"):
        return LocalRunner()
    placement = os.environ.get(PLACEMENT_ENV, "tab")
    pane = root_pane or os.environ.get(HERDR_PANE_ENV, "")
    if placement != "tab" and not pane:
        sys.exit(
            f"split モードには分割元の pane id が必要です。--pane <id> か {HERDR_PANE_ENV} を渡してください"
            f"（pj() で claude を起こせば自動で入ります）。"
        )
    return HerdrRunner(pane, placement, direction)
