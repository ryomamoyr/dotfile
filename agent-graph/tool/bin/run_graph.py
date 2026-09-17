"""タスクグラフを実行するスケジューラ: worktree 隔離・受け入れ検証・レビュー・統合・承認ゲート・PR"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shlex
import shutil
import sys
import threading
import time
from pathlib import Path

from common import (
    EXAMPLE_TASKS_PATH,
    OUT_DIR,
    PROJECT_DIR,
    TOOL_DIR,
    WORKTREES_DIR,
    append_event,
    ensure_dirs,
    graph_dir,
    graph_state_path,
    load_json,
    locked_state,
    now_iso,
    resolve_session,
    run_cmd,
    tail,
    tasks_path,
)
from graph_model import (
    ACTIVE_STATES,
    CODEX_EXEC_FLAGS,
    EXECUTORS,
    TERMINAL_STATES,
    WAITING_STATES,
    is_blocked_by_failure,
    load_spec,
    ready_tasks,
    summarize,
    task_state,
    validate_spec,
)
from harness import (
    SCOPE_IGNORE_GLOBS,
    find_scope_violations,
    format_feedback,
    list_changed_files,
    run_accept,
)
from herdr_runner import HerdrRunner, LocalRunner, create_runner, write_job_script

# 受け入れ検証で使う形だけ通す。uv と uvx の全面許可はしない
UV_TOOLS = "Bash(uv run --project *),Bash(uv run --with pytest pytest *),Bash(uvx ruff *)"
CLAUDE_ALLOWED_TOOLS = f"Read,Write,Edit,Glob,Grep,{UV_TOOLS},Bash(git diff *),Bash(git status *),Bash(git log *)"
REVIEWER_ALLOWED_TOOLS = f"Read,Glob,Grep,{UV_TOOLS},Bash(git diff *),Bash(git log *)"
CLAUDE_MAX_TURNS = 60
# VERDICT は本文の最後の空でない行だけを採用する。本文中の言及を拾わない
VERDICT_LINE_PATTERN = re.compile(r"^VERDICT:\s*(approve|request_changes)\s*$", re.IGNORECASE)
DIFF_CHAR_LIMIT = 30000
POLL_SEC = 2
# timeout で終わった子・受け入れ検証の異常終了に使う終了コード
TIMEOUT_CODE = 124
# 統合 worktree は 1 つしかない。merge と worktree 追加を直列化する
INTEGRATION_LOCK = threading.RLock()

# 無人実行の claude 子に渡す native サンドボックス設定。strictAllowlist は入れない
# （許可外ドメインが必要になったとき無人実行が黙って止まるのを避けるため）
CHILD_SANDBOX_SETTINGS = {
    "sandbox": {
        "enabled": True,
        "allowUnsandboxedCommands": False,
        "filesystem": {"allowWrite": ["~/.cache/uv", "~/.npm"]},
        "network": {
            "allowedDomains": [
                "github.com",
                "registry.npmjs.org",
                "pypi.org",
                "files.pythonhosted.org",
            ],
            "allowMachLookup": True,
        },
        "credentials": {
            "files": [
                {"path": "~/.ssh", "mode": "deny"},
                {"path": "~/.aws/credentials", "mode": "deny"},
                {"path": "~/.netrc", "mode": "deny"},
            ]
        },
    }
}
# "off" にすると claude 子へのサンドボックス付与をやめる（逃げ道）
CHILD_SANDBOX_ENV = "AGENT_GRAPH_CHILD_SANDBOX"


# ---------- git ----------

def git(args: list[str], cwd: Path) -> tuple[int, str]:
    proc = run_cmd(["git", *args], cwd=cwd)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def current_branch(repo: Path) -> str:
    return git(["rev-parse", "--abbrev-ref", "HEAD"], repo)[1]


def branch_exists(repo: Path, branch: str) -> bool:
    return git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], repo)[0] == 0


def integration_branch(session: str) -> str:
    return f"agent/{session}/integration"


def task_branch(session: str, task_id: str) -> str:
    return f"agent/{session}/{task_id}"


class WorktreeError(RuntimeError):
    """worktree を作れなかった。呼び出し側がタスクを failed に落とす"""


def ensure_worktree(repo: Path, path: Path, branch: str, base: str) -> None:
    # 既にあれば再利用（再試行時に途中成果を残す）。無ければ base から新ブランチで作る
    with INTEGRATION_LOCK:
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        if branch_exists(repo, branch):
            code, output = git(["worktree", "add", str(path), branch], repo)
        else:
            code, output = git(["worktree", "add", "-b", branch, str(path), base], repo)
    if code != 0:
        raise WorktreeError(f"worktree を作れません ({branch}): {output}")


def prepare_integration(repo: Path, session: str, base_branch: str) -> Path:
    path = WORKTREES_DIR / session / "_integration"
    ensure_worktree(repo, path, integration_branch(session), base_branch)
    return path


# 実行時生成物だけを無視する。.agents 配下は state / out / tasks / worktrees に限る
AGENTS_RUNTIME_GLOBS = [".agents/state/*", ".agents/out/*", ".agents/tasks/*", ".agents/worktrees/*"]
COMMIT_IGNORE_GLOBS = [g for g in SCOPE_IGNORE_GLOBS if not g.startswith(".agents/")] + AGENTS_RUNTIME_GLOBS
# scope と outputs に 1 つも当たらなかったときの戻り値
COMMIT_NO_MATCH = "対象なし"


def changed_paths(worktree: Path) -> list[str]:
    tracked = run_cmd(["git", "diff", "--name-only", "HEAD"], cwd=worktree).stdout.splitlines()
    untracked = run_cmd(["git", "ls-files", "--others", "--exclude-standard"], cwd=worktree).stdout.splitlines()
    return sorted({line.strip() for line in tracked + untracked if line.strip()})


def path_matches(path: str, pattern: str) -> bool:
    # ディレクトリ指定は配下も対象にする
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern.rstrip("/") + "/*")


def select_commit_paths(paths: list[str], patterns: list[str]) -> list[str]:
    return [
        path
        for path in paths
        if not any(fnmatch.fnmatch(path, glob) for glob in COMMIT_IGNORE_GLOBS)
        and any(path_matches(path, pattern) for pattern in patterns)
    ]


def commit_patterns(task: dict) -> list[str]:
    return list(dict.fromkeys(task["scope"] + task["outputs"]))


def commit_all(worktree: Path, message: str, patterns: list[str]) -> str:
    # 統合に入れるのは scope と outputs に一致するものだけ。patterns が空なら従来どおり全体
    if not run_cmd(["git", "status", "--porcelain"], cwd=worktree).stdout.strip():
        return "変更なし"
    if patterns:
        selected = select_commit_paths(changed_paths(worktree), patterns)
        if not selected:
            return COMMIT_NO_MATCH
        git(["add", "--", *selected], worktree)
    else:
        git(["add", "-A"], worktree)
    if git(["diff", "--cached", "--quiet"], worktree)[0] == 0:
        return "変更なし"
    return git(["commit", "-q", "-m", message], worktree)[1] or "commit 済み"


def merge_into_integration(integration_wt: Path, branch: str) -> tuple[bool, str]:
    code, output = git(["merge", "--no-ff", "--no-edit", branch], integration_wt)
    if code != 0:
        git(["merge", "--abort"], integration_wt)
        return False, output
    return True, output


# ---------- 検証とレビューの判定 ----------

def safe_accept(commands: list[str], cwd: Path, timeout_sec: int) -> dict:
    # timeout を含む例外で受け入れ検証が落ちても、スレッドを殺さず不合格として扱う
    try:
        return run_accept(commands, cwd, timeout_sec)
    except Exception as error:  # noqa: BLE001
        return {
            "passed": False,
            "results": [{"command": "; ".join(commands), "code": TIMEOUT_CODE, "output": f"受け入れ検証が異常終了しました: {error!r}"}],
        }


def parse_verdict(text: str) -> str:
    # 最後の空でない行が VERDICT 行のときだけ採用する。該当しなければ空文字
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    match = VERDICT_LINE_PATTERN.match(lines[-1]) if lines else None
    return match.group(1).lower() if match else ""


# ---------- 状態更新 ----------

def update_state(session: str, task_id: str, **fields: object) -> dict:
    with locked_state(session) as state:
        current = task_state(state, task_id)
        current.update(fields)
        current["updated"] = now_iso()
        snapshot = dict(current)
    if "state" in fields or "note" in fields:
        append_event({"event": "task_state", "session": session, "task_id": task_id, **{k: v for k, v in fields.items() if k in ("state", "attempts", "executor", "branch")}})
        print(f"[{now_iso()}] {task_id}: {snapshot['state']}" + (f" ({fields['note']})" if "note" in fields else ""))
    return snapshot


def read_task_state(session: str, task_id: str) -> dict:
    with locked_state(session) as state:
        return dict(task_state(state, task_id))


# ---------- プロンプト ----------

def resolve_inputs(spec: dict, task: dict) -> list[str]:
    # 明示された inputs に加え、上流タスクの outputs を入力として渡す
    upstream = [p for dep in task["depends_on"] for p in spec["by_id"][dep]["outputs"]]
    return list(dict.fromkeys(task["inputs"] + upstream))


def build_task_prompt(spec: dict, task: dict, feedback: str, attempt: int) -> str:
    lines = [f"# タスク {task['id']}: {task['title']}", "", "## 目的", task["prompt"].strip(), ""]
    if spec["goal"]:
        lines += ["## 全体の目標（文脈）", spec["goal"].strip(), ""]
    if task["scope"]:
        lines += ["## 触ってよいファイル（scope）"] + [f"- {g}" for g in task["scope"]] + ["", "scope 外の変更は不合格になります。", ""]
    inputs = resolve_inputs(spec, task)
    if inputs:
        lines += ["## 上流からの入力（読んでから始める）"] + [f"- {p}" for p in inputs] + [""]
    if task["outputs"]:
        lines += ["## 期待する成果物"] + [f"- {p}" for p in task["outputs"]] + [""]
    if task["accept"]:
        lines += ["## 受け入れ条件（完了前に自分でも実行し、全て通すこと）"] + [f"- `{c}`" for c in task["accept"]] + [""]
    if feedback:
        lines += [f"## 前回の試行（{attempt - 1} 回目）で不合格になった理由", feedback, "", "上記を解消してください。", ""]
    lines += [
        "## 作業上の規則",
        "- この作業ディレクトリ内で完結させる。git commit / push はしない（スケジューラが行う）",
        "- コーディング規約は AGENTS.md に従う",
        "- 最後に「変更点の要約」と「受け入れコマンドの実行結果」を書く",
    ]
    return "\n".join(lines) + "\n"


def build_review_prompt(spec: dict, task: dict, diff: str, out_text: str) -> str:
    return "\n".join(
        [
            f"# レビュー対象: タスク {task['id']}: {task['title']}",
            "",
            "## タスクの目的",
            task["prompt"].strip(),
            "",
            "## 受け入れ条件",
            *[f"- `{c}`" for c in task["accept"]],
            "",
            "## scope",
            *[f"- {g}" for g in task["scope"]],
            "",
            "## 実装者の報告",
            out_text.strip() or "(報告なし)",
            "",
            "## 差分",
            "```diff",
            diff,
            "```",
            "",
            "手順: 差分を読み、受け入れコマンドを再実行し、AGENTS.md の規約と目的への適合を確認する。",
            "最終行に `VERDICT: approve` または `VERDICT: request_changes` を書く。request_changes なら修正指示を箇条書きで書く。",
        ]
    ) + "\n"


# ---------- 実行者ごとの起動スクリプト ----------

def child_env(session: str, task_id: str) -> str:
    # 子（worktree 内の claude / codex）の hooks が親リポジトリの状態ファイルに書けるようにする
    return (
        f"export AGENT_GRAPH_PROJECT={shlex.quote(str(PROJECT_DIR))}\n"
        f"export AGENT_GRAPH_PARENT_SESSION={shlex.quote(session)}\n"
        f"export AGENT_GRAPH_TASK={shlex.quote(task_id)}\n"
    )


def build_codex_body(session: str, task_id: str, worktree: Path, prompt: Path, out: Path, model: str) -> str:
    # model が空なら -m を付けず、Codex 側の既定（~/.codex/config.toml）に任せる
    model_flag = f"-m {shlex.quote(model)} " if model else ""
    return (
        child_env(session, task_id)
        + f"cd {shlex.quote(str(worktree))}\n"
        + f"codex exec {model_flag}--output-last-message {shlex.quote(str(out))} {CODEX_EXEC_FLAGS} "
        + f"- < {shlex.quote(str(prompt))}\n"
    )


def build_claude_body(
    session: str, task_id: str, worktree: Path, prompt: Path, out: Path, agent: str, allowed_tools: str, model: str = ""
) -> str:
    # model が空なら agents/<agent>.md の frontmatter の既定に任せる
    model_flag = f"--model {shlex.quote(model)} " if model else ""
    # 無人実行の子だけに native サンドボックスをかける。AGENT_GRAPH_CHILD_SANDBOX=off で外せる
    settings_flag = ""
    if os.environ.get(CHILD_SANDBOX_ENV) != "off":
        settings_flag = f"--settings {shlex.quote(json.dumps(CHILD_SANDBOX_SETTINGS))} "
    return (
        child_env(session, task_id)
        + f"cd {shlex.quote(str(worktree))}\n"
        + f"claude -p --agent {agent} {model_flag}{settings_flag}--output-format text --permission-mode acceptEdits "
        + f"--allowedTools {shlex.quote(allowed_tools)} --max-turns {CLAUDE_MAX_TURNS} "
        + f"< {shlex.quote(str(prompt))} > {shlex.quote(str(out))}\n"
    )


def tool_command(*args: str) -> str:
    # ~/.local/share/agent-graph の uv 環境で run_graph.py を呼ぶコマンド文字列
    script = TOOL_DIR / "bin" / "run_graph.py"
    return (
        f"cd {shlex.quote(str(PROJECT_DIR))} && "
        f"uv run --project {shlex.quote(str(TOOL_DIR))} python {shlex.quote(str(script))} "
        + " ".join(shlex.quote(a) for a in args)
    )


def build_gate_body(session: str, task_id: str) -> str:
    return tool_command("gate", task_id, "--session", session) + "\n"


# ---------- 1 タスクの実行 ----------

class Scheduler:
    def __init__(self, session: str, spec: dict, repo: Path, runner: HerdrRunner | LocalRunner, base_branch: str, keep_done: bool) -> None:
        self.keep_done = keep_done
        self.session = session
        self.spec = spec
        self.repo = repo
        self.runner = runner
        self.base_branch = base_branch
        self.integration_wt = prepare_integration(repo, session, base_branch)
        self.threads: dict[str, threading.Thread] = {}

    # --- 起動 ---

    def dispatch(self, task: dict) -> None:
        kind = EXECUTORS[self.effective_executor(task)]["kind"]
        target = {"human": self.run_gate, "pr": self.run_pr}.get(kind, self.run_task)
        thread = threading.Thread(target=target, args=(task,), name=task["id"], daemon=True)
        self.threads[task["id"]] = thread
        thread.start()

    def resume_waiting(self, task: dict) -> None:
        thread = threading.Thread(target=self.wait_human, args=(task,), name=task["id"], daemon=True)
        self.threads[task["id"]] = thread
        thread.start()

    def active_ids(self) -> set[str]:
        return {tid for tid, th in self.threads.items() if th.is_alive()}

    def effective_executor(self, task: dict) -> str:
        return read_task_state(self.session, task["id"]).get("executor") or task["executor"]

    # --- 実装タスク ---

    def run_task(self, task: dict) -> None:
        # スレッドが黙って死ぬとタスクが verifying のまま固まる。想定外の例外はここで failed にする
        try:
            self.execute_task(task)
        except Exception as error:  # noqa: BLE001
            update_state(
                self.session,
                task["id"],
                state="failed",
                ended=now_iso(),
                feedback=f"スケジューラが例外で停止しました: {error!r}",
                note="想定外の例外",
            )

    def execute_task(self, task: dict) -> None:
        tid = task["id"]
        executor_name = self.effective_executor(task)
        executor = EXECUTORS[executor_name]
        previous = read_task_state(self.session, tid)
        attempt = previous["attempts"] + 1
        feedback = previous.get("feedback", "")

        branch = task_branch(self.session, tid)
        worktree = WORKTREES_DIR / self.session / tid
        ensure_worktree(self.repo, worktree, branch, integration_branch(self.session))

        out_dir = OUT_DIR / self.session
        out_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = out_dir / f"{tid}.attempt{attempt}.prompt.md"
        prompt_path.write_text(build_task_prompt(self.spec, task, feedback, attempt), encoding="utf-8")
        out_path = out_dir / f"{tid}.attempt{attempt}.md"

        # 昇格後は state の model を使う。kind をまたぐ昇格では handle_failure が空に戻している
        requested = previous.get("model", "") if previous.get("escalated") else task["model"]
        model = requested or executor["model"]
        if executor["kind"] == "codex":
            body = build_codex_body(self.session, tid, worktree, prompt_path, out_path, model)
        else:
            body = build_claude_body(self.session, tid, worktree, prompt_path, out_path, executor["agent"], CLAUDE_ALLOWED_TOOLS, requested)
        script = write_job_script(self.session, f"{tid}-a{attempt}", body)
        node_id = f"{tid}-a{attempt}"

        update_state(self.session, tid, state="running", attempts=attempt, executor=executor_name, model=model, branch=branch, worktree=str(worktree), prompt=str(prompt_path), started=now_iso())
        handle = self.runner.start(self.session, node_id, f"{self.session}/{tid}", script, worktree)
        update_state(self.session, tid, pane=handle)

        finished = self.runner.wait(handle, node_id, task["timeout_sec"])
        if not finished:
            # 次の試行が始まる前に子を確実に終わらせる
            self.runner.close(handle)
            self.runner.terminate(handle)
        exit_code = self.runner.exit_code(handle, node_id) if finished else TIMEOUT_CODE
        out_text = out_path.read_text(encoding="utf-8") if out_path.exists() else ""

        update_state(self.session, tid, state="verifying")
        # 変更ファイルは受け入れコマンドを走らせる前に取る（テスト実行が作る生成物を実行者の責任にしない）
        violations = find_scope_violations(list_changed_files(worktree, integration_branch(self.session)), task["scope"])
        verify = safe_accept(task["accept"], worktree, task["timeout_sec"])
        append_event({"event": "task_verify", "session": self.session, "task_id": tid, "attempt": attempt, "passed": verify["passed"] and not violations and exit_code == 0, "exit_code": exit_code, "violations": violations})
        update_state(self.session, tid, verify=verify, violations=violations, exit_code=exit_code, output=tail(out_text, 6000))

        if exit_code != 0 or not verify["passed"] or violations:
            self.handle_failure(task, format_feedback(exit_code, verify, violations, ""))
            return

        review_text = ""
        if task["review"]:
            update_state(self.session, tid, state="reviewing")
            verdict, review_text = self.run_review(task, worktree, out_text, attempt)
            update_state(self.session, tid, review={"verdict": verdict, "text": tail(review_text, 6000)})
            if verdict != "approve":
                self.handle_failure(task, format_feedback(0, {"results": []}, [], review_text))
                return

        self.integrate(task, worktree, branch)

    def run_review(self, task: dict, worktree: Path, out_text: str, attempt: int) -> tuple[str, str]:
        # 作った者と別のモデル（Claude reviewer）が差分を検証する
        tid = task["id"]
        commit_all(worktree, f"agent({tid}): 検証前スナップショット", commit_patterns(task))
        diff = git(["diff", f"{integration_branch(self.session)}...HEAD"], worktree)[1]
        diff = diff if len(diff) <= DIFF_CHAR_LIMIT else diff[:DIFF_CHAR_LIMIT] + "\n…(以降省略)"
        out_dir = OUT_DIR / self.session
        prompt_path = out_dir / f"{tid}.attempt{attempt}.review-prompt.md"
        prompt_path.write_text(build_review_prompt(self.spec, task, diff, out_text), encoding="utf-8")
        review_path = out_dir / f"{tid}.attempt{attempt}.review.md"
        node_id = f"{tid}-a{attempt}-review"
        body = build_claude_body(self.session, tid, worktree, prompt_path, review_path, EXECUTORS["reviewer"]["agent"], REVIEWER_ALLOWED_TOOLS, task["review_model"])
        script = write_job_script(self.session, node_id, body)
        handle = self.runner.start(self.session, node_id, f"{self.session}/{tid} review", script, worktree)
        finished = self.runner.wait(handle, node_id, task["timeout_sec"])
        self.runner.close(handle)
        if not finished:
            self.runner.terminate(handle)
        text = review_path.read_text(encoding="utf-8") if review_path.exists() else ""
        verdict = parse_verdict(text) if finished else ""
        if not verdict:
            text += "\n(最終行に VERDICT が無いため request_changes 扱い)"
        return verdict or "request_changes", text

    def integrate(self, task: dict, worktree: Path, branch: str) -> None:
        tid = task["id"]
        update_state(self.session, tid, state="merging")
        # 統合 worktree は 1 つ。commit と merge を直列化して index.lock 衝突と巻き戻しを防ぐ
        with INTEGRATION_LOCK:
            committed = commit_all(worktree, f"agent({tid}): {task['title']}", commit_patterns(task))
            if committed == COMMIT_NO_MATCH:
                # 変更はあるのに scope と outputs のどれにも当たらない。黙って done にせず人に返す
                update_state(
                    self.session,
                    tid,
                    state="failed",
                    ended=now_iso(),
                    feedback="変更が scope と outputs のどれにも一致せず統合できません:\n  " + "\n  ".join(changed_paths(worktree)),
                    note="統合対象なし",
                )
                return
            merged, output = merge_into_integration(self.integration_wt, branch)
        if not merged:
            update_state(self.session, tid, state="conflict", feedback=f"統合ブランチへのマージで競合:\n{output}", note="人の判断待ち")
            self.wait_human(task)
            return
        update_state(self.session, tid, state="done", ended=now_iso(), feedback="")
        if not self.keep_done:
            self.runner.close(read_task_state(self.session, tid).get("pane", ""))

    # --- 失敗・再試行・昇格 ---

    def handle_failure(self, task: dict, feedback: str) -> None:
        tid = task["id"]
        current = read_task_state(self.session, tid)
        retry = task["retry"]
        if current["attempts"] <= retry["max"]:
            update_state(self.session, tid, state="planned", feedback=feedback, note=f"再試行 {current['attempts']}/{retry['max']}")
            return
        escalate_to = retry["escalate_to"]
        if escalate_to != "human" and not current.get("escalated"):
            fields: dict[str, object] = {"state": "planned", "executor": escalate_to, "escalated": True, "feedback": feedback}
            # 実行者の系統が変わるなら model は引き継がない。codex の model id は claude で即死する
            previous_executor = current.get("executor") or task["executor"]
            if EXECUTORS[escalate_to]["kind"] != EXECUTORS[previous_executor]["kind"]:
                fields["model"] = ""
            update_state(self.session, tid, **fields, note=f"{escalate_to} に昇格")
            return
        update_state(self.session, tid, state="waiting_human", feedback=feedback, note="再試行上限。人の判断待ち")
        self.wait_human(task)

    # --- 人の判断 ---

    def run_gate(self, task: dict) -> None:
        update_state(self.session, task["id"], state="waiting_human", note="承認ゲート")
        self.wait_human(task)

    def wait_human(self, task: dict) -> None:
        tid = task["id"]
        if isinstance(self.runner, HerdrRunner):
            script = write_job_script(self.session, f"{tid}-gate", build_gate_body(self.session, tid))
            worktree = WORKTREES_DIR / self.session / tid
            self.runner.start(self.session, f"{tid}-gate", f"{self.session}/{tid} gate", script, worktree if worktree.exists() else PROJECT_DIR)
        else:
            print(f"  → 判断待ち: agr approve|retry|reject {tid} --session {self.session}")
        while True:
            with locked_state(self.session) as state:
                current = task_state(state, tid)
                decision = current.pop("decision", "")
            if decision:
                break
            time.sleep(POLL_SEC)
        self.apply_decision(task, decision)

    def apply_decision(self, task: dict, decision: str) -> None:
        tid = task["id"]
        kind = EXECUTORS[task["executor"]]["kind"]
        if decision == "approve":
            if kind == "human":
                update_state(self.session, tid, state="done", ended=now_iso())
                return
            worktree = WORKTREES_DIR / self.session / tid
            if worktree.exists():
                self.integrate(task, worktree, task_branch(self.session, tid))
            else:
                update_state(self.session, tid, state="done", ended=now_iso())
        elif decision == "retry":
            # 昇格の結果は巻き戻さない。試行回数だけ戻す
            update_state(self.session, tid, state="planned", attempts=0, note="人の指示で再試行")
        else:
            update_state(self.session, tid, state="rejected", ended=now_iso(), note="人が却下")

    # --- PR ---

    def run_pr(self, task: dict) -> None:
        tid = task["id"]
        update_state(self.session, tid, state="running", attempts=1, executor="pr")
        report_path = write_report(self.session, self.spec)
        branch = integration_branch(self.session)
        if not shutil.which("gh"):
            update_state(self.session, tid, state="failed", feedback="gh が見つかりません。手動で PR を作成してください", output=str(report_path))
            return
        code, output = git(["push", "-u", "origin", branch], self.integration_wt)
        if code != 0:
            update_state(self.session, tid, state="failed", feedback=f"push 失敗:\n{output}")
            return
        title = f"[agent {self.session}] {self.spec['goal'].strip().splitlines()[0] if self.spec['goal'] else task['title']}"
        proc = run_cmd(["gh", "pr", "create", "--base", self.base_branch, "--head", branch, "--title", title, "--body-file", str(report_path)], cwd=self.repo)
        if proc.returncode != 0:
            update_state(self.session, tid, state="failed", feedback=f"gh pr create 失敗:\n{proc.stdout}{proc.stderr}")
            return
        update_state(self.session, tid, state="done", ended=now_iso(), output=proc.stdout.strip(), pr_url=proc.stdout.strip())


# ---------- レポート ----------

def write_report(session: str, spec: dict) -> Path:
    state = load_json(graph_state_path(session), {})
    lines = [f"# {session}: {spec['goal'].strip() or '実行レポート'}", "", "| タスク | 実行者 | 状態 | 試行 | 検証 |", "| --- | --- | --- | --- | --- |"]
    for task in spec["tasks"]:
        current = state.get(task["id"], {})
        verify = current.get("verify", {})
        passed = "合格" if verify.get("passed") and not current.get("violations") else ("-" if not verify else "不合格")
        lines.append(f"| {task['id']} {task['title']} | {current.get('executor') or task['executor']} | {current.get('state', 'planned')} | {current.get('attempts', 0)} | {passed} |")
    lines += ["", "## 各タスクの報告"]
    for task in spec["tasks"]:
        output = state.get(task["id"], {}).get("output", "")
        if output:
            lines += [f"### {task['id']} {task['title']}", "", output.strip(), ""]
    path = graph_dir(session) / "report.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# ---------- スケジューラ本体 ----------

def reconcile_stale(session: str, spec: dict) -> None:
    # 前回の run が途中で落ちた場合、実行中だった状態を planned に戻して再投入できるようにする
    with locked_state(session) as state:
        for task in spec["tasks"]:
            current = task_state(state, task["id"])
            if current["state"] in ACTIVE_STATES:
                current["state"] = "planned"
                current["updated"] = now_iso()


def run(args: argparse.Namespace) -> None:
    ensure_dirs()
    session = resolve_session(args.session)
    spec = load_spec(session)
    errors = validate_spec(spec)
    if errors:
        sys.exit("tasks.yaml が不正です:\n- " + "\n- ".join(errors))
    repo = PROJECT_DIR
    base_branch = spec["base_branch"] or current_branch(repo)
    with locked_state(session) as state:
        state.setdefault("_meta", {})["base_branch"] = base_branch
        state["_meta"]["goal"] = spec["goal"]
    reconcile_stale(session, spec)
    try:
        scheduler = Scheduler(session, spec, repo, create_runner(args.pane, args.direction), base_branch, args.keep_done)
    except WorktreeError as error:
        sys.exit(str(error))
    append_event({"event": "graph_run", "session": session, "goal": spec["goal"], "tasks": len(spec["tasks"])})
    print(f"[agent-graph] {session}: {len(spec['tasks'])} タスク、統合ブランチ {integration_branch(session)}（base: {base_branch}）")

    deadline = time.monotonic() + args.budget_min * 60
    while True:
        with locked_state(session) as state:
            snapshot = json.loads(json.dumps(state))
        states = {t["id"]: snapshot.get(t["id"], {}).get("state", "planned") for t in spec["tasks"]}
        if all(s in TERMINAL_STATES for s in states.values()):
            break
        active = scheduler.active_ids()
        for task in spec["tasks"]:
            if states[task["id"]] in WAITING_STATES and task["id"] not in active:
                scheduler.resume_waiting(task)
        active = scheduler.active_ids()
        if time.monotonic() > deadline:
            if not active:
                print("[agent-graph] 時間予算を使い切りました。再度 run すると続きから実行します")
                break
            # 判断待ちのスレッドしか残っていないなら、人を待たずに終える
            waiting = {t["id"] for t in spec["tasks"] if states[t["id"]] in WAITING_STATES}
            if active <= waiting:
                print("[agent-graph] 時間予算を使い切りました。判断待ちを残して終了します: " + ", ".join(sorted(active)))
                break
            time.sleep(POLL_SEC)
            continue
        ready = [t for t in ready_tasks(spec, snapshot) if t["id"] not in active]
        for task in ready[: max(0, args.max_parallel - len(active))]:
            scheduler.dispatch(task)
        if not active and not ready and not scheduler.active_ids():
            stuck = [t["id"] for t in spec["tasks"] if states[t["id"]] == "planned" and is_blocked_by_failure(t, snapshot)]
            print("[agent-graph] 進行できるタスクがありません。上流の失敗で止まっているタスク: " + (", ".join(stuck) or "なし"))
            break
        time.sleep(POLL_SEC)

    report = write_report(session, spec)
    print(f"[agent-graph] {session} 終了: {summarize(spec, snapshot)}  レポート: {report}")


# ---------- CLI ----------

def cmd_init(args: argparse.Namespace) -> None:
    # 雛形を <repo>/.agents/graph/<session>/tasks.yaml に置く（既にあれば触らない）
    ensure_dirs()
    session = resolve_session(args.session)
    target = tasks_path(session)
    if target.exists():
        sys.exit(f"既にあります: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(EXAMPLE_TASKS_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"雛形を置きました: {target}")


def cmd_validate(args: argparse.Namespace) -> None:
    session = resolve_session(args.session)
    errors = validate_spec(load_spec(session))
    if errors:
        sys.exit("NG:\n- " + "\n- ".join(errors))
    print(f"OK: {session} の tasks.yaml は有効です")


def cmd_status(args: argparse.Namespace) -> None:
    session = resolve_session(args.session)
    spec = load_spec(session)
    with locked_state(session) as state:
        snapshot = json.loads(json.dumps(state))
    print(f"{'id':<10} {'状態':<14} {'試行':<4} {'実行者':<10} 題名")
    for task in spec["tasks"]:
        current = snapshot.get(task["id"], {})
        print(f"{task['id']:<10} {current.get('state', 'planned'):<14} {current.get('attempts', 0):<4} {(current.get('executor') or task['executor']):<10} {task['title']}")
        if current.get("state") in WAITING_STATES and current.get("feedback"):
            print("           理由: " + current["feedback"].strip().splitlines()[0])


def set_decision(args: argparse.Namespace, decision: str) -> None:
    session = resolve_session(args.session)
    with locked_state(session) as state:
        current = task_state(state, args.task_id)
        if current["state"] not in WAITING_STATES:
            sys.exit(f"{args.task_id} は判断待ちではありません（現在: {current['state']}）")
        current["decision"] = decision
    print(f"{args.task_id}: {decision} を記録しました。スケジューラが反映します")


def cmd_gate(args: argparse.Namespace) -> None:
    # herdr の pane で人が答える対話。herdr には blocked として見える
    session = resolve_session(args.session)
    spec = load_spec(session)
    task = spec["by_id"][args.task_id]
    current = read_task_state(session, args.task_id)
    print(f"=== 判断待ち: {session}/{task['id']} {task['title']} ===")
    print(task["prompt"].strip())
    if current.get("feedback"):
        print("\n--- 理由 ---\n" + current["feedback"].strip())
    if current.get("worktree"):
        print(f"\nworktree: {current['worktree']}  branch: {current.get('branch', '')}")
    answer = ""
    while answer not in ("a", "r", "x"):
        answer = input("\n[a] 承認して統合  [r] 再試行  [x] 却下 > ").strip().lower()
    with locked_state(session) as state:
        task_state(state, args.task_id)["decision"] = {"a": "approve", "r": "retry", "x": "reject"}[answer]
    print("記録しました。この pane は閉じて構いません")


def cmd_launch(args: argparse.Namespace) -> None:
    # run を herdr の pane で起動し、Fable の Bash ツールを塞がない
    session = resolve_session(args.session)
    runner = create_runner(args.pane, args.direction)
    extra = ["--pane", args.pane] if args.pane else []
    extra += ["--keep-done"] if args.keep_done else []
    body = tool_command("run", "--session", session, "--max-parallel", str(args.max_parallel), "--budget-min", str(args.budget_min), *extra) + "\n"
    handle = runner.start(session, "scheduler", f"{session}/scheduler", write_job_script(session, "scheduler", body), PROJECT_DIR)
    print(f"[agent-graph] スケジューラを起動しました: {handle}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="タスクグラフを実行する")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--session", help="セッション識別子（省略時は現在のセッション）")

    for name, helptext in (("init", "tasks.yaml の雛形を置く"), ("validate", "tasks.yaml を検証"), ("status", "状態を表示")):
        add_common(sub.add_parser(name, help=helptext))

    for name in ("run", "launch"):
        p = sub.add_parser(name, help="グラフを実行" if name == "run" else "run を herdr の pane で起動")
        add_common(p)
        p.add_argument("--max-parallel", type=int, default=3)
        p.add_argument("--budget-min", type=int, default=120, help="この時間を超えたら新規投入を止める")
        p.add_argument("--pane", help="split モードでの分割元 pane id")
        p.add_argument("--direction", default="right", choices=["right", "down"])
        p.add_argument("--keep-done", action="store_true", help="完了したタスクの tab / pane を閉じない")

    for name in ("approve", "retry", "reject", "gate"):
        p = sub.add_parser(name, help=f"判断待ちタスクに {name}")
        add_common(p)
        p.add_argument("task_id")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    commands = {
        "init": cmd_init,
        "validate": cmd_validate,
        "status": cmd_status,
        "run": run,
        "launch": cmd_launch,
        "gate": cmd_gate,
        "approve": lambda a: set_decision(a, "approve"),
        "retry": lambda a: set_decision(a, "retry"),
        "reject": lambda a: set_decision(a, "reject"),
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
