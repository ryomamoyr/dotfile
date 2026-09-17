"""生死判定の土台: claude の見分け、所有者 PID の遡り、起動時刻の取得、イベントへの PID 付与"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

import common as cm

# 祖先の起点。ps を擬似化するテストで親 PID として使う
PARENT_PID = 100
NO_OWNER_MESSAGE = "祖先に claude が見つからず"


def fake_ancestors(monkeypatch, chain: dict[int, str]) -> None:
    # pid -> command の対応から擬似的な親子列を作る。ppid は pid + 1 で連ねる
    monkeypatch.setattr(os, "getppid", lambda: PARENT_PID)

    def fake_run_ps(fields: str, pid: int) -> str:
        if pid not in chain:
            return ""
        return f"{pid + 1} {chain[pid]}"

    monkeypatch.setattr(cm, "run_ps", fake_run_ps)


@pytest.mark.parametrize(
    "command",
    [
        "/Users/r/.local/bin/claude",
        "node /opt/homebrew/bin/claude",
        "node /x/@anthropic-ai/claude-code/cli.js",
        "bun /x/node_modules/@anthropic-ai/claude-code/cli.js",
    ],
)
def test_is_claude_accepts_native_and_js_runtimes(command):
    # 実行ファイルが claude か、JS ランタイムが claude の本体を引数に取る形
    assert cm.is_claude(command)


@pytest.mark.parametrize(
    "command",
    [
        "uv run --project .agents python agent_hook.py",
        "/bin/zsh -c claude",
        '/bin/sh -c "uv run --project .agents python agent_hook.py claude"',
        "/usr/local/bin/claude-graph-viewer",
        "",
    ],
)
def test_is_claude_rejects_wrappers_and_lookalikes(command):
    # シェル経由の起動や名前の似た別コマンドを所有者と見なさない
    assert not cm.is_claude(command)


def test_owner_pid_walks_up_to_claude(monkeypatch):
    # hook の直接の親は uv。祖先を遡って claude の PID を返す
    fake_ancestors(
        monkeypatch,
        {
            PARENT_PID: "uv run --project .agents python agent_hook.py",
            PARENT_PID + 1: "/bin/zsh -c hook",
            PARENT_PID + 2: "node /x/@anthropic-ai/claude-code/cli.js",
        },
    )
    assert cm.owner_pid() == PARENT_PID + 2


def test_owner_pid_stops_at_walk_limit(monkeypatch, capsys):
    # 上限より遠い claude は探さない。OWNER_WALK_MAX 段までで打ち切る
    chain = {
        PARENT_PID + step: "uv run --project .agents python agent_hook.py"
        for step in range(cm.OWNER_WALK_MAX)
    }
    chain[PARENT_PID + cm.OWNER_WALK_MAX] = "/Users/r/.local/bin/claude"
    fake_ancestors(monkeypatch, chain)
    assert cm.owner_pid() == 0
    assert NO_OWNER_MESSAGE in capsys.readouterr().err


def test_owner_pid_returns_zero_and_warns_without_claude(monkeypatch, capsys):
    # 祖先に claude が無ければ 0。旧方式に落ちることを stderr に 1 行残す
    fake_ancestors(monkeypatch, {PARENT_PID: "/sbin/launchd"})
    assert cm.owner_pid() == 0
    err = capsys.readouterr().err
    assert NO_OWNER_MESSAGE in err
    assert len(err.strip().splitlines()) == 1


def test_process_start_time_forces_c_locale(monkeypatch):
    # 起動時刻は文字列で突き合わせる。ps の表記をロケールで揺らさない
    captured: dict = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout="Thu Jan  1 00:00:00 1970\n")

    monkeypatch.setenv("LC_ALL", "ja_JP.UTF-8")
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert cm.process_start_time(4242) == "Thu Jan  1 00:00:00 1970"
    assert captured["argv"] == ["ps", "-o", "lstart=", "-p", "4242"]
    assert captured["env"]["LC_ALL"] == "C"


def test_process_start_time_is_empty_when_ps_fails(monkeypatch):
    # 消えた PID では ps が失敗する。空文字を返して比較側に判断を委ねる
    monkeypatch.setattr(
        subprocess, "run", lambda argv, **kwargs: SimpleNamespace(returncode=1, stdout="")
    )
    assert cm.process_start_time(4242) == ""


def test_append_event_records_owner_pid(tmp_path, monkeypatch):
    # 全イベントに所有者の PID と起動時刻を付ける。ダッシュボードの生死問い合わせの鍵
    monkeypatch.setattr(cm, "EVENTS_PATH", tmp_path / "events.jsonl")
    monkeypatch.setattr(cm, "EVENTS_LOCK_PATH", tmp_path / "events.lock")
    monkeypatch.setattr(cm, "ensure_dirs", lambda: None)
    monkeypatch.setattr(cm, "owner_pid", lambda: 4242)
    monkeypatch.setattr(cm, "process_start_time", lambda pid: f"start-{pid}")
    cm.append_event({"event": "session_start", "session": "s-001"})
    record = json.loads((tmp_path / "events.jsonl").read_text(encoding="utf-8"))
    assert record["pid"] == 4242
    assert record["pid_start"] == "start-4242"
    assert record["event"] == "session_start"
    assert record["ts"]


def test_append_event_omits_pid_without_owner(tmp_path, monkeypatch):
    # 所有者が取れないときは PID を書かない。誤った生存判定の材料にしない
    monkeypatch.setattr(cm, "EVENTS_PATH", tmp_path / "events.jsonl")
    monkeypatch.setattr(cm, "EVENTS_LOCK_PATH", tmp_path / "events.lock")
    monkeypatch.setattr(cm, "ensure_dirs", lambda: None)
    monkeypatch.setattr(cm, "owner_pid", lambda: 0)
    cm.append_event({"event": "session_start", "session": "s-001"})
    record = json.loads((tmp_path / "events.jsonl").read_text(encoding="utf-8"))
    assert "pid" not in record
    assert "pid_start" not in record
