"""生死問い合わせからの状態導出: PID の実在・起動時刻・transcript の実体で running を裏付ける"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import pytest

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

import graph_server as gs

TS = "2026-01-01T00:00:00+0900"
SESSION_ID = "sid-1"
AGENT_ID = "a1"


def make_session(
    name: str = "s-001",
    pid: int = 0,
    pid_start: str = "",
    last_ts: str = TS,
    children: bool = True,
) -> dict:
    root = {
        "id": "root", "kind": "root", "label": name, "model": "", "status": "running",
        "started": TS, "ended": "", "task": "", "description": "",
    }
    session: dict = {
        "name": name, "goal": "", "nodes": {"root": root}, "edges": [], "last_event_ts": last_ts,
    }
    if pid:
        session["pid"] = pid
        session["pid_start"] = pid_start
    if children:
        session["nodes"][AGENT_ID] = {
            "id": AGENT_ID, "kind": "claude", "label": "worker", "status": "running",
        }
    return session


@pytest.fixture
def project(tmp_path, monkeypatch) -> Path:
    # transcript の置き場とセッション名の対応表を tmp に作る
    projects = tmp_path / "projects"
    slug = gs.project_slug(tmp_path)
    (projects / slug / SESSION_ID / "subagents").mkdir(parents=True)
    monkeypatch.setattr(gs, "CLAUDE_PROJECTS_DIR", projects)
    state = tmp_path / ".agents" / "state"
    state.mkdir(parents=True)
    (state / "sessions.json").write_text(
        json.dumps({SESSION_ID: "s-001"}), encoding="utf-8"
    )
    return tmp_path


def write_transcript(project: Path, agent_id: str = AGENT_ID, age_sec: float = 0.0) -> Path:
    slug = gs.project_slug(project)
    path = project / "projects" / slug / SESSION_ID / "subagents" / f"agent-{agent_id}.jsonl"
    path.write_text("{}\n", encoding="utf-8")
    if age_sec:
        stamp = time.time() - age_sec
        os.utime(path, (stamp, stamp))
    return path


def reaped_pid() -> int:
    # 終了して回収済みのプロセスの PID。実在しない PID を確実に得る
    proc = subprocess.Popen(["true"])
    proc.wait()
    return proc.pid


def test_dead_pid_ends_root_and_loses_children(project):
    # プロセスが消えていれば root は ended、子は lost
    session = make_session(pid=reaped_pid(), pid_start="Thu Jan  1 00:00:00 1970")
    gs.derive_liveness({"s-001": session}, [], project)
    assert session["nodes"]["root"]["status"] == "ended"
    assert session["nodes"][AGENT_ID]["status"] == "lost"
    assert session["nodes"][AGENT_ID]["reconciled"] == "親セッションの終了で失われた"


def test_pid_reuse_is_treated_as_dead(project):
    # PID は生きているが起動時刻が違う。別プロセスなので死と判定する
    session = make_session(pid=os.getpid(), pid_start="Thu Jan  1 00:00:00 1970")
    gs.derive_liveness({"s-001": session}, [], project)
    assert session["nodes"]["root"]["status"] == "ended"
    assert session["nodes"][AGENT_ID]["status"] == "lost"


def test_live_pid_with_transcript_keeps_running(project):
    # 起動時刻まで一致する生きたセッション。transcript があれば running を維持する
    write_transcript(project)
    session = make_session(pid=os.getpid(), pid_start=gs.process_start_time(os.getpid()))
    gs.derive_liveness({"s-001": session}, [], project)
    assert session["nodes"]["root"]["status"] == "running"
    assert session["nodes"][AGENT_ID]["status"] == "running"


def test_live_pid_without_transcript_loses_child(project):
    # 記録だけのノード。transcript が無ければ running にしない
    session = make_session(pid=os.getpid(), pid_start=gs.process_start_time(os.getpid()))
    gs.derive_liveness({"s-001": session}, [], project)
    assert session["nodes"]["root"]["status"] == "running"
    assert session["nodes"][AGENT_ID]["status"] == "lost"
    assert session["nodes"][AGENT_ID]["reconciled"] == "transcript が無い。記録だけのノード"


def test_idle_transcript_loses_child(project, monkeypatch):
    # transcript はあるが更新が止まっている。書き手がいないので lost
    monkeypatch.setattr(gs, "agent_idle_threshold_sec", lambda: 600.0)
    write_transcript(project, age_sec=3600)
    session = make_session(pid=os.getpid(), pid_start=gs.process_start_time(os.getpid()))
    gs.derive_liveness({"s-001": session}, [], project)
    assert session["nodes"][AGENT_ID]["status"] == "lost"
    assert session["nodes"][AGENT_ID]["reconciled"] == "transcript の更新が止まっている"


def test_legacy_session_without_pane_falls_back_to_time(project):
    # 旧形式で pane も無い。最後のイベントが古ければ root ended、子は lost
    session = make_session(last_ts="2020-01-01T00:00:00+0900")
    gs.derive_liveness({"s-001": session}, [], project)
    assert session["nodes"]["root"]["status"] == "ended"
    assert session["nodes"][AGENT_ID]["status"] == "lost"


def test_manual_agent_start_does_not_revive_dead_session(project):
    # 死んだセッションの events に手で agent_start を足しても running にならない
    pid = reaped_pid()
    events = [
        {"ts": TS, "event": "session_start", "session": "s-001", "model": "fable",
         "pid": pid, "pid_start": "Thu Jan  1 00:00:00 1970"},
        {"ts": TS, "event": "agent_start", "session": "s-001",
         "agent_id": AGENT_ID, "agent_type": "general-purpose"},
    ]
    sessions: dict = {}
    gs.apply_events(events, sessions, {})
    assert sessions["s-001"]["nodes"][AGENT_ID]["status"] == "running"  # 追記の暫定値
    gs.derive_liveness(sessions, [], project)
    assert sessions["s-001"]["nodes"]["root"]["status"] == "ended"
    assert sessions["s-001"]["nodes"][AGENT_ID]["status"] == "lost"


def test_process_start_time_is_locale_independent(monkeypatch):
    # 起動時刻は比較の鍵。ロケールを変えても表記が動かないことを確かめる
    baseline = gs.process_start_time(os.getpid())
    monkeypatch.setenv("LC_ALL", "ja_JP.UTF-8")
    assert gs.process_start_time(os.getpid()) == baseline
    assert re.match(r"^[A-Z][a-z]{2} ", baseline)
