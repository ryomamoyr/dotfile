"""tasks.yaml・実行状態・イベントを 1 つの有向グラフに組み立て、自動更新ダッシュボードに配信する HTTP サーバ"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import secrets
import shlex
import shutil
import subprocess
import sys
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from common import (
    PROJECT_DIR,
    STATE_DIR,
    TOOL_DIR,
    graph_state_path,
    list_graph_sessions,
    load_json,
    locked_state,
    now_iso,
    read_events,
    run_cmd,
    tasks_path,
)
from graph_model import ACTIVE_STATES, EXECUTORS, WAITING_STATES, load_spec, task_state
from herdr_runner import marker_pattern

try:
    from common import process_start_time
except ImportError:
    # 旧 common.py にはまだ無い。人が stage を配るまでのつなぎとして同じ実装を持つ
    def process_start_time(pid: int) -> str:
        # 比較の鍵にするので表記をロケールで揺らさない
        proc = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            env={**os.environ, "LC_ALL": "C"},
            capture_output=True,
            text=True,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""


HTML_PATH = Path(__file__).resolve().parent / "graph.html"
# 追跡が途切れたジョブの pane を読むときの行数
PANE_READ_LINES = "50"
# ブラウザからの操作。task は tasks.yaml のタスク、codex は単発ジョブ
TASK_ACTIONS = {"approve", "retry", "reject"}
CODEX_ACTIONS = {"rerun"}
DISCOVERY_TTL_SEC = 15
WORKER_TIMEOUT_SEC = 30
# herdr の呼び出しはすべてこの秒数で打ち切る
HERDR_TIMEOUT_SEC = 5
# 同じプロセス内で pane 一覧を使い回す秒数
HERDR_CACHE_TTL_SEC = 2.0
DISCOVERY_SKIP = {".git", ".agents", ".venv", "node_modules", "Library", ".Trash"}
# 記録が途絶えたセッションを終了扱いにするまでの分数。環境変数で上書き可
STALE_SESSION_MIN_DEFAULT = 30
STALE_SESSION_ENV = "AGENT_GRAPH_STALE_MIN"
# transcript の更新が止まった claude サブエージェントを失踪とみなすまでの分数
AGENT_IDLE_MIN_DEFAULT = 10
AGENT_IDLE_ENV = "AGENT_GRAPH_AGENT_IDLE_MIN"
# Claude Code が会話とサブエージェントの transcript を置く場所
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
# transcript の置き場の名前を作るとき - に置き換える文字
SLUG_CHARS = re.compile(r"[^a-zA-Z0-9]")
# プロジェクトごとのスナップショットを使い回す秒数
SNAPSHOT_TTL_DEFAULT = 2.0
SNAPSHOT_TTL_ENV = "AGENT_GRAPH_SNAPSHOT_TTL"
# 前方一致でターンをまとめてよい時刻差
TURN_MERGE_SEC = 60
# ブラウザからの POST に必要な認証
TOKEN_PATH = STATE_DIR / "agd.token"
TOKEN_HEADER = "X-Agent-Graph-Token"
TOKEN_PLACEHOLDER = "__AGENT_GRAPH_TOKEN__"
# 送信本文から除く制御文字。タブと改行だけ残す
CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def parse_ts(value: str) -> datetime | None:
    # 壊れた時刻は判定に使わない
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S%z")
    except (ValueError, TypeError):
        return None


def parse_json(text: str, default: dict | list) -> dict | list:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return default


def read_json(path: Path, default: dict | list) -> dict | list:
    # 壊れた状態ファイルで表示全体を落とさない
    try:
        return load_json(path, default)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return default


def env_number(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, ValueError, TypeError):
        return default


def parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()
    return meta


def load_agent_models(project_dir: Path) -> dict[str, str]:
    # ユーザー層（~/.claude/agents）とリポジトリ層（.claude/agents）の両方から name → model を拾う
    models: dict[str, str] = {}
    for base in (
        Path.home() / ".claude" / "agents",
        project_dir / ".claude" / "agents",
    ):
        if not base.exists():
            continue
        for path in base.rglob("*.md"):
            meta = parse_frontmatter(path.read_text(encoding="utf-8"))
            if "name" in meta:
                models[meta["name"]] = meta.get("model", "")
    return models


def new_session(name: str) -> dict:
    root = {
        "id": "root",
        "kind": "root",
        "label": name,
        "model": "",
        "status": "running",
        "started": "",
        "ended": "",
        "task": "",
        "description": "",
    }
    return {"name": name, "goal": "", "nodes": {"root": root}, "edges": []}


def first_line(text: str) -> str:
    stripped = text.strip()
    return stripped.splitlines()[0] if stripped else ""


def add_edge(session: dict, parent: str, child: str, label: str) -> None:
    session["edges"].append({"source": parent, "target": child, "label": label})


def attach_parent(session: dict, event: dict) -> str:
    # 子セッションからの委譲はタスクノードの下に、それ以外は親エージェントか root の下に付ける
    task_id = event.get("task_id", "")
    if task_id and task_id in session["nodes"]:
        return task_id
    return event.get("parent", "root")


def mergeable_turn(last: dict, prompt: str, ts: str) -> bool:
    # 空の指示はまとめない。前方一致でも時刻が離れていれば別のターン
    if not prompt or not last.get("prompt"):
        return False
    if not (prompt.startswith(last["prompt"]) or last["prompt"].startswith(prompt)):
        return False
    started, now = parse_ts(last.get("ts", "")), parse_ts(ts)
    if started is None or now is None:
        return False
    return abs((now - started).total_seconds()) <= TURN_MERGE_SEC


def apply_events(
    events: list[dict], sessions: dict[str, dict], agent_models: dict[str, str]
) -> None:
    pending: dict[tuple[str, str], deque[dict]] = defaultdict(deque)
    for event in events:
        name = event.get("session", "unknown")
        session = sessions.setdefault(name, new_session(name))
        session["last_event_ts"] = event["ts"]
        # 生死問い合わせの鍵。最新の非空を残す。旧形式のイベントには無い
        if event.get("pid"):
            session["pid"] = event["pid"]
            session["pid_start"] = event.get("pid_start", "")
        nodes = session["nodes"]
        kind = event.get("event")

        if kind == "session_start":
            root = nodes["root"]
            root["model"] = event.get("model", "")
            root["status"] = "running"
            root["ended"] = ""
            root["started"] = root["started"] or event["ts"]
            # 生死判定用の根 pane。derive_liveness が pane list との突合に使う。最新の非空を残す
            if event.get("herdr_pane"):
                session["herdr_pane"] = event["herdr_pane"]
        elif kind == "session_end":
            nodes["root"]["status"] = "ended"
            nodes["root"]["ended"] = event["ts"]
        elif kind in {"turn_start", "turn_done"}:
            # ターンが終わってもセッションは生きている。次の入力待ち = idle
            nodes["root"]["status"] = "idle" if kind == "turn_done" else "running"
            nodes["root"]["ended"] = event["ts"] if kind == "turn_done" else ""
            if event.get("prompt"):
                nodes["root"]["task"] = event["prompt"]
            # 指示 → やったこと の履歴。turn_start で行を作り、turn_done で要約を埋める
            turns = session.setdefault("turns", [])
            prompt = event.get("prompt", "").strip()
            if kind == "turn_start":
                # サブエージェントの通知や返信は人の指示ではないので履歴に載せない
                if prompt.startswith("<"):
                    continue
                # 直前の指示の続きを 60 秒以内に送ったものだけ 1 行にまとめる。長い方を残す
                last = turns[-1] if turns else None
                if last and not last["done"] and mergeable_turn(last, prompt, event["ts"]):
                    last["prompt"] = max(last["prompt"], prompt, key=len)
                else:
                    for t in turns:
                        t["done"] = t["done"] or event["ts"]
                    turns.append({"ts": event["ts"], "prompt": prompt, "done": "", "summary": []})
            elif turns:
                # 要約は done が空の最新のターンに付ける。全部済んでいれば何も上書きしない
                target = next((t for t in reversed(turns) if not t["done"]), None)
                for t in turns:
                    t["done"] = t["done"] or event["ts"]
                if target is not None:
                    if event.get("summary"):
                        target["summary"] = event["summary"]
                    if event.get("reply"):
                        target["reply"] = event["reply"]
        elif kind == "task_dispatch":
            pending[(name, event.get("agent_type", ""))].append(event)
        elif kind == "agent_start":
            existing = nodes.get(event.get("agent_id", ""))
            if existing is not None:
                # 自分の子の完了待ちで止まっていた agent の再開。description と辺はそのまま
                existing["status"] = "running"
                existing["ended"] = ""
                continue
            agent_type = event.get("agent_type", "")
            queue = pending[(name, agent_type)]
            dispatch = queue.popleft() if queue else {}
            # 委譲記録も種別も無いものは Claude Code 内部のバックグラウンドエージェント。描かない
            if not dispatch and not agent_type:
                continue
            node_id = event.get("agent_id", "")
            nodes[node_id] = {
                "id": node_id,
                "kind": "claude",
                "label": agent_type,
                "model": dispatch.get("model") or agent_models.get(agent_type, ""),
                "status": "running",
                "started": event["ts"],
                "ended": "",
                "task": dispatch.get("prompt", ""),
                "description": dispatch.get("description", ""),
            }
            add_edge(
                session,
                attach_parent(
                    session, {**dispatch, "task_id": event.get("task_id", "")}
                ),
                node_id,
                dispatch.get("description") or first_line(dispatch.get("prompt", "")),
            )
        elif kind == "agent_stop":
            node = nodes.get(event.get("agent_id", ""))
            if node is None:
                continue
            node["status"] = "done"
            node["ended"] = event["ts"]
            if event.get("task"):
                node["task"] = event["task"]
            if event.get("result"):
                node["result"] = event["result"]
            if event.get("summary"):
                node["summary"] = event["summary"]
            # 子から親へ戻る辺。親は、この子を target にした既存の辺の source から引く
            parent = next(
                (e["source"] for e in session["edges"] if e["target"] == node["id"]),
                None,
            )
            already = any(
                e.get("back") and e["source"] == node["id"] and e["target"] == parent
                for e in session["edges"]
            )
            if parent and not already:
                summary = node.get("summary") or []
                label = summary[0] if summary else first_line(node.get("result", ""))
                session["edges"].append(
                    {"source": node["id"], "target": parent, "label": label, "back": True}
                )
        elif kind == "codex_start":
            node_id = event["node_id"]
            nodes[node_id] = {
                "id": node_id,
                "kind": "codex",
                "label": node_id,
                "model": event.get("model", ""),
                "status": "running",
                "started": event["ts"],
                "ended": "",
                "task": event.get("task", ""),
                "description": event.get("description", ""),
                "pane": event.get("pane", ""),
                "out": event.get("out", ""),
                "accept": event.get("accept", []),
            }
            add_edge(
                session,
                event.get("parent", "root"),
                node_id,
                event.get("description") or first_line(event.get("task", "")),
            )
        elif kind == "codex_done":
            node = nodes.get(event["node_id"])
            if node is None:
                continue
            node["status"] = event.get("status", "done")
            node["ended"] = event["ts"]
            node["exit_code"] = event.get("exit_code")
            node["verify"] = event.get("verify", {})
        elif kind == "denied":
            session.setdefault("denied", []).append(
                {
                    "ts": event["ts"],
                    "tool": event.get("tool", ""),
                    "reason": event.get("reason", ""),
                    "detail": event.get("command") or event.get("path", ""),
                }
            )


def apply_task_graph(name: str, session: dict) -> None:
    # tasks.yaml と状態ファイルからタスク DAG を作る。依存の無いタスクは root に繋ぐ
    spec = load_spec(name)
    state = read_json(graph_state_path(name), {})
    session["goal"] = spec["goal"]
    session["meta"] = state.get("_meta", {})
    nodes = session["nodes"]
    for task in spec["tasks"]:
        current = state.get(task["id"], {})
        executor = current.get("executor") or task["executor"]
        nodes[task["id"]] = {
            "id": task["id"],
            "kind": "task",
            "label": task["title"],
            "executor": executor,
            "model": current.get("model") or task["model"] or EXECUTORS.get(executor, {}).get("model", ""),
            "status": current.get("state", "planned"),
            "attempts": current.get("attempts", 0),
            "started": current.get("started", ""),
            "ended": current.get("ended", ""),
            "task": task["prompt"],
            "description": task["title"],
            "accept": task["accept"],
            "scope": task["scope"],
            "outputs": task["outputs"],
            "depends_on": task["depends_on"],
            "review": current.get("review", {}),
            "verify": current.get("verify", {}),
            "violations": current.get("violations", []),
            "feedback": current.get("feedback", ""),
            "branch": current.get("branch", ""),
            "worktree": current.get("worktree", ""),
            "pane": current.get("pane", ""),
            "output": current.get("output", ""),
            "pr_url": current.get("pr_url", ""),
            "retry": task["retry"],
        }
    for task in spec["tasks"]:
        if not task["depends_on"]:
            add_edge(session, "root", task["id"], task["title"])
        for dep in task["depends_on"]:
            handed = [
                p
                for p in spec["by_id"].get(dep, {}).get("outputs", [])
                if p in task["inputs"]
            ] or spec["by_id"].get(dep, {}).get("outputs", [])
            add_edge(
                session,
                dep,
                task["id"],
                ", ".join(handed[:3]) + ("…" if len(handed) > 3 else ""),
            )


_panes_cache: tuple[float, list[dict] | None] = (0.0, None)
_panes_lock = threading.Lock()


def run_herdr(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    # herdr は応答しないことがある。必ず打ち切り、失敗は None にする
    if not shutil.which("herdr"):
        return None
    try:
        return run_cmd(["herdr", *args], timeout_sec=HERDR_TIMEOUT_SEC)
    except (subprocess.TimeoutExpired, OSError):
        return None


def herdr_panes() -> list[dict] | None:
    # pane 一覧。herdr が無い・失敗・壊れた出力はすべて判定不能の None
    global _panes_cache
    with _panes_lock:
        ts, cached = _panes_cache
        if cached is not None and time.monotonic() - ts < HERDR_CACHE_TTL_SEC:
            return cached
    proc = run_herdr(["pane", "list"])
    if proc is None or proc.returncode != 0 or not proc.stdout.strip():
        return None
    data = parse_json(proc.stdout, {})
    result = data.get("result", {}) if isinstance(data, dict) else {}
    panes = result.get("panes", []) if isinstance(result, dict) else []
    if not isinstance(panes, list):
        return None
    with _panes_lock:
        _panes_cache = (time.monotonic(), panes)
    return panes


def list_live_panes() -> set[str] | None:
    panes = herdr_panes()
    return None if panes is None else {p.get("pane_id", "") for p in panes}


def read_marker_exit(
    node_id: str, handle: str, live_panes: set[str] | None
) -> int | None:
    # 完了マーカー AGENT_GRAPH_DONE:<id>:<code> を探す。ローカル実行はログ、herdr は pane 画面
    if handle.endswith(".log"):
        log = Path(handle)
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        match = marker_pattern(node_id).search(text)
        return int(match.group(1)) if match else None
    if live_panes is None or handle not in live_panes:
        return None
    proc = run_herdr(
        ["pane", "read", handle, "--source", "recent", "--lines", PANE_READ_LINES]
    )
    if proc is None:
        return None
    match = marker_pattern(node_id).search(proc.stdout)
    return int(match.group(1)) if match else None


def reconcile_codex_nodes(session: dict, live_panes: set[str] | None) -> None:
    # codex_done が記録されずに待ち受けが途切れたジョブを、ログ / pane / 出力ファイルから読み取りだけで確定する
    # derive_liveness が pane 消失で lost に降格した codex も、ここでマーカーがあれば done/failed に精緻化する
    # codex_done で確定した done/failed は事実なので触らない
    for node in session["nodes"].values():
        if node.get("kind") != "codex" or node["status"] in ("done", "failed"):
            continue
        job = read_json(STATE_DIR / "jobs" / session["name"] / f"{node['id']}.json", {})
        handle = job.get("pane") or node.get("pane", "")
        exit_code = read_marker_exit(node["id"], handle, live_panes)
        out_exists = Path(node.get("out", "")).exists() if node.get("out") else False
        if exit_code is not None:
            node["status"] = "done" if exit_code == 0 and out_exists else "failed"
            node["exit_code"] = exit_code
            node["reconciled"] = (
                "待ち受けが途切れたためマーカーから補正（受け入れ条件は未検証）"
            )
        elif (
            live_panes is not None
            and handle
            and not handle.endswith(".log")
            and handle not in live_panes
        ):
            node["status"] = "lost"
            node["reconciled"] = "pane が閉じられ、完了マーカーを読めなかった" + (
                "（出力ファイルはある）" if out_exists else "（出力ファイルもない）"
            )


def stale_threshold_sec() -> float:
    return env_number(STALE_SESSION_ENV, STALE_SESSION_MIN_DEFAULT) * 60


def agent_idle_threshold_sec() -> float:
    return env_number(AGENT_IDLE_ENV, AGENT_IDLE_MIN_DEFAULT) * 60


def pane_ids(panes: list[dict] | None) -> set[str] | None:
    # pane_id の集合。取得不能は None、空一覧は空集合
    if panes is None:
        return None
    return {p.get("pane_id", "") for p in panes} - {""}


def pane_labels(panes: list[dict]) -> set[str]:
    # pane の表示名。scheduler pane は "<session>/scheduler" で作られる
    return {p.get("label", "") for p in panes} - {""}


def live_names_from(panes: list[dict], project: Path) -> set[str]:
    # pane の agent_session.value を session_id とみなし、sessions.json でセッション名に突き合わせる
    ids = {(p.get("agent_session") or {}).get("value", "") for p in panes} - {""}
    if not ids:
        return set()
    mapping = read_json(project / ".agents" / "state" / "sessions.json", {})
    if not isinstance(mapping, dict):
        return set()
    return {name for sid, name in mapping.items() if sid in ids}


def scheduler_pane_alive(name: str, labels: set[str]) -> bool:
    return f"{name}/scheduler" in labels


def demote_root_if_stale(session: dict) -> None:
    # 生死を問えない root は、最後のイベントからの経過時間で終了を判定する
    root = session["nodes"]["root"]
    stamp = parse_ts(session.get("last_event_ts", ""))
    if stamp is None:
        return
    if (datetime.now().astimezone() - stamp).total_seconds() > stale_threshold_sec():
        root["status"] = "ended"
        root["ended"] = session.get("last_event_ts", "")


def process_alive(pid: int, pid_start: str) -> bool:
    # プロセスの実在を問い合わせる。起動時刻まで一致して初めて同じプロセスとみなす
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass  # 他ユーザーのプロセス。実在はするので起動時刻まで確かめる
    except (OSError, OverflowError, TypeError, ValueError):
        return False
    return not pid_start or process_start_time(pid) == pid_start


def session_alive(
    name: str, session: dict, live_names: set[str], live_ids: set[str] | None
) -> bool | None:
    # 一次情報は claude プロセスの実在。pid の無い旧形式は pane で問い、どちらも無ければ None
    pid = session.get("pid", 0)
    if pid:
        return process_alive(int(pid), session.get("pid_start", ""))
    if live_ids is None:
        return None
    if name in live_names:
        return True
    herdr_pane = session.get("herdr_pane", "")
    if herdr_pane:
        return herdr_pane in live_ids
    return None


def project_slug(project_dir: Path) -> str:
    # Claude Code は cwd の英数字以外をすべて - に置き換えた名前で transcript を置く
    return SLUG_CHARS.sub("-", str(project_dir.resolve()))


def subagent_dirs(name: str, project_dir: Path) -> list[Path] | None:
    # セッション名に対応する transcript の置き場。プロジェクトの記録ごと無ければ問い合わせ不能の None
    base = CLAUDE_PROJECTS_DIR / project_slug(project_dir)
    if not base.is_dir():
        return None
    mapping = read_json(project_dir / ".agents" / "state" / "sessions.json", {})
    if not isinstance(mapping, dict):
        return []
    return [base / sid / "subagents" for sid, value in mapping.items() if value == name]


def transcript_path(dirs: list[Path], agent_id: str) -> Path | None:
    for directory in dirs:
        path = directory / f"agent-{agent_id}.jsonl"
        if path.exists():
            return path
    return None


def agent_lost_reason(dirs: list[Path] | None, agent_id: str) -> str:
    # 生きている親の下の子は transcript の実体で問う。空文字は running を維持する
    if dirs is None:
        return ""
    path = transcript_path(dirs, agent_id)
    if path is None:
        return "transcript が無い。記録だけのノード"
    try:
        idle = time.time() - path.stat().st_mtime
    except OSError:
        return ""
    return "transcript の更新が止まっている" if idle > agent_idle_threshold_sec() else ""


def derive_agent_children(
    session: dict, alive: bool, name: str, project_dir: Path
) -> None:
    # claude 子は pane も PID も持たない。親の生死と transcript の実体から決める
    children = [
        node
        for node in session["nodes"].values()
        if node.get("kind") == "claude" and node["status"] in ("running", "idle")
    ]
    if not children:
        return
    dirs = subagent_dirs(name, project_dir) if alive else None
    for node in children:
        reason = "親セッションの終了で失われた" if not alive else agent_lost_reason(dirs, node["id"])
        if reason:
            node["status"] = "lost"
            node["reconciled"] = reason


def demote_missing_panes(session: dict, live_ids: set[str]) -> None:
    # herdr の pane を持つ running codex で、pane が一覧に無ければ lost。この後 reconcile がマーカーで精緻化する
    for node in session["nodes"].values():
        if node.get("kind") != "codex" or node["status"] != "running":
            continue
        pane = node.get("pane", "")
        if pane and not pane.endswith(".log") and pane not in live_ids:
            node["status"] = "lost"
            node["reconciled"] = "pane が pane list から消えた"


def derive_task_nodes(name: str, session: dict, labels: set[str]) -> None:
    # task の status は graph state を基準にする。ACTIVE のときだけ scheduler pane の在を確認する
    tasks = [n for n in session["nodes"].values() if n.get("kind") == "task"]
    if any((n.get("pane") or "").endswith(".log") for n in tasks):
        return  # ローカル実行のグラフは herdr pane 判定の対象外
    if scheduler_pane_alive(name, labels):
        return
    for node in tasks:
        if node["status"] in ACTIVE_STATES:
            node["status"] = "stalled"
            node["reconciled"] = "スケジューラの pane が無く、状態が更新されない"


def derive_liveness(
    sessions: dict[str, dict], panes: list[dict] | None, project_dir: Path
) -> None:
    # events が主張した status を生死の問い合わせで上書きする。死を running に優先する
    live_ids = pane_ids(panes)
    live_names = live_names_from(panes, project_dir) if panes is not None else set()
    labels = pane_labels(panes) if panes is not None else set()
    for name, session in sessions.items():
        session["live_pane"] = name in live_names
        root = session["nodes"]["root"]
        alive = (
            False
            if root["status"] == "ended"
            else session_alive(name, session, live_names, live_ids)
        )
        if alive is None:
            # 問い合わせられないセッションだけ、最後のイベントからの経過時間に落とす
            demote_root_if_stale(session)
            alive = root["status"] != "ended"
        elif not alive and root["status"] != "ended":
            root["status"] = "ended"
            root["ended"] = session.get("last_event_ts", "") or now_iso()
        derive_agent_children(session, alive, name, project_dir)
        if live_ids is not None:
            demote_missing_panes(session, live_ids)
            derive_task_nodes(name, session, labels)


def build_graph(project_dir: Path) -> dict:
    sessions: dict[str, dict] = {}
    for name in list_graph_sessions():
        if tasks_path(name).exists():
            apply_task_graph(name, sessions.setdefault(name, new_session(name)))
    apply_events(read_events(), sessions, load_agent_models(project_dir))
    # 冒頭で pane list を 1 回だけ取る。三値（list / None）を生死導出と codex 補正に渡す
    panes = herdr_panes()
    derive_liveness(sessions, panes, project_dir)
    live_ids = pane_ids(panes)
    for session in sessions.values():
        reconcile_codex_nodes(session, live_ids)
    visible = [
        s for s in sessions.values()
        if not (s["name"] == "unknown" and len(s["nodes"]) == 1)
    ]
    # 生きているセッションを先に、その中では新しい順
    ordered = sorted(
        visible,
        key=lambda s: (s["nodes"]["root"]["status"] == "ended", s["nodes"]["root"]["started"]),
        reverse=True,
    )
    ordered.sort(key=lambda s: s["nodes"]["root"]["status"] == "ended")
    return {"sessions": [serialize_session(s) for s in ordered]}


def serialize_session(session: dict) -> dict:
    root = session["nodes"]["root"]
    return {
        "name": session["name"],
        "goal": session.get("goal", ""),
        "live_pane": session.get("live_pane", False),
        "meta": session.get("meta", {}),
        "root": {
            "status": root["status"],
            "started": root["started"],
            "ended": root["ended"],
            "model": root["model"],
        },
        "nodes": list(session["nodes"].values()),
        "edges": session["edges"],
        "turns": session.get("turns", [])[-50:],
        "denied": session.get("denied", [])[-20:],
    }


# ---------- ブラウザからの操作 ----------


def decide_task(session: str, task_id: str, action: str) -> str:
    # 判断待ちは decision を置いてスケジューラに任せる。失敗済みは直接 planned / rejected に戻す（次の agr launch が拾う）
    with locked_state(session) as state:
        current = task_state(state, task_id)
        if current["state"] in WAITING_STATES:
            current["decision"] = action
            return f"{task_id}: {action} を記録した。スケジューラが反映する"
        if current["state"] == "failed" and action == "retry":
            # 昇格の結果と不合格理由は残す。試行回数だけ戻す。スケジューラの retry と同じ挙動
            current.update(
                state="planned",
                attempts=0,
                note="ダッシュボードから再試行",
                updated=now_iso(),
            )
            return f"{task_id}: planned に戻した。agr launch で再開する"
        if current["state"] == "failed" and action == "reject":
            current.update(
                state="rejected",
                ended=now_iso(),
                note="ダッシュボードで却下",
                updated=now_iso(),
            )
            return f"{task_id}: 却下した"
        return f"{task_id} は操作できる状態ではない（現在: {current['state']}）"


def rerun_codex(session: str, node_id: str) -> str:
    # agc rerun を切り離して起動する。待ち受けはその子プロセスが担い、codex_done を記録する
    log_dir = STATE_DIR / "logs" / session
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"rerun-{node_id}.log"
    script = TOOL_DIR / "bin" / "spawn_codex.py"
    command = f"cd {shlex.quote(str(PROJECT_DIR))} && uv run --project {shlex.quote(str(TOOL_DIR))} python {shlex.quote(str(script))} rerun {shlex.quote(node_id)} --session {shlex.quote(session)}"
    with log_path.open("w", encoding="utf-8") as log:
        subprocess.Popen(
            command,
            shell=True,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    return f"{node_id} を再実行した。新しいノードが現れる（ログ: {log_path}）"


def perform_action(payload: dict) -> str:
    session = str(payload.get("session", ""))
    node_id = str(payload.get("id", ""))
    action = str(payload.get("action", ""))
    if not session or not node_id:
        return "session と id が必要"
    if action in TASK_ACTIONS:
        return decide_task(session, node_id, action)
    if action in CODEX_ACTIONS:
        return rerun_codex(session, node_id)
    return f"未知の操作: {action}"


# .agents はリポジトリ直下にしか無い。root/<group>/<repo> までを見れば足りるので、
# データディレクトリ（数十万階層になり得る）へは降りない
DISCOVERY_MAX_DEPTH = 3


SAY_MAX_CHARS = 4000


def find_pane_for_session(project: Path, session_name: str) -> str:
    # herdr の pane 一覧には各 pane の Claude session_id が載る。sessions.json で名前に突き合わせる
    sessions = read_json(project / ".agents" / "state" / "sessions.json", {})
    ids = {sid for sid, name in sessions.items() if name == session_name}
    if not ids:
        return ""
    for pane in herdr_panes() or []:
        if (pane.get("agent_session") or {}).get("value") in ids:
            return pane.get("pane_id", "")
    return ""


def say_to_session(project: Path, session_name: str, text: str) -> str:
    text = CONTROL_CHARS.sub("", text).strip()
    if not text:
        return "本文が空です"
    if text.startswith("/"):
        return "先頭が / の本文は送れません。スラッシュコマンドとして実行されます"
    if len(text) > SAY_MAX_CHARS:
        return f"長すぎます（{SAY_MAX_CHARS} 字まで）"
    pane = find_pane_for_session(project, session_name)
    if not pane:
        return "送信先の pane が見つかりません（herdr 上で動いている claude のセッションだけ送れます）"
    # 改行は Enter として解釈されて途中で送信されるので、1 行にする
    one_line = " ".join(text.splitlines())
    sent = run_herdr(["pane", "send-text", pane, one_line])
    if sent is None:
        return "送信に失敗: herdr が応答しません"
    if sent.returncode != 0:
        return "送信に失敗: " + (sent.stderr or sent.stdout).strip()[:200]
    run_herdr(["pane", "send-keys", pane, "enter"])
    return f"{session_name} に送りました（pane {pane}）"


def discover_projects(roots: list[Path]) -> list[Path]:
    projects = set()
    for root in roots:
        root = root.resolve()
        for directory, names, _ in os.walk(root):
            depth = len(Path(directory).resolve().relative_to(root).parts)
            if ".agents" in names:
                projects.add(Path(directory).resolve())
                names[:] = []  # 見つけたプロジェクトの下は見ない
                continue
            if depth >= DISCOVERY_MAX_DEPTH:
                names[:] = []
                continue
            names[:] = [
                name
                for name in names
                if name not in DISCOVERY_SKIP and not name.startswith(".")
            ]
    return sorted(projects)


def worker_error(detail: str) -> dict:
    return {
        "sessions": [],
        "error": detail[:500],
        "message": "プロジェクトの読み込み・操作に失敗しました: " + detail[:200],
    }


def run_project_worker(project: Path, payload: dict | None = None) -> dict:
    # 1 プロジェクトの失敗は error に畳んで返す。全体の表示は落とさない
    command = [sys.executable, str(Path(__file__).resolve()), "--snapshot"]
    if payload is not None:
        command = command[:-1] + ["--action-json", json.dumps(payload)]
    try:
        proc = subprocess.run(
            command,
            env={**os.environ, "AGENT_GRAPH_PROJECT": str(project)},
            capture_output=True,
            text=True,
            timeout=WORKER_TIMEOUT_SEC,
        )
        if proc.returncode:
            return worker_error(proc.stderr.strip() or f"exit={proc.returncode}")
        data = json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        return worker_error(f"{WORKER_TIMEOUT_SEC} 秒で応答がありません")
    except json.JSONDecodeError as error:
        return worker_error(f"出力を読めません: {error}")
    except OSError as error:
        return worker_error(str(error))
    if not isinstance(data, dict) or "sessions" not in data:
        return data if isinstance(data, dict) else worker_error("想定外の出力")
    return data


class SnapshotCache:
    # プロジェクトごとに TTL で結果を持つ。同時に来た要求は 1 回の計算を共有する
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.entries: dict[Path, dict] = {}

    def get(self, project: Path) -> dict:
        with self.lock:
            entry = self.entries.setdefault(
                project, {"lock": threading.Lock(), "ts": 0.0, "value": None}
            )
        ttl = env_number(SNAPSHOT_TTL_ENV, SNAPSHOT_TTL_DEFAULT)
        with entry["lock"]:
            fresh = entry["value"] is not None and time.monotonic() - entry["ts"] < ttl
            if not fresh:
                entry["value"] = run_project_worker(project)
                entry["ts"] = time.monotonic()
            return entry["value"]

    def drop(self, project: Path) -> None:
        # 操作の直後は古い結果を返さない
        with self.lock:
            entry = self.entries.get(project)
        if entry:
            with entry["lock"]:
                entry["value"] = None


class ProjectCatalog:
    def __init__(self, roots: list[Path]) -> None:
        self.roots = roots
        self.projects: list[Path] = []
        self.updated = 0.0
        self.snapshots = SnapshotCache()

    def list_projects(self) -> list[Path]:
        if time.monotonic() - self.updated > DISCOVERY_TTL_SEC:
            self.projects = discover_projects(self.roots)
            self.updated = time.monotonic()
        return self.projects

    def build_dashboard(self) -> dict:
        projects = self.list_projects()
        with ThreadPoolExecutor(max_workers=8) as pool:
            snapshots = list(pool.map(self.snapshots.get, projects))
        sessions = []
        result = []
        for project, snapshot in zip(projects, snapshots):
            for session in snapshot["sessions"]:
                session.update(
                    project=str(project),
                    project_name=project.name,
                    key=f"{project}::{session['name']}",
                )
                sessions.append(session)
            result.append(
                {
                    "path": str(project),
                    "name": project.name,
                    "error": snapshot.get("error", ""),
                }
            )
        return {"projects": result, "sessions": sessions}

    def act(self, payload: dict) -> str:
        project = Path(str(payload.get("project", ""))).resolve()
        if project not in self.list_projects():
            return "表示対象のプロジェクトを指定してください"
        if any(
            not value
            or any(
                c
                not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                for c in value
            )
            for value in (str(payload.get("session", "")), str(payload.get("id", "")))
        ):
            return "セッションまたはエージェントの識別子が不正です"
        message = run_project_worker(project, payload).get("message", "")
        self.snapshots.drop(project)
        return message


class GraphHandler(BaseHTTPRequestHandler):
    project_dir: Path = Path(".")
    catalog: ProjectCatalog
    token: str = ""
    allowed_hosts: frozenset[str] = frozenset()

    def host_ok(self) -> bool:
        # DNS リバインディング対策。ループバック名以外の Host は受け付けない
        return self.headers.get("Host", "") in self.allowed_hosts

    def token_ok(self) -> bool:
        sent = self.headers.get(TOKEN_HEADER, "")
        return bool(self.token) and hmac.compare_digest(sent, self.token)

    def do_GET(self) -> None:
        if not self.host_ok():
            self.send_error(403)
            return
        path = urlparse(self.path).path
        if path == "/":
            html = HTML_PATH.read_text(encoding="utf-8").replace(
                TOKEN_PLACEHOLDER, self.token
            )
            self.send_bytes(html.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/graph":
            body = json.dumps(
                self.catalog.build_dashboard(), ensure_ascii=False
            ).encode("utf-8")
            self.send_bytes(body, "application/json; charset=utf-8")
        else:
            self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in ("/api/action", "/api/say"):
            self.send_error(404)
            return
        # Host・Origin・トークンの 3 つが揃わない要求は受け付けない
        origin = self.headers.get("Origin", "")
        if (
            not self.host_ok()
            or not self.headers.get("Content-Type", "").startswith("application/json")
            or (origin and origin != f"http://{self.headers.get('Host', '')}")
            or not self.token_ok()
        ):
            self.send_error(403)
            return
        try:
            length = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            length = 0
        payload = parse_json((self.rfile.read(length) or b"{}").decode("utf-8", "replace"), {})
        if not isinstance(payload, dict):
            self.send_error(400)
            return
        if path == "/api/say":
            # 送信先のプロジェクトは、探索で見つかっているものに限る
            project = Path(str(payload.get("project", ""))).resolve()
            if project not in set(self.catalog.list_projects()):
                message = "不明なプロジェクトです"
            else:
                message = say_to_session(project, str(payload.get("session", "")), str(payload.get("text", "")))
        else:
            message = self.catalog.act(payload)
        self.send_bytes(
            json.dumps({"message": message}, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def send_bytes(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="agent graph ダッシュボードを配信する")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--root", action="append", help="プロジェクトを探索する親ディレクトリ（複数可）"
    )
    parser.add_argument("--snapshot", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--action-json", help=argparse.SUPPRESS)
    return parser.parse_args()


def write_token() -> str:
    # 起動ごとに作り直す。読めるのは本人だけ
    token = secrets.token_urlsafe(32)
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(TOKEN_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(handle, "w", encoding="utf-8") as out:
        out.write(token + "\n")
    os.chmod(TOKEN_PATH, 0o600)
    return token


def allowed_hosts(host: str, port: int) -> frozenset[str]:
    names = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    if host not in {"0.0.0.0", "::", ""}:
        names.add(f"{host}:{port}")
    return frozenset(names)


def main() -> None:
    args = parse_args()
    if args.snapshot:
        print(json.dumps(build_graph(PROJECT_DIR), ensure_ascii=False))
        return
    if args.action_json:
        print(
            json.dumps(
                {"message": perform_action(json.loads(args.action_json))},
                ensure_ascii=False,
            )
        )
        return
    GraphHandler.project_dir = PROJECT_DIR
    roots = (
        [Path(root).expanduser().resolve() for root in args.root]
        if args.root
        else [Path.home() / "00_project", PROJECT_DIR]
    )
    GraphHandler.catalog = ProjectCatalog(roots)
    GraphHandler.token = write_token()
    GraphHandler.allowed_hosts = allowed_hosts(args.host, args.port)
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        print(
            f"警告: {args.host} で待ち受けます。ループバック以外の Host は 403 で拒否します",
            file=sys.stderr,
        )
    server = ThreadingHTTPServer((args.host, args.port), GraphHandler)
    print(
        f"agent graph [{PROJECT_DIR.name}]: http://{args.host}:{args.port}/  (Ctrl+C で停止)"
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
