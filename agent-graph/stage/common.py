"""共通ユーティリティ: スクリプト（グローバル）と状態（リポジトリ直下 .agents/）のパス分離、イベント追記、排他ロック"""

from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

# スクリプト本体の場所（~/.local/share/agent-graph）。dotfiles から symlink される
TOOL_DIR = Path(__file__).resolve().parent.parent
EXAMPLE_TASKS_PATH = TOOL_DIR / "tasks.example.yaml"

# 状態を置くリポジトリを明示する環境変数（worktree 内の子セッションが親リポジトリを指すために使う）
PROJECT_ENV = "AGENT_GRAPH_PROJECT"


def find_git_root(start: Path) -> Path | None:
    proc = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    return Path(proc.stdout.strip()) if proc.returncode == 0 else None


def resolve_project_dir() -> Path:
    # 優先順: 明示指定 → Claude Code が渡す cwd → 現在地の git ルート → 現在地
    explicit = os.environ.get(PROJECT_ENV)
    if explicit:
        return Path(explicit).resolve()
    claude_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if claude_dir:
        return find_git_root(Path(claude_dir)) or Path(claude_dir).resolve()
    return find_git_root(Path.cwd()) or Path.cwd().resolve()


PROJECT_DIR = resolve_project_dir()
AGENTS_DIR = PROJECT_DIR / ".agents"
STATE_DIR = AGENTS_DIR / "state"
TASKS_DIR = AGENTS_DIR / "tasks"
OUT_DIR = AGENTS_DIR / "out"
GRAPH_DIR = AGENTS_DIR / "graph"
WORKTREES_DIR = AGENTS_DIR / "worktrees"
EVENTS_PATH = STATE_DIR / "events.jsonl"
SESSIONS_PATH = STATE_DIR / "sessions.json"
CURRENT_SESSION_PATH = STATE_DIR / "current_session"
COUNTER_PATH = STATE_DIR / "counter"

# リポジトリの .gitignore を汚さず、ローカルだけで除外する
EXCLUDE_LINES = [".agents/"]


def ensure_dirs() -> None:
    for directory in (STATE_DIR, TASKS_DIR, OUT_DIR, GRAPH_DIR, WORKTREES_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    ensure_git_exclude()


def resolve_git_dir(project: Path) -> Path | None:
    # worktree の .git は「gitdir: <path>」1 行のファイル。subprocess を使わず読み取りだけで解決する
    git_path = project / ".git"
    if git_path.is_dir():
        return git_path
    if not git_path.is_file():
        return None
    gitdir = git_path.read_text(encoding="utf-8").strip().removeprefix("gitdir:").strip()
    path = Path(gitdir)
    # <repo>/.git/worktrees/<名前> の 2 つ上が共通の git ディレクトリ
    return path.parent.parent if path.parent.name == "worktrees" else path


def ensure_git_exclude() -> None:
    git_dir = resolve_git_dir(PROJECT_DIR)
    if git_dir is None or not git_dir.is_dir():
        return
    exclude = git_dir / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    existing = (
        exclude.read_text(encoding="utf-8").splitlines() if exclude.exists() else []
    )
    missing = [line for line in EXCLUDE_LINES if line not in existing]
    if missing:
        with exclude.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(missing) + "\n")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


EVENTS_LOCK_PATH = STATE_DIR / "events.lock"


@contextmanager
def locked_events() -> Iterator[None]:
    # 複数セッションが同じ events.jsonl を追記するための排他。locked_state と同じ flock 方式
    EVENTS_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with EVENTS_LOCK_PATH.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield
        fcntl.flock(lock, fcntl.LOCK_UN)


# hook は uv 経由で起動されるので、直接の親は uv になる。所有者の claude まで遡る上限
OWNER_WALK_MAX = 6
# npm 版の Claude Code を動かす実行ファイル。argv に claude の本体が入る
JS_RUNTIMES = {"node", "bun", "deno"}


def run_ps(fields: str, pid: int) -> str:
    # ps の表記をロケールで揺らさない。起動時刻を比較の鍵に使うため C に固定する
    proc = subprocess.run(
        ["ps", "-o", fields, "-p", str(pid)],
        env={**os.environ, "LC_ALL": "C"},
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() if proc.returncode == 0 else ""


def process_start_time(pid: int) -> str:
    # プロセスの起動時刻。PID 再利用を弾く鍵にする。取れなければ空文字
    return run_ps("lstart=", pid)


def is_claude(command: str) -> bool:
    # 実行ファイルが claude か、npm 版のように node が claude の本体を引数に取るか
    tokens = command.split()
    if not tokens:
        return False
    if Path(tokens[0]).name == "claude":
        return True
    return Path(tokens[0]).name in JS_RUNTIMES and any(
        claude_arg(token) for token in tokens[1:]
    )


def claude_arg(token: str) -> bool:
    # node が受け取る本体。実行ファイル名か npm パッケージのディレクトリ名で見分ける
    path = Path(token)
    return path.name == "claude" or "claude-code" in path.parts


def owner_pid() -> int:
    # セッションの所有者である claude の PID。祖先に claude が無ければ 0
    pid = os.getppid()
    for _ in range(OWNER_WALK_MAX):
        line = run_ps("ppid=,command=", pid)
        parent, _, command = line.partition(" ")
        if not command.strip():
            break
        if is_claude(command):
            return pid
        pid = int(parent)
    print(
        "[agent-graph] 祖先に claude が見つからず pid を記録しない。生死判定は旧方式に落ちる",
        file=sys.stderr,
    )
    return 0


def append_event(event: dict) -> None:
    # 1 イベント = 1 行の JSON。履歴とダッシュボードの時系列に使う
    ensure_dirs()
    record = {"ts": now_iso(), **event}
    # 生死問い合わせの鍵。ダッシュボードはこの PID にプロセスの実在を尋ねる
    pid = owner_pid()
    if pid:
        record["pid"] = pid
        record["pid_start"] = process_start_time(pid)
    with locked_events(), EVENTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_events() -> list[dict]:
    if not EVENTS_PATH.exists():
        return []
    lines = EVENTS_PATH.read_text(encoding="utf-8").splitlines()
    # 書き込み途中の末尾行（閉じ括弧なし）は読み飛ばす
    return [json.loads(line) for line in lines if line.strip().endswith("}")]


def load_json(path: Path, default: dict | list) -> dict | list:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_atomic(path: Path, text: str) -> None:
    # 同じディレクトリの一時ファイルに書いてから差し替える。読み手が途中の内容を見ない
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name, suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as tmp:
            tmp.write(text)
        os.replace(tmp_name, path)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def save_json(path: Path, data: dict | list) -> None:
    write_atomic(path, json.dumps(data, ensure_ascii=False, indent=2))


@contextmanager
def locked_file(path: Path) -> Iterator[None]:
    # 状態ファイルごとの排他。<ファイル名>.lock を flock で押さえる
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


@contextmanager
def locked_json(path: Path, default: dict | list) -> Iterator[dict | list]:
    # 読み・更新・書き戻しを 1 つのロックで包む。sessions.json のような共有状態に使う
    with locked_file(path):
        data = load_json(path, default)
        yield data
        save_json(path, data)


def next_counter(path: Path) -> int:
    # 採番は flock で直列化し、書き込みは原子的に行う
    with locked_file(path):
        value = int(path.read_text().strip()) + 1 if path.exists() else 1
        write_atomic(path, str(value))
    return value


def resolve_session(explicit: str | None) -> str:
    if explicit:
        return explicit
    return (
        CURRENT_SESSION_PATH.read_text().strip()
        if CURRENT_SESSION_PATH.exists()
        else "manual"
    )


def graph_dir(session: str) -> Path:
    return GRAPH_DIR / session


def tasks_path(session: str) -> Path:
    return graph_dir(session) / "tasks.yaml"


def graph_state_path(session: str) -> Path:
    return STATE_DIR / "graph" / f"{session}.json"


def list_graph_sessions() -> list[str]:
    if not GRAPH_DIR.exists():
        return []
    return sorted(p.parent.name for p in GRAPH_DIR.glob("*/tasks.yaml"))


@contextmanager
def locked_state(session: str) -> Iterator[dict]:
    # スケジューラのスレッドと CLI（approve 等）が同じ状態ファイルを安全に更新するための排他
    path = graph_state_path(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    with locked_json(path, {}) as state:
        yield state


def run_cmd(
    args: list[str],
    cwd: Path | None = None,
    timeout_sec: int | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    # 失敗しても例外にせず、呼び出し側が returncode を見て判断する
    return subprocess.run(
        args,
        cwd=cwd,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )


def tail(text: str, limit: int = 4000) -> str:
    return text if len(text) <= limit else "…(先頭省略)…\n" + text[-limit:]
