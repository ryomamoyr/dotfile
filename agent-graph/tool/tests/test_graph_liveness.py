"""ダッシュボードの生死導出: pane 実体からの降格・orphaned・scheduler pane・手動 start が復活しないこと"""

from __future__ import annotations

import importlib
import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

import graph_server as gs

TS = "2026-01-01T00:00:00+0900"


def make_root(status: str = "running") -> dict:
    return {"id": "root", "kind": "root", "label": "s", "model": "", "status": status,
            "started": TS, "ended": "", "task": "", "description": ""}


def make_session(name: str, nodes: list[dict] | None = None, herdr_pane: str = "",
                 last_ts: str = TS, root_status: str = "running") -> dict:
    session = {"name": name, "goal": "", "nodes": {"root": make_root(root_status)},
               "edges": [], "last_event_ts": last_ts}
    if herdr_pane:
        session["herdr_pane"] = herdr_pane
    for node in nodes or []:
        session["nodes"][node["id"]] = node
    return session


def codex_node(node_id: str = "c1", status: str = "running", pane: str = "w1:p9") -> dict:
    return {"id": node_id, "kind": "codex", "label": node_id, "status": status, "pane": pane, "out": ""}


def claude_node(node_id: str = "a1", status: str = "running") -> dict:
    return {"id": node_id, "kind": "claude", "label": "worker", "status": status}


def task_node(node_id: str = "T1", status: str = "running", pane: str = "w1:pT") -> dict:
    return {"id": node_id, "kind": "task", "label": "impl", "status": status, "pane": pane}


def pane(pane_id: str, session_id: str = "", label: str = "") -> dict:
    p: dict = {"pane_id": pane_id}
    if session_id:
        p["agent_session"] = {"value": session_id}
    if label:
        p["label"] = label
    return p


# ---------- 段階 1: pane 実体からの降格 ----------

def test_derive_liveness_demotes_missing_codex_pane(tmp_path):
    # 生きているつもりの codex。pane 一覧に pane が無ければ lost に降格する
    session = make_session("s-001", [codex_node(pane="w1:p9")], herdr_pane="w1:pR")
    gs.derive_liveness({"s-001": session}, [pane("w1:pR")], tmp_path)
    assert session["nodes"]["c1"]["status"] == "lost"


def test_derive_liveness_keeps_present_codex_pane(tmp_path):
    # pane が一覧にあれば running のまま。降格専用で昇格はしない
    session = make_session("s-001", [codex_node(pane="w1:p9")], herdr_pane="w1:pR")
    gs.derive_liveness({"s-001": session}, [pane("w1:pR"), pane("w1:p9")], tmp_path)
    assert session["nodes"]["c1"]["status"] == "running"


# ---------- 段階 2: reconcile 常時実行と task の scheduler pane ----------

def test_task_stalled_without_scheduler_pane(tmp_path):
    # ACTIVE の task。scheduler pane が無ければ stalled
    session = make_session("g-001", [task_node("T1", "running")], herdr_pane="w1:pR")
    gs.derive_liveness({"g-001": session}, [pane("w1:pR"), pane("w1:pT")], tmp_path)
    assert session["nodes"]["T1"]["status"] == "stalled"


def test_task_kept_with_scheduler_pane(tmp_path):
    # scheduler pane があれば graph state の status を尊重する
    session = make_session("g-001", [task_node("T1", "running")], herdr_pane="w1:pR")
    panes = [pane("w1:pR"), pane("w1:pT"), pane("w1:pS", label="g-001/scheduler")]
    gs.derive_liveness({"g-001": session}, panes, tmp_path)
    assert session["nodes"]["T1"]["status"] == "running"


def test_reconcile_refines_lost_codex(tmp_path, monkeypatch):
    # running ガードを外したので、lost に降格した codex もマーカーがあれば done に精緻化する
    monkeypatch.setattr(gs, "STATE_DIR", tmp_path / "state")
    log = tmp_path / "c1.log"
    log.write_text("AGENT_GRAPH_DONE:c1:0\n", encoding="utf-8")
    out = tmp_path / "c1.md"
    out.write_text("結果", encoding="utf-8")
    node = codex_node("c1", status="lost", pane=str(log))
    node["out"] = str(out)
    session = make_session("s-001", [node])
    gs.reconcile_codex_nodes(session, set())
    assert session["nodes"]["c1"]["status"] == "done"


# ---------- 段階 3: サブエージェントの orphaned ----------

def test_orphaned_child_becomes_lost(tmp_path):
    # 親 root が死なら agent_stop の無い claude 子は running のままにしない
    session = make_session("s-001", [claude_node("a1", "running")], root_status="ended")
    gs.derive_liveness({"s-001": session}, [], tmp_path)
    assert session["nodes"]["a1"]["status"] == "lost"


def test_child_kept_running_under_live_root(tmp_path):
    # 親が生きていれば子の生死は問えない。running を保つ
    session = make_session("s-001", [claude_node("a1", "running")], herdr_pane="w1:pR")
    gs.derive_liveness({"s-001": session}, [pane("w1:pR")], tmp_path)
    assert session["nodes"]["root"]["status"] == "running"
    assert session["nodes"]["a1"]["status"] == "running"


# ---------- 段階 4: 生死を正に。手動 start が復活しない ----------

def test_manual_start_does_not_revive_dead_session(tmp_path):
    # events に手で agent_start を足しても、root の pane が死なら子は running にならない
    events = [
        {"ts": TS, "event": "session_start", "session": "s-001", "model": "fable", "herdr_pane": "w1:pDEAD"},
        {"ts": "2026-01-01T00:01:00+0900", "event": "agent_start", "session": "s-001",
         "agent_id": "a1", "agent_type": "general-purpose"},
    ]
    sessions: dict = {}
    gs.apply_events(events, sessions, {})
    assert sessions["s-001"]["nodes"]["a1"]["status"] == "running"  # 追記の暫定値
    gs.derive_liveness(sessions, [pane("w1:pOTHER")], tmp_path)
    assert sessions["s-001"]["nodes"]["root"]["status"] == "ended"
    assert sessions["s-001"]["nodes"]["a1"]["status"] != "running"


def test_manual_start_stays_running_when_root_pane_alive(tmp_path):
    # root の pane が生きていれば子は running のまま。生死を問えない子は親に従う
    events = [
        {"ts": TS, "event": "session_start", "session": "s-001", "model": "fable", "herdr_pane": "w1:pR"},
        {"ts": "2026-01-01T00:01:00+0900", "event": "agent_start", "session": "s-001",
         "agent_id": "a1", "agent_type": "general-purpose"},
    ]
    sessions: dict = {}
    gs.apply_events(events, sessions, {})
    gs.derive_liveness(sessions, [pane("w1:pR")], tmp_path)
    assert sessions["s-001"]["nodes"]["root"]["status"] in ("running", "idle")
    assert sessions["s-001"]["nodes"]["a1"]["status"] == "running"


def test_apply_events_records_herdr_pane(tmp_path):
    # session_start の herdr_pane を session に残す
    events = [{"ts": TS, "event": "session_start", "session": "s-001", "model": "fable", "herdr_pane": "w1:pR"}]
    sessions: dict = {}
    gs.apply_events(events, sessions, {})
    assert sessions["s-001"]["herdr_pane"] == "w1:pR"


def test_panes_none_falls_back_to_time(tmp_path, monkeypatch):
    # pane 取得不能のときは 30 分判定に委ねる。古いセッションは終了、新しいセッションは残す
    monkeypatch.setattr(gs, "stale_threshold_sec", lambda: 1800.0)
    old = make_session("s-old", last_ts="2020-01-01T00:00:00+0900")
    fresh = make_session("s-new", last_ts=gs.now_iso())
    gs.derive_liveness({"s-old": old, "s-new": fresh}, None, tmp_path)
    assert old["nodes"]["root"]["status"] == "ended"
    assert fresh["nodes"]["root"]["status"] == "running"


# ---------- 段階 5: hook が herdr_pane を残す ----------

@pytest.fixture
def isolated_hook(tmp_path, monkeypatch) -> Iterator[tuple[object, Path]]:
    project = tmp_path / "repo"
    (project / ".agents" / "state").mkdir(parents=True)
    monkeypatch.setenv("AGENT_GRAPH_PROJECT", str(project))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.delenv("AGENT_GRAPH_PARENT_SESSION", raising=False)
    import agent_hook
    import common
    importlib.reload(common)
    yield importlib.reload(agent_hook), project
    monkeypatch.undo()
    importlib.reload(common)
    importlib.reload(agent_hook)


@pytest.mark.skip(
    reason="agent_hook.py がハーネスの保護対象で編集不可。herdr_pane の記録を入れられるまで保留"
)
def test_session_start_writes_herdr_pane(isolated_hook, monkeypatch):
    hook, project = isolated_hook
    monkeypatch.setenv("HERDR_PANE_ID", "w1:pR")
    hook.handle_session_start(
        {"session_id": "sid-new", "source": "startup", "cwd": str(project),
         "model": "fable", "hook_event_name": "SessionStart"}
    )
    events_path = project / ".agents" / "state" / "events.jsonl"
    events = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip().endswith("}")]
    starts = [e for e in events if e.get("event") == "session_start"]
    assert starts and starts[-1].get("herdr_pane") == "w1:pR"
