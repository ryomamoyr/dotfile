"""ハーネスの回帰テスト: 保護パス・Bash の書き込み先・危険コマンド・記録失敗時の拒否維持

参考実装 (refference/.agents/tests/test_harness.py) からの移植。
参考実装は「.agents/ がツールキット本体かつ実行時データ」という単一リポジトリ構成だったため、
".agents/bin/harness.py" のようなパス文字列だけでツール本体を保護できた。
現行構成は agent-graph/tool（グローバルなツールキット、~/.local/share/agent-graph に symlink）と
呼び出し元リポジトリの .agents/（実行時データのみ）を分離しているため、
harness.py 自身の保護は「ツールキット相対」（TOOL_DIR 基準）で検査する必要がある。
そのため PROTECTED_RELATIVE は「呼び出し元プロジェクト相対で保護されるパス」に絞り、
ツール本体（bin/harness.py 等）の保護は別途 TOOL_DIR 起点の絶対パスで検査する。
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

import harness

PROJECT_ENV = "AGENT_GRAPH_PROJECT"

# 保護対象。プロジェクト相対で保護される実行時データと設定・秘密情報
PROTECTED_RELATIVE = [
    ".claude/settings.json",
    ".claude/hooks/agent-graph-hook.sh",
    ".codex/config.toml",
    ".codex/hooks/guard-sensitive-files.sh",
    ".agents/graph/demo-001/tasks.yaml",
    ".agents/state/events.jsonl",
    ".git/config",
    ".env",
    ".env.local",
    "secrets/server.pem",
    "secrets/server.key",
]

ALLOWED_RELATIVE = [
    "src/a.py",
    "docs/human/index.html",
    ".agents/worktrees/demo/src/a.py",
    ".agents/tests/test_harness.py",
    # bin の harness/agent_hook/common 以外は編集可（ツールキット相対の保護対象外）
    ".agents/bin/graph_server.py",
]

# ツール本体（TOOL_DIR = agent-graph/tool 直下）。project 引数に依らず絶対パスで保護される
TOOLKIT_PROTECTED = [
    BIN_DIR / "harness.py",
    BIN_DIR / "agent_hook.py",
    BIN_DIR / "common.py",
]

# ツールキット相対でも保護対象外（scope 外のスクリプトは編集可）
TOOLKIT_ALLOWED = [
    BIN_DIR / "graph_server.py",
    BIN_DIR / "run_graph.py",
    BIN_DIR / "spawn_codex.py",
    BIN_DIR / "herdr_runner.py",
]

# 書き込み先の抽出で拒否したいコマンド
DENY_BASH = [
    "echo x > .env",
    "echo x >> .env",
    "echo x >.env",
    "tee ~/.claude/settings.json",
    f"cat foo | tee -a {BIN_DIR / 'harness.py'}",
    "cp x ~/.ssh/id_rsa",
    "mv x .claude/settings.json",
    "install -m 644 x .codex/config.toml",
    "sed -i '' s/a/b/ .agents/graph/demo-001/tasks.yaml",
    f"perl -pi -e s/a/b/ {BIN_DIR / 'common.py'}",
]

ALLOWED_BASH = [
    "echo x > out.txt",
    "cp src/a.py src/b.py",
    "sed -i '' s/a/b/ src/a.py",
    "grep -r foo src",
]


def joined(*parts: str) -> str:
    # 危険な文字列をそのまま書くと hook がこのファイルの作成自体を止める
    return " ".join(parts)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return tmp_path.resolve()


@pytest.mark.parametrize("relative", PROTECTED_RELATIVE)
def test_protected_path_is_denied(project: Path, relative: str) -> None:
    assert harness.check_path(relative, project)


@pytest.mark.parametrize("relative", ALLOWED_RELATIVE)
def test_ordinary_path_is_allowed(project: Path, relative: str) -> None:
    assert harness.check_path(relative, project) == ""


@pytest.mark.parametrize("path", TOOLKIT_PROTECTED)
def test_toolkit_own_script_is_denied(project: Path, path: Path) -> None:
    # ツール本体は呼び出し元プロジェクトに関わらず、絶対パス（TOOL_DIR 相対）で保護される
    assert harness.check_path(str(path), project)


@pytest.mark.parametrize("path", TOOLKIT_ALLOWED)
def test_toolkit_other_script_is_allowed(project: Path, path: Path) -> None:
    assert harness.check_path(str(path), project) == ""


def test_absolute_path_inside_project_is_denied(project: Path) -> None:
    assert harness.check_path(str(project / ".claude" / "settings.json"), project)


def test_home_config_is_denied(project: Path) -> None:
    # symlink 越しの ~/.claude/settings.json もホーム相対の形で一致させる
    assert harness.check_path("~/.claude/settings.json", project)


def test_empty_path_is_allowed(project: Path) -> None:
    assert harness.check_path("", project) == ""


@pytest.mark.parametrize("command", DENY_BASH)
def test_bash_write_target_is_denied(project: Path, command: str) -> None:
    assert harness.check_bash(command, project)


@pytest.mark.parametrize("command", ALLOWED_BASH)
def test_bash_without_protected_target_is_allowed(project: Path, command: str) -> None:
    assert harness.check_bash(command, project) == ""


def test_unparsable_command_is_denied(project: Path) -> None:
    # 引用符が閉じていない入力は分割できない。検査できないので拒否側に倒す
    assert harness.check_bash("echo 'unterminated", project)


def test_existing_deny_bash_still_works(project: Path) -> None:
    dangerous = [
        joined("git", "push", "origin", "main"),
        joined("su" + "do", "id"),
        joined("rm", "-rf", "~/"),
        joined("git", "reset", "--hard", "HEAD~1"),
        joined("chmod", "777", "src"),
    ]
    for command in dangerous:
        assert harness.check_bash(command, project), command


@pytest.fixture
def hook_with_broken_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[object]:
    # 状態ファイルが壊れた偽のリポジトリを PROJECT_DIR にして読み込み直す
    project = tmp_path / "repo"
    (project / ".agents" / "state").mkdir(parents=True)
    (project / ".agents" / "state" / "sessions.json").write_text(
        "{壊れている", encoding="utf-8"
    )
    monkeypatch.setenv(PROJECT_ENV, str(project))
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    import agent_hook
    import common

    importlib.reload(common)
    yield importlib.reload(agent_hook)
    monkeypatch.undo()
    importlib.reload(common)
    importlib.reload(agent_hook)


def test_denial_survives_broken_sessions_file(hook_with_broken_state: object) -> None:
    hook = hook_with_broken_state
    with pytest.raises(SystemExit) as raised:
        hook.handle_pre_tool_use(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "Bash",
                "tool_input": {"command": "su" + "do id"},
            }
        )
    assert raised.value.code == 2


def test_protected_edit_denial_survives_broken_sessions_file(
    hook_with_broken_state: object,
) -> None:
    hook = hook_with_broken_state
    with pytest.raises(SystemExit) as raised:
        hook.handle_pre_tool_use(
            {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "Write",
                "tool_input": {"file_path": ".claude/settings.json"},
            }
        )
    assert raised.value.code == 2


def test_allowed_tool_call_survives_broken_sessions_file(
    hook_with_broken_state: object,
) -> None:
    # 記録が失敗しても許可は許可のまま。例外で exit 1 にしない
    hook = hook_with_broken_state
    hook.handle_pre_tool_use(
        {
            "hook_event_name": "PreToolUse",
            "session_id": "s1",
            "tool_name": "Bash",
            "tool_input": {"command": "echo ok"},
        }
    )
