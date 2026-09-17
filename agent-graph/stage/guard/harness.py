"""ハーネス: 危険操作の拒否・保護パス・lint・受け入れコマンド・スコープ検査（すべて決定的に判定する）

このファイルは /usr/local/lib/agent-graph/harness.py に root 所有で置く本体である。
配置は agent-graph/stage/guard/install-guard.sh が行う。
判定ロジックは agent-graph/tool/bin/harness.py と同一にする。分岐させると判定が食い違う。
"""

from __future__ import annotations

import fnmatch
import re
import shlex
import shutil
import subprocess
from pathlib import Path

from common import PROJECT_DIR, TOOL_DIR, run_cmd, tail

# native サンドボックスが Bash の子プロセスまで制限しても、これらの検査は残す。
# サンドボックスは Bash しか見ず Edit と Write は対象外のため。
# Codex の hook 入力 JSON は Claude Code と同じ形なので、同じ agent-graph-hook.sh を .codex/hooks.json からも呼ぶ
# 拒否する Bash コマンド。統合・push はスケジューラだけが行う
DENY_BASH: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\bgit\s+push\b"),
        "git push は禁止。統合と PR は run_graph の pr ノードが行う",
    ),
    (
        re.compile(
            r"\bgit\s+(reset\s+--hard|clean\s+-[a-zA-Z]*f|checkout\s+--\s|restore\s+\.)"
        ),
        "作業内容を破棄する git 操作は禁止",
    ),
    (re.compile(r"\bgit\s+branch\s+-D\b"), "ブランチの強制削除は禁止"),
    (
        re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(/|~|\$HOME|\.\.)(/|\s|$)"),
        "ルート・ホーム・親ディレクトリの再帰削除は禁止",
    ),
    (re.compile(r"\bsudo\b"), "sudo は禁止"),
    (
        re.compile(r"\b(curl|wget)\b[^|]*\|\s*(ba|z)?sh\b"),
        "ダウンロードしたスクリプトの直接実行は禁止",
    ),
    (re.compile(r"\bchmod\s+(-R\s+)?777\b"), "chmod 777 は禁止"),
    (
        re.compile(
            r"\b(cat|less|more|head|tail|grep|sed|awk|bat)\b[^\n|]*(\.env\b|\.ssh/|\.aws/credentials|\.netrc|\.pem\b)"
        ),
        "秘密情報ファイルの読み出しは禁止",
    ),
]

# 編集を拒否するパス。プロジェクト相対・ツールキット相対・ホーム相対・絶対のいずれかの形で一致すれば拒否する
PROTECTED_GLOBS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "**/id_rsa*",
    ".agents/state/**",
    ".git/**",
    # ハーネス自身と設定。書き換えられると以降の拒否と受け入れ検証がすべて無効になる。
    # ツール本体（agent-graph/tool/bin/*.py）はプロジェクト直下でなくツールキット相対で判定する
    ".claude/**",
    ".codex/**",
    "bin/harness.py",
    "bin/agent_hook.py",
    "bin/common.py",
    "bin/graph_model.py",
    ".agents/graph/**/tasks.yaml",
    # Python起動時のimportフック横取り対策
    "bin/sitecustomize.py",
    "bin/usercustomize.py",
    # 依存関係・仮想環境・コンパイル済みキャッシュの改ざん対策
    ".venv/**",
    "pyproject.toml",
    "uv.lock",
    "bin/__pycache__/**",
    "bin/*.pyc",
    # ガード本体の置き場（root所有）。絶対パスでのみ一致する
    "/usr/local/lib/agent-graph/**",
]

# コマンドの区切り。ここを境に次のコマンド名が始まる
COMMAND_SEPARATORS = {"|", "||", "&&", ";", "&", "|&"}
# 単独で現れるリダイレクト記号。次のトークンが書き込み先
REDIRECT_TOKEN = re.compile(r"^\d?>>?$")
# 書き込み先が続けて書かれたリダイレクト
REDIRECT_ATTACHED = re.compile(r"^\d?>>?(?P<target>.+)$")
# 引数すべてが書き込み先になるコマンド
ALL_ARG_WRITERS = {"tee"}
# 最終引数が書き込み先になるコマンド
LAST_ARG_WRITERS = {"cp", "mv", "install"}
# インプレース編集を行うコマンドと、そのフラグ
INPLACE_EDITORS = {"sed", "perl"}
INPLACE_FLAG = re.compile(r"^-[a-zA-Z]*i")
# 拒否理由に載せるコマンドの長さ
COMMAND_LABEL_LIMIT = 120


def split_segments(tokens: list[str]) -> tuple[list[list[str]], list[str]]:
    # トークンをコマンド単位に区切り、同時にリダイレクト先を集める
    segments: list[list[str]] = [[]]
    targets: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in COMMAND_SEPARATORS:
            segments.append([])
            index += 1
            continue
        if REDIRECT_TOKEN.match(token):
            if index + 1 < len(tokens):
                targets.append(tokens[index + 1])
            index += 2
            continue
        attached = REDIRECT_ATTACHED.match(token)
        if attached:
            targets.append(attached.group("target"))
            index += 1
            continue
        segments[-1].append(token)
        index += 1
    return segments, targets


def extract_write_targets(command: str) -> list[str]:
    # 完全な shell 構文解析は目指さない。リダイレクトと代表的な書き込みコマンドの引数だけを拾う
    segments, targets = split_segments(shlex.split(command))
    for segment in segments:
        if not segment:
            continue
        name = Path(segment[0]).name
        options = segment[1:]
        arguments = [token for token in options if not token.startswith("-")]
        if name in ALL_ARG_WRITERS:
            targets.extend(arguments)
        elif name in LAST_ARG_WRITERS and arguments:
            targets.append(arguments[-1])
        elif name in INPLACE_EDITORS and any(
            INPLACE_FLAG.match(token) for token in options
        ):
            targets.extend(arguments)
    return targets


def check_bash(command: str, project_dir: Path = PROJECT_DIR) -> str:
    # 拒否理由を返す。空文字なら許可
    for pattern, reason in DENY_BASH:
        if pattern.search(command):
            return reason
    try:
        targets = extract_write_targets(command)
    except ValueError:
        # 引用符が閉じていないなど分割できない入力は、書き込み先を確かめられないので拒否側に倒す
        return f"コマンドを解釈できないため拒否します: {command[:COMMAND_LABEL_LIMIT]}"
    for target in targets:
        reason = check_path(target, project_dir)
        if reason:
            return reason
    return ""


def path_forms(target: Path, project_dir: Path) -> list[str]:
    # symlink 越しの絶対パスも拾うため、resolve 前後それぞれをプロジェクト相対・ツールキット相対・ホーム相対・絶対で並べる
    bases = [project_dir, project_dir.resolve(), TOOL_DIR, TOOL_DIR.resolve(), Path.home()]
    forms: list[str] = []
    for candidate in (target, target.resolve()):
        for base in bases:
            if candidate.is_relative_to(base):
                forms.append(str(candidate.relative_to(base)))
        forms.append(str(candidate))
    return forms


def check_path(path: str, project_dir: Path = PROJECT_DIR) -> str:
    if not path:
        return ""
    target = Path(path).expanduser()
    if not target.is_absolute():
        target = project_dir / target
    if str(target).startswith(str(Path.home() / ".ssh")):
        return "~/.ssh 配下の編集は禁止"
    forms = [*path_forms(target, project_dir), target.name]
    for glob in PROTECTED_GLOBS:
        if any(fnmatch.fnmatch(form, glob) for form in forms):
            return f"保護対象のパスです: {path}"
    return ""


def lint_file(path: str) -> tuple[bool, str]:
    # Python ファイルだけ ruff にかける。ruff は uvx 経由で取得する
    if not path.endswith(".py") or not shutil.which("uvx"):
        return True, ""
    proc = run_cmd(["uvx", "ruff", "check", "--no-cache", path], timeout_sec=120)
    return proc.returncode == 0, tail(proc.stdout + proc.stderr, 3000)


def run_accept(commands: list[str], cwd: Path, timeout_sec: int) -> dict:
    # 受け入れコマンドを順に実行する。1 つでも落ちたら不合格
    results: list[dict] = []
    for command in commands:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        results.append(
            {
                "command": command,
                "code": proc.returncode,
                "output": tail(proc.stdout + proc.stderr, 3000),
            }
        )
    return {"passed": all(r["code"] == 0 for r in results), "results": results}


def list_changed_files(repo: Path, base_ref: str) -> list[str]:
    # 統合ブランチは並行タスクの完了で進むので、分岐点（merge-base）からの差分だけを見る
    base = (
        run_cmd(["git", "merge-base", base_ref, "HEAD"], cwd=repo).stdout.strip()
        or base_ref
    )
    tracked = run_cmd(["git", "diff", "--name-only", base], cwd=repo).stdout.split()
    untracked = run_cmd(
        ["git", "ls-files", "--others", "--exclude-standard"], cwd=repo
    ).stdout.split()
    return sorted(set(tracked) | set(untracked))


# scope 検査で無視する生成物（テスト実行や uv が作るもの。誰の責任でもない）
SCOPE_IGNORE_GLOBS = [
    "uv.lock",
    "*.pyc",
    "*/__pycache__/*",
    "__pycache__/*",
    ".venv/*",
    ".pytest_cache/*",
    ".ruff_cache/*",
    ".mypy_cache/*",
    "node_modules/*",
    ".agents/*",
]


def find_scope_violations(files: list[str], scope: list[str]) -> list[str]:
    # scope が空なら検査しない。生成物を除き、glob に 1 つも当たらないファイルが違反
    if not scope:
        return []
    candidates = [
        f for f in files if not any(fnmatch.fnmatch(f, g) for g in SCOPE_IGNORE_GLOBS)
    ]
    return [
        f for f in candidates if not any(fnmatch.fnmatch(f, glob) for glob in scope)
    ]


def format_feedback(
    exit_code: int, verify: dict, violations: list[str], review: str
) -> str:
    lines: list[str] = []
    if exit_code != 0:
        lines.append(f"- 実行プロセスが異常終了しました (exit={exit_code})")
    for result in verify.get("results", []):
        if result["code"] != 0:
            lines.append(
                f"- 受け入れコマンドが失敗: `{result['command']}` (exit={result['code']})\n```\n{result['output']}\n```"
            )
    if violations:
        lines.append(
            "- scope 外のファイルを変更しています。scope 内だけに収めるか、必要なら変更を戻してください:\n  "
            + "\n  ".join(violations)
        )
    if review:
        lines.append("- レビュアーの指摘:\n" + review)
    return "\n".join(lines)
