"""スケジューラの回帰テスト: pr の検証、VERDICT の判定、統合に入れる範囲、状態ファイルの原子性、昇格と再試行"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

import pytest
import yaml

BIN_DIR = Path(__file__).resolve().parent.parent / "bin"
if str(BIN_DIR) not in sys.path:
    sys.path.insert(0, str(BIN_DIR))

import common
import graph_model
import run_graph

SESSION = "test-001"
# 原子性テストの規模: 書き込み回数と 1 件あたりの詰め物の長さ
ATOMIC_WRITES = 200
ATOMIC_PADDING = 4000
# 採番テストの規模: スレッド数と 1 スレッドあたりの採番回数
COUNTER_THREADS = 8
COUNTER_STEPS = 20
JOIN_SEC = 30

CODE_TASK = {
    "id": "T1",
    "title": "実装",
    "executor": "codex",
    "scope": ["src/*"],
    "accept": ["true"],
    "prompt": "何か書く",
}


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    # 実データを触らないよう、状態と tasks.yaml の置き場を一時ディレクトリに向ける
    state = tmp_path / "state"
    monkeypatch.setattr(common, "STATE_DIR", state)
    monkeypatch.setattr(common, "GRAPH_DIR", tmp_path / "graph")
    monkeypatch.setattr(common, "TASKS_DIR", tmp_path / "tasks")
    monkeypatch.setattr(common, "OUT_DIR", tmp_path / "out")
    monkeypatch.setattr(common, "WORKTREES_DIR", tmp_path / "worktrees")
    monkeypatch.setattr(common, "EVENTS_PATH", state / "events.jsonl")
    monkeypatch.setattr(common, "EVENTS_LOCK_PATH", state / "events.lock")
    monkeypatch.setattr(common, "ensure_git_exclude", lambda: None)
    monkeypatch.setattr(run_graph, "WORKTREES_DIR", tmp_path / "worktrees")
    state.mkdir(parents=True)
    return tmp_path


def write_spec(root: Path, tasks: list[dict]) -> dict:
    path = root / "graph" / SESSION / "tasks.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"goal": "テスト", "tasks": tasks}, allow_unicode=True), encoding="utf-8")
    return graph_model.load_spec(SESSION)


def make_scheduler(spec: dict) -> run_graph.Scheduler:
    # __init__ は worktree を作るので、状態遷移の検証には属性だけ組み立てた実体を使う
    scheduler = run_graph.Scheduler.__new__(run_graph.Scheduler)
    scheduler.session = SESSION
    scheduler.spec = spec
    scheduler.repo = Path.cwd()
    scheduler.runner = None
    scheduler.base_branch = "main"
    scheduler.keep_done = True
    scheduler.threads = {}
    return scheduler


def set_task_state(task_id: str, **fields: object) -> None:
    with common.locked_state(SESSION) as state:
        graph_model.task_state(state, task_id).update(fields)


def run_git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    run_git(["init", "-q"], root)
    run_git(["config", "user.email", "test@example.com"], root)
    run_git(["config", "user.name", "test"], root)
    (root / "README.md").write_text("初期\n", encoding="utf-8")
    run_git(["add", "README.md"], root)
    run_git(["commit", "-q", "-m", "初期コミット"], root)
    return root


def committed_files(repo_path: Path) -> list[str]:
    return sorted(run_git(["show", "--name-only", "--pretty=format:", "HEAD"], repo_path).split())


# ---------- pr タスクの検証 ----------

def test_pr_without_human_gate_is_error(isolated_state):
    spec = write_spec(isolated_state, [CODE_TASK, {"id": "PR", "title": "PR を作成", "executor": "pr", "depends_on": ["T1"]}])
    errors = graph_model.validate_spec(spec)
    assert [e for e in errors if "human" in e]


def test_pr_behind_human_gate_passes(isolated_state):
    spec = write_spec(
        isolated_state,
        [
            CODE_TASK,
            {"id": "G1", "title": "最終確認", "executor": "human", "depends_on": ["T1"]},
            {"id": "PR", "title": "PR を作成", "executor": "pr", "depends_on": ["G1"]},
        ],
    )
    assert graph_model.validate_spec(spec) == []


def test_example_tasks_pass_validation(isolated_state):
    raw = yaml.safe_load(common.EXAMPLE_TASKS_PATH.read_text(encoding="utf-8"))
    spec = write_spec(isolated_state, raw["tasks"])
    assert graph_model.validate_spec(spec) == []


# ---------- VERDICT の判定 ----------

def test_verdict_uses_last_line_only():
    text = "差分を読んだ。ここで VERDICT: approve と書いても本文なので拾わない。\n\nVERDICT: request_changes\n"
    assert run_graph.parse_verdict(text) == "request_changes"


def test_verdict_approve_on_last_line():
    assert run_graph.parse_verdict("問題なし\n\nVERDICT: approve\n") == "approve"


def test_verdict_missing_is_empty():
    assert run_graph.parse_verdict("VERDICT: approve\nただし後書きを足した") == ""
    assert run_graph.parse_verdict("判定を書き忘れた\n") == ""
    assert run_graph.parse_verdict("") == ""


# ---------- 統合に入れるファイル ----------

def test_commit_all_skips_out_of_scope(repo):
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "other").mkdir()
    (repo / "other" / "b.py").write_text("y = 2\n", encoding="utf-8")
    (repo / "README.md").write_text("書き換え\n", encoding="utf-8")
    run_graph.commit_all(repo, "agent(T1): 実装", ["src/*", "docs/out.md"])
    assert committed_files(repo) == ["src/a.py"]
    assert "other/b.py" in run_git(["status", "--porcelain", "-uall"], repo)


def test_commit_all_skips_generated_files(repo):
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "src" / "__pycache__").mkdir()
    (repo / "src" / "__pycache__" / "a.pyc").write_text("生成物\n", encoding="utf-8")
    run_graph.commit_all(repo, "agent(T1): 実装", ["src/**"])
    assert committed_files(repo) == ["src/a.py"]


def test_commit_all_without_scope_adds_everything(repo):
    (repo / "free.txt").write_text("scope 無し\n", encoding="utf-8")
    run_graph.commit_all(repo, "agent(D1): 文書", [])
    assert committed_files(repo) == ["free.txt"]


def test_commit_all_adds_agents_scope(repo):
    # 実行時生成物でない .agents 配下は統合に入れる
    target = repo / ".agents" / "graph" / "examples"
    target.mkdir(parents=True)
    (target / "sample.yaml").write_text("goal: 例\n", encoding="utf-8")
    (repo / ".agents" / "state").mkdir()
    (repo / ".agents" / "state" / "events.jsonl").write_text("{}\n", encoding="utf-8")
    run_graph.commit_all(repo, "agent(T1): 例を追加", [".agents/graph/examples/*.yaml"])
    assert committed_files(repo) == [".agents/graph/examples/sample.yaml"]


def test_commit_all_without_match_makes_no_commit(repo):
    before = run_git(["rev-parse", "HEAD"], repo)
    (repo / "other.txt").write_text("対象外\n", encoding="utf-8")
    assert run_graph.commit_all(repo, "agent(T1): 実装", ["src/*"]) == run_graph.COMMIT_NO_MATCH
    assert run_git(["rev-parse", "HEAD"], repo) == before


def test_integrate_fails_when_nothing_matches(isolated_state, repo):
    # scope 外の変更しかないまま done にすると成果が消える
    spec = write_spec(isolated_state, [CODE_TASK])
    scheduler = make_scheduler(spec)
    scheduler.integration_wt = repo
    (repo / "other.txt").write_text("対象外\n", encoding="utf-8")
    scheduler.integrate(spec["by_id"]["T1"], repo, "agent/test/T1")
    current = run_graph.read_task_state(SESSION, "T1")
    assert current["state"] == "failed"
    assert "other.txt" in current["feedback"]


# ---------- 状態ファイルの原子性 ----------

def test_save_json_is_always_valid(tmp_path):
    path = tmp_path / "state.json"
    common.save_json(path, {"n": -1})
    done = threading.Event()
    broken: list[str] = []

    def write_many() -> None:
        for index in range(ATOMIC_WRITES):
            common.save_json(path, {"n": index, "pad": "あ" * ATOMIC_PADDING})
        done.set()

    writer = threading.Thread(target=write_many)
    writer.start()
    reads = 0
    while not done.is_set():
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError) as error:
            broken.append(repr(error))
        reads += 1
    writer.join(timeout=JOIN_SEC)
    assert not writer.is_alive()
    assert reads > 0
    assert broken == []
    assert json.loads(path.read_text(encoding="utf-8"))["n"] == ATOMIC_WRITES - 1


def test_next_counter_does_not_duplicate(tmp_path):
    path = tmp_path / "counter"
    values: list[int] = []
    lock = threading.Lock()

    def count_many() -> None:
        for _ in range(COUNTER_STEPS):
            value = common.next_counter(path)
            with lock:
                values.append(value)

    threads = [threading.Thread(target=count_many) for _ in range(COUNTER_THREADS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=JOIN_SEC)
    assert sorted(values) == list(range(1, COUNTER_THREADS * COUNTER_STEPS + 1))


# ---------- 昇格と人の再試行 ----------

def test_escalation_across_kinds_clears_model(isolated_state):
    task = {**CODE_TASK, "model": "gpt-5.5", "retry": {"max": 0, "escalate_to": "doc-heavy"}}
    spec = write_spec(isolated_state, [task])
    scheduler = make_scheduler(spec)
    set_task_state("T1", attempts=1, executor="codex", model="gpt-5.5")
    scheduler.handle_failure(spec["by_id"]["T1"], "受け入れ不合格")
    current = run_graph.read_task_state(SESSION, "T1")
    assert current["state"] == "planned"
    assert current["executor"] == "doc-heavy"
    assert current["escalated"] is True
    assert current["model"] == ""


def test_escalation_within_kind_keeps_model(isolated_state):
    task = {**CODE_TASK, "executor": "doc-light", "retry": {"max": 0, "escalate_to": "doc-heavy"}}
    spec = write_spec(isolated_state, [task])
    scheduler = make_scheduler(spec)
    set_task_state("T1", attempts=1, executor="doc-light", model="sonnet")
    scheduler.handle_failure(spec["by_id"]["T1"], "受け入れ不合格")
    current = run_graph.read_task_state(SESSION, "T1")
    assert current["executor"] == "doc-heavy"
    assert current["model"] == "sonnet"


def test_human_retry_keeps_escalation(isolated_state):
    spec = write_spec(isolated_state, [CODE_TASK])
    scheduler = make_scheduler(spec)
    set_task_state("T1", state="waiting_human", attempts=3, executor="doc-heavy", escalated=True, model="")
    scheduler.apply_decision(spec["by_id"]["T1"], "retry")
    current = run_graph.read_task_state(SESSION, "T1")
    assert current["state"] == "planned"
    assert current["attempts"] == 0
    assert current["executor"] == "doc-heavy"
    assert current["escalated"] is True


# ---------- 失敗経路 ----------

def test_safe_accept_turns_timeout_into_failure():
    verify = run_graph.safe_accept(["sleep 5"], Path.cwd(), 1)
    assert verify["passed"] is False
    assert verify["results"][0]["code"] == run_graph.TIMEOUT_CODE


def test_ensure_worktree_raises_on_failure(tmp_path):
    with pytest.raises(run_graph.WorktreeError):
        run_graph.ensure_worktree(tmp_path, tmp_path / "wt", "agent/test/T1", "存在しない基点")
