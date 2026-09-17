"""セッション採番のテスト: fork の継承と、UserPromptSubmit まで採番を遅らせる挙動を確認する"""

from __future__ import annotations

import importlib
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stdout
from pathlib import Path

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

import agent_hook
import common

ISOLATED_ENV = (
    common.PROJECT_ENV,
    "CLAUDE_PROJECT_DIR",
    agent_hook.PARENT_SESSION_ENV,
    agent_hook.HERDR_PANE_ENV,
)
# 並行テストの規模: 追記件数、書き換えの試行上限、追記スレッドの待ち時間
CONCURRENT_APPENDS = 300
CONCURRENT_DROPS = 200
CONCURRENT_JOIN_SEC = 30


class SessionNamingTest(unittest.TestCase):
    def setUp(self) -> None:
        # 実データを触らないよう、状態の置き場を一時ディレクトリに差し替えて再読み込みする
        self.tmp = tempfile.TemporaryDirectory()
        self.saved_env = {key: os.environ.get(key) for key in ISOLATED_ENV}
        for key in ISOLATED_ENV:
            os.environ.pop(key, None)
        os.environ[common.PROJECT_ENV] = self.tmp.name
        importlib.reload(common)
        self.hook = importlib.reload(agent_hook)
        self.assertEqual(self.hook.PROJECT_DIR, Path(self.tmp.name).resolve())

    def tearDown(self) -> None:
        for key, value in self.saved_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        importlib.reload(common)
        importlib.reload(agent_hook)
        self.tmp.cleanup()

    def read_counter(self) -> int:
        path = self.hook.COUNTER_PATH
        return int(path.read_text().strip()) if path.exists() else 0

    def read_sessions(self) -> dict:
        path = self.hook.SESSIONS_PATH
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    def read_current(self) -> str:
        path = self.hook.CURRENT_SESSION_PATH
        return path.read_text().strip() if path.exists() else ""

    def send_session_start(self, session_id: str, source: str = "startup") -> str:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.hook.handle_session_start(
                {
                    "hook_event_name": "SessionStart",
                    "session_id": session_id,
                    "source": source,
                    "cwd": self.tmp.name,
                }
            )
        return buffer.getvalue()

    def send_user_prompt(self, session_id: str, prompt: str = "最初の指示") -> str:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            self.hook.record_turn_state(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "session_id": session_id,
                    "prompt": prompt,
                }
            )
        return buffer.getvalue()

    def send_stop(self, session_id: str) -> None:
        with redirect_stdout(io.StringIO()):
            self.hook.record_turn_state(
                {
                    "hook_event_name": "Stop",
                    "session_id": session_id,
                    "transcript_path": "",
                    "last_assistant_message": "完了",
                }
            )

    def send_session_end(self, session_id: str, reason: str = "clear") -> None:
        with redirect_stdout(io.StringIO()):
            self.hook.handle_session_end(
                {
                    "hook_event_name": "SessionEnd",
                    "session_id": session_id,
                    "reason": reason,
                }
            )

    def test_known_session_id_keeps_counter(self) -> None:
        self.send_session_start("s1")
        self.send_user_prompt("s1")
        before = self.read_counter()
        name = self.hook.resolve_session_name("s1")
        self.assertEqual(name, self.read_sessions()["s1"])
        self.assertEqual(self.read_counter(), before)

    def test_fork_inherits_latest_turn_session(self) -> None:
        self.send_session_start("s1")
        self.send_user_prompt("s1")
        name = self.read_sessions()["s1"]
        before = self.read_counter()
        # 継承元が current_session ではなく直近 turn であることを確かめる
        self.hook.CURRENT_SESSION_PATH.write_text("stale-999")
        self.send_session_start("s2", source="fork")
        self.assertEqual(self.read_sessions()["s2"], name)
        self.assertEqual(self.read_counter(), before)
        self.assertEqual(self.read_current(), name)

    def test_fork_falls_back_to_current_session(self) -> None:
        self.hook.CURRENT_SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.hook.CURRENT_SESSION_PATH.write_text("proj-042")
        self.send_session_start("s1", source="fork")
        self.assertEqual(self.read_sessions()["s1"], "proj-042")
        self.assertEqual(self.read_counter(), 0)

    def test_session_start_alone_keeps_counter(self) -> None:
        output = self.send_session_start("s1")
        self.assertEqual(self.read_counter(), 0)
        self.assertEqual(self.read_sessions(), {})
        self.assertEqual(output, "")
        starts = [e for e in common.read_events() if e["event"] == "session_start"]
        self.assertEqual(starts[-1]["session"], "")

    def test_first_user_prompt_assigns_name(self) -> None:
        self.send_session_start("s1")
        output = self.send_user_prompt("s1")
        name = f"{self.hook.PROJECT_DIR.name}-001"
        self.assertEqual(self.read_counter(), 1)
        self.assertEqual(self.read_sessions()["s1"], name)
        self.assertEqual(self.read_current(), name)
        self.assertIn(f"このセッションの識別子は {name} です", output)
        self.assertEqual(common.read_events()[-1]["session"], name)

    def test_second_user_prompt_keeps_counter(self) -> None:
        self.send_session_start("s1")
        self.send_user_prompt("s1")
        self.send_stop("s1")
        output = self.send_user_prompt("s1", "2 回目の指示")
        self.assertEqual(self.read_counter(), 1)
        self.assertEqual(output, "")
        self.assertEqual(common.read_events()[-1]["session"], self.read_sessions()["s1"])


    def test_empty_session_end_removes_events(self) -> None:
        self.send_session_start("s1")
        self.send_session_end("s1")
        events = common.read_events()
        self.assertEqual([e for e in events if e.get("session_id") == "s1"], [])
        self.assertEqual([e for e in events if e["event"] == "session_end"], [])

    def test_empty_session_end_forgets_session_id(self) -> None:
        self.send_session_start("s1")
        self.send_user_prompt("s1")
        name = self.read_sessions()["s1"]
        # 発話せずに終わった fork は消え、継承元のセッションは残る
        self.send_session_start("s2", source="fork")
        self.send_session_end("s2")
        self.assertEqual(self.read_sessions(), {"s1": name})
        turns = [e for e in common.read_events() if e["event"] == "turn_start"]
        self.assertEqual([e["session"] for e in turns], [name])

    def test_session_with_turn_records_session_end(self) -> None:
        self.send_session_start("s1")
        self.send_user_prompt("s1")
        before = len(common.read_events())
        self.send_session_end("s1")
        events = common.read_events()
        self.assertEqual(len(events), before + 1)
        self.assertEqual(events[-1]["event"], "session_end")
        self.assertEqual(events[-1]["session"], self.read_sessions()["s1"])


    def test_legacy_turn_protects_session(self) -> None:
        # session_id を持たない旧形式の turn_start があるセッションは削除しない
        name = "legacy-001"
        common.save_json(self.hook.SESSIONS_PATH, {"s1": name})
        common.append_event({"event": "turn_start", "session": name, "prompt": "旧形式"})
        self.send_session_start("s1")
        before = len(common.read_events())
        self.send_session_end("s1")
        events = common.read_events()
        self.assertEqual(len(events), before + 1)
        self.assertEqual(events[-1]["event"], "session_end")
        self.assertTrue(any(e.get("session_id") == "s1" for e in events))
        self.assertEqual(self.read_sessions(), {"s1": name})

    def test_legacy_turn_of_other_session_is_not_protected(self) -> None:
        common.save_json(self.hook.SESSIONS_PATH, {"s1": "legacy-001"})
        common.append_event(
            {"event": "turn_start", "session": "legacy-002", "prompt": "別名の旧形式"}
        )
        self.send_session_start("s1")
        self.send_session_end("s1")
        events = common.read_events()
        self.assertEqual([e for e in events if e.get("session_id") == "s1"], [])
        self.assertEqual([e for e in events if e["event"] == "session_end"], [])
        self.assertEqual(self.read_sessions(), {})


    def test_drop_keeps_concurrent_appends(self) -> None:
        # 書き換え中の追記が失われないこと。ロックが無ければ取りこぼす
        self.send_session_start("s1")
        done = threading.Event()

        def append_many() -> None:
            for index in range(CONCURRENT_APPENDS):
                common.append_event(
                    {"event": "noise", "session": "other", "index": index}
                )
            done.set()

        writer = threading.Thread(target=append_many)
        writer.start()
        for _ in range(CONCURRENT_DROPS):
            if done.is_set():
                break
            self.hook.drop_session_events("s1")
        writer.join(timeout=CONCURRENT_JOIN_SEC)
        self.assertTrue(done.is_set(), "追記スレッドが終わらなかった")
        self.hook.drop_session_events("s1")
        noise = [e["index"] for e in common.read_events() if e["event"] == "noise"]
        self.assertEqual(sorted(noise), list(range(CONCURRENT_APPENDS)))
        self.assertEqual([e for e in common.read_events() if e.get("session_id") == "s1"], [])


    def use_project(self, project: Path) -> None:
        # 別の擬似リポジトリを PROJECT_DIR にして読み込み直す
        os.environ[common.PROJECT_ENV] = str(project)
        importlib.reload(common)

    def make_worktree(self) -> tuple[Path, Path]:
        # worktree の .git は「gitdir: <共通 git ディレクトリ>/worktrees/<名前>」1 行のファイル
        root = Path(self.tmp.name)
        common_dir = root / "main" / ".git"
        (common_dir / "worktrees" / "wt").mkdir(parents=True)
        worktree = root / "wt"
        worktree.mkdir()
        (worktree / ".git").write_text(f"gitdir: {common_dir / 'worktrees' / 'wt'}\n")
        return worktree, common_dir

    def test_worktree_git_file_does_not_raise(self) -> None:
        worktree, _ = self.make_worktree()
        self.use_project(worktree)
        common.ensure_git_exclude()
        self.assertFalse((worktree / ".git" / "info").exists())

    def test_worktree_exclude_goes_to_common_git_dir(self) -> None:
        worktree, common_dir = self.make_worktree()
        self.use_project(worktree)
        common.ensure_git_exclude()
        exclude = common_dir / "info" / "exclude"
        self.assertEqual(exclude.read_text(encoding="utf-8").splitlines(), [".agents/"])

    def test_plain_git_dir_keeps_behavior(self) -> None:
        project = Path(self.tmp.name) / "plain"
        (project / ".git").mkdir(parents=True)
        self.use_project(project)
        common.ensure_git_exclude()
        exclude = project / ".git" / "info" / "exclude"
        self.assertEqual(exclude.read_text(encoding="utf-8").splitlines(), [".agents/"])


if __name__ == "__main__":
    unittest.main()
