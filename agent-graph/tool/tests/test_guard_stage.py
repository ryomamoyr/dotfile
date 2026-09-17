"""ガードの root 所有化(agent-graph/stage/guard/)の回帰テスト

対象は次の2つに限定する。判定ロジック本体(bin/harness.py)は test_harness.py で
既にカバー済みのため、ここでは重複させない。

1. agent-graph-hook.sh の入口ロジック(root_owned / guard_chain / main の分岐)
2. install-guard.sh の静的な妥当性(配置元パス・chmod/chown引数・構文)

sudo は一切使わない。root所有チェックの「合格」ケースは stat コマンドを
スタブ(常に "0 755" を返す偽 stat を PATH 先頭に置く)してシミュレートする。
「不合格」ケースは実際の一時ディレクトリ(現在の利用者所有)や実シンボリックリンク
を使い、本物の分岐を通す。
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
TOOL_DIR = TESTS_DIR.parent
AGENT_GRAPH_DIR = TOOL_DIR.parent
GUARD_STAGE_DIR = AGENT_GRAPH_DIR / "stage" / "guard"
HOOK_SCRIPT = GUARD_STAGE_DIR / "agent-graph-hook.sh"
INSTALL_SCRIPT = GUARD_STAGE_DIR / "install-guard.sh"
HARNESS_STAGE = GUARD_STAGE_DIR / "harness.py"
HARNESS_TOOL = TOOL_DIR / "bin" / "harness.py"

MISSING_MESSAGE = "ガードが未導入"
TAMPERED_MESSAGE = "改ざんの可能性があるため停止します"
UV_MISSING_MESSAGE = "uv が見つかりません"

MINIMAL_PATH = "/usr/bin:/bin:/sbin:/usr/sbin"


def _run(argv: list[str], env: dict[str, str], input_text: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        argv,
        input=input_text,
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


def _base_env(tmpdir: Path, path: str = MINIMAL_PATH, home: str | None = None) -> dict[str, str]:
    # 本物の環境から必要最小限だけを引き継ぎ、TMPDIR とPATHをテスト用に固定する
    env = {"PATH": path, "TMPDIR": str(tmpdir), "HOME": home or os.environ.get("HOME", "/nonexistent")}
    # macOS のロケール関連が無いとエラーになる呼び出し元がいるため保険で引き継ぐ
    for key in ("LANG", "LC_ALL"):
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def _make_stat_stub(bin_dir: Path) -> None:
    # 呼び出し元のパスに関わらず「root所有・mode 755」を返す偽 stat
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "stat"
    stub.write_text("#!/usr/bin/env bash\necho '0 755'\n")
    stub.chmod(0o755)


def _patched_hook(tmp_path: Path, guard_dir: Path) -> Path:
    # 実スクリプトの GUARD_DIR 行だけをテスト用ディレクトリへ差し替えた複製を作る
    # (本物ファイルは変更しない。判定ロジックは触らない)
    text = HOOK_SCRIPT.read_text(encoding="utf-8")
    original = 'GUARD_DIR="/usr/local/lib/agent-graph"'
    assert text.count(original) == 1, "GUARD_DIR の宣言行が想定と異なる。スクリプトの変更を確認する"
    patched = text.replace(original, f'GUARD_DIR="{guard_dir}"')
    dest = tmp_path / "agent-graph-hook.patched.sh"
    dest.write_text(patched, encoding="utf-8")
    dest.chmod(0o755)
    return dest


def _hook_functions_only() -> str:
    # main "$@" の呼び出し行を除いた関数定義だけを source する用のテキスト
    lines = HOOK_SCRIPT.read_text(encoding="utf-8").splitlines()
    assert lines[-1].strip() == 'main "$@"', "末尾が main の呼び出しでない。スクリプト構造が変わった"
    return "\n".join(lines[:-1])


# ---------- 1. root_owned / guard_chain の単体テスト(関数を直接source) ----------


def test_root_owned_rejects_symlink(tmp_path):
    target = tmp_path / "real"
    target.mkdir()
    link = tmp_path / "link"
    link.symlink_to(target)
    script = f'{_hook_functions_only()}\nroot_owned "{link}"; echo EXIT:$?\n'
    result = _run(["bash", "-c", script], _base_env(tmp_path))
    assert "EXIT:1" in result.stdout, result.stdout + result.stderr


def test_root_owned_rejects_current_user_owner(tmp_path):
    # テスト実行者は root ではない前提。実ディレクトリはそのまま不合格になる
    owned = tmp_path / "owned"
    owned.mkdir()
    script = f'{_hook_functions_only()}\nroot_owned "{owned}"; echo EXIT:$?\n'
    result = _run(["bash", "-c", script], _base_env(tmp_path))
    assert "EXIT:1" in result.stdout, result.stdout + result.stderr


def test_root_owned_rejects_missing_path(tmp_path):
    missing = tmp_path / "does-not-exist"
    script = f'{_hook_functions_only()}\nroot_owned "{missing}"; echo EXIT:$?\n'
    result = _run(["bash", "-c", script], _base_env(tmp_path))
    assert "EXIT:1" in result.stdout, result.stdout + result.stderr


def test_root_owned_accepts_root_owned_safe_mode(tmp_path):
    stub_bin = tmp_path / "stubbin"
    _make_stat_stub(stub_bin)
    target = tmp_path / "safe"
    target.mkdir()
    script = f'{_hook_functions_only()}\nroot_owned "{target}"; echo EXIT:$?\n'
    env = _base_env(tmp_path, path=f"{stub_bin}:{MINIMAL_PATH}")
    result = _run(["bash", "-c", script], env)
    assert "EXIT:0" in result.stdout, result.stdout + result.stderr


def test_root_owned_rejects_root_owned_group_writable(tmp_path):
    stub_bin = tmp_path / "stubbin"
    stub_bin.mkdir()
    stub = stub_bin / "stat"
    # root所有だが group 書き込み可(0775相当)を模す
    stub.write_text("#!/usr/bin/env bash\necho '0 775'\n")
    stub.chmod(0o755)
    target = tmp_path / "loose"
    target.mkdir()
    script = f'{_hook_functions_only()}\nroot_owned "{target}"; echo EXIT:$?\n'
    env = _base_env(tmp_path, path=f"{stub_bin}:{MINIMAL_PATH}")
    result = _run(["bash", "-c", script], env)
    assert "EXIT:1" in result.stdout, result.stdout + result.stderr


def test_guard_chain_orders_from_root_to_target():
    script = f'{_hook_functions_only()}\nguard_chain "/a/b/c"\n'
    result = _run(["bash", "-c", script], _base_env(Path("/tmp")))
    lines = [line for line in result.stdout.splitlines() if line]
    assert lines == ["/", "/a", "/a/b", "/a/b/c"], result.stdout + result.stderr


# ---------- 2. main() の分岐(GUARD_DIR を差し替えた複製で検証) ----------


def test_hook_passes_through_when_not_installed(tmp_path):
    guard_dir = tmp_path / "usr_local_lib_agent_graph"  # 作らない = 未導入
    hook = _patched_hook(tmp_path, guard_dir)
    stamp_dir = tmp_path / "tmpdir1"
    stamp_dir.mkdir()
    result = _run([str(hook)], _base_env(stamp_dir))
    assert result.returncode == 0, result.stderr
    assert MISSING_MESSAGE in result.stderr


def test_hook_missing_message_shown_once_per_tmpdir(tmp_path):
    guard_dir = tmp_path / "usr_local_lib_agent_graph"
    hook = _patched_hook(tmp_path, guard_dir)
    stamp_dir = tmp_path / "tmpdir2"
    stamp_dir.mkdir()
    env = _base_env(stamp_dir)
    first = _run([str(hook)], env)
    second = _run([str(hook)], env)
    assert first.returncode == 0
    assert second.returncode == 0
    assert MISSING_MESSAGE in first.stderr
    assert MISSING_MESSAGE not in second.stderr


def test_hook_rejects_when_chain_is_user_owned(tmp_path):
    # スタブ無し = 本物の stat。テスト実行者(非root)所有のディレクトリなので必ず不合格になる
    guard_dir = tmp_path / "guard"
    guard_dir.mkdir()
    (guard_dir / "harness.py").write_text("# fake\n", encoding="utf-8")
    hook = _patched_hook(tmp_path, guard_dir)
    stamp_dir = tmp_path / "tmpdir3"
    stamp_dir.mkdir()
    result = _run([str(hook)], _base_env(stamp_dir))
    assert result.returncode == 2, result.stdout + result.stderr
    assert TAMPERED_MESSAGE in result.stderr


def test_hook_rejects_symlinked_ancestor_even_when_stat_reports_root_owned(tmp_path):
    # stat をスタブして「所有者はroot・書き込み権限も無い」と偽装しても、
    # symlink は -L チェックで実体を確認しているため素通りしない
    stub_bin = tmp_path / "stubbin"
    _make_stat_stub(stub_bin)
    real_dir = tmp_path / "real_guard"
    real_dir.mkdir()
    (real_dir / "harness.py").write_text("# fake\n", encoding="utf-8")
    link_dir = tmp_path / "guard_link"
    link_dir.symlink_to(real_dir)
    hook = _patched_hook(tmp_path, link_dir)
    stamp_dir = tmp_path / "tmpdir4"
    stamp_dir.mkdir()
    env = _base_env(stamp_dir, path=f"{stub_bin}:{MINIMAL_PATH}")
    result = _run([str(hook)], env)
    assert result.returncode == 2, result.stdout + result.stderr
    assert TAMPERED_MESSAGE in result.stderr


def test_hook_reaches_uv_check_and_stops_hard_when_uv_missing(tmp_path):
    # 祖先をすべて root所有・安全な権限に偽装(stat スタブ)して chain 検査を通過させ、
    # uv 不在の判定分岐(ハード停止)まで到達することを確認する
    stub_bin = tmp_path / "stubbin"
    _make_stat_stub(stub_bin)
    guard_dir = tmp_path / "guard5"
    guard_dir.mkdir()
    (guard_dir / "harness.py").write_text("# fake\n", encoding="utf-8")
    hook = _patched_hook(tmp_path, guard_dir)
    stamp_dir = tmp_path / "tmpdir5"
    stamp_dir.mkdir()
    fake_home = tmp_path / "fake_home"  # $HOME/.local/bin/uv が無い偽ホーム
    env = _base_env(stamp_dir, path=f"{stub_bin}:{MINIMAL_PATH}", home=str(fake_home))
    result = _run([str(hook)], env)
    assert result.returncode == 2, result.stdout + result.stderr
    assert UV_MISSING_MESSAGE in result.stderr
    assert TAMPERED_MESSAGE not in result.stderr


def test_hook_soft_flag_lets_uv_missing_pass_through(tmp_path):
    stub_bin = tmp_path / "stubbin"
    _make_stat_stub(stub_bin)
    guard_dir = tmp_path / "guard6"
    guard_dir.mkdir()
    (guard_dir / "harness.py").write_text("# fake\n", encoding="utf-8")
    hook = _patched_hook(tmp_path, guard_dir)
    stamp_dir = tmp_path / "tmpdir6"
    stamp_dir.mkdir()
    fake_home = tmp_path / "fake_home2"
    env = _base_env(stamp_dir, path=f"{stub_bin}:{MINIMAL_PATH}", home=str(fake_home))
    env["AGENT_GRAPH_HOOK_SOFT"] = "1"
    result = _run([str(hook)], env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert UV_MISSING_MESSAGE not in result.stderr
    assert TAMPERED_MESSAGE not in result.stderr


# ---------- 3. install-guard.sh の静的検証(実行しない) ----------


def test_install_guard_syntax_is_valid():
    # bash -n は構文チェックのみで実行はしない
    result = subprocess.run(
        ["bash", "-n", str(INSTALL_SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_install_guard_source_resolves_to_existing_harness_file():
    # SOURCE="$(cd -P "$(dirname "$0")" && pwd)/harness.py" は
    # install-guard.sh と同じディレクトリの harness.py を指す
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert 'SOURCE="$(cd -P "$(dirname "$0")" && pwd)/harness.py"' in text
    assert HARNESS_STAGE.is_file()
    assert not HARNESS_STAGE.is_symlink()


def test_install_guard_requires_root_before_touching_filesystem():
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert re.search(r'if \[ "\$\(id -u\)" -ne 0 \]', text)
    # root チェックの直後で exit 1 していることを確認する(先に潜って何か書いてしまわないか)
    match = re.search(r'if \[ "\$\(id -u\)" -ne 0 \]; then\n(.*?)\nfi', text, re.DOTALL)
    assert match is not None
    assert "exit 1" in match.group(1)


def test_install_guard_checks_same_ancestor_chain_as_hook():
    # DESIGN.md 通り / /usr /usr/local /usr/local/lib の4段を確認し、
    # hook 側 root_owned と同じ 0022 マスクを使っていること
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    assert "for parent in / /usr /usr/local /usr/local/lib" in text
    assert "8#$mode & 8#022" in text
    hook_text = HOOK_SCRIPT.read_text(encoding="utf-8")
    assert "8#$mode & 8#022" in hook_text


def test_install_guard_places_files_with_root_ownership_and_expected_modes():
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    # ディレクトリ: root:root 0755
    assert re.search(r'install\s+-d\s+-o\s+0\s+-g\s+0\s+-m\s+0755\s+"\$GUARD_DIR"', text)
    # 本体ファイル: root:root 0644、配置先は $GUARD (= $GUARD_DIR/harness.py)
    assert re.search(r'install\s+-o\s+0\s+-g\s+0\s+-m\s+0644\s+"\$STAGED"\s+"\$GUARD"', text)
    assert 'GUARD_DIR="/usr/local/lib/agent-graph"' in text
    assert 'GUARD="$GUARD_DIR/harness.py"' in text


def test_install_guard_validates_syntax_before_installing():
    # 構文が壊れた本体を置かないよう py_compile で検査してから install する順になっている
    text = INSTALL_SCRIPT.read_text(encoding="utf-8")
    compile_pos = text.index("py_compile")
    install_pos = text.index('install -o 0 -g 0 -m 0644 "$STAGED" "$GUARD"')
    assert compile_pos < install_pos


# ---------- 4. harness.py(ガード配置版)と bin/harness.py(判定ロジック本体)の同期 ----------


def test_stage_harness_compiles():
    result = subprocess.run(
        ["python3", "-m", "py_compile", str(HARNESS_STAGE)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def _strip_module_docstring(text: str) -> str:
    lines = text.splitlines(keepends=True)
    if not lines or not lines[0].startswith('"""'):
        return text
    if lines[0].count('"""') >= 2 and len(lines[0].strip()) > 3:
        return "".join(lines[1:])
    for index in range(1, len(lines)):
        if '"""' in lines[index]:
            return "".join(lines[index + 1 :])
    raise AssertionError("docstring の終端が見つからない")


def test_stage_harness_matches_tool_harness_except_docstring():
    # README「同期」節: 判定ロジックは agent-graph/tool/bin/harness.py と完全一致させる設計
    stage_body = _strip_module_docstring(HARNESS_STAGE.read_text(encoding="utf-8"))
    tool_body = _strip_module_docstring(HARNESS_TOOL.read_text(encoding="utf-8"))
    assert stage_body == tool_body, (
        "判定ロジックが agent-graph/tool/bin/harness.py と分岐している。"
        "README の同期手順に従って両方を直す必要がある"
    )


@pytest.mark.parametrize("path", [HOOK_SCRIPT, INSTALL_SCRIPT, HARNESS_STAGE])
def test_referenced_files_exist(path: Path):
    assert path.is_file()
