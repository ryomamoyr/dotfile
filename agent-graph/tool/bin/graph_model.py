"""タスクグラフ (tasks.yaml) の読み込み・検証・実行状態の定義"""

from __future__ import annotations

import re

import yaml

from common import tasks_path

# 状態遷移: planned → running → verifying → reviewing → done
#                          ↘ failed / conflict / waiting_human（人の判断待ち）
TERMINAL_STATES = {"done", "failed", "rejected"}
WAITING_STATES = {"waiting_human", "conflict"}
ACTIVE_STATES = {"running", "verifying", "reviewing", "merging"}

# codex exec の共通フラグ。旧 --full-auto は codex-cli 0.153 で廃止、--sandbox workspace-write が後継
CODEX_EXEC_FLAGS = "--sandbox workspace-write --skip-git-repo-check"

# 実行者の定義。kind が起動方法、model は表示用
EXECUTORS: dict[str, dict] = {
    "codex": {"kind": "codex", "model": "gpt-6-astra", "review": True},
    "doc-light": {
        "kind": "claude",
        "agent": "doc-light",
        "model": "haiku",
        "review": False,
    },
    "doc-heavy": {
        "kind": "claude",
        "agent": "doc-heavy",
        "model": "sonnet",
        "review": False,
    },
    "reviewer": {
        "kind": "claude",
        "agent": "reviewer",
        "model": "sonnet",
        "review": False,
    },
    "human": {"kind": "human", "model": "", "review": False},
    "pr": {"kind": "pr", "model": "", "review": False},
}
PLANNABLE_EXECUTORS = [name for name in EXECUTORS if name != "reviewer"]
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def normalize_task(raw: dict) -> dict:
    executor = raw.get("executor", "codex")
    retry = {"max": 1, "escalate_to": "human", **raw.get("retry", {})}
    return {
        "id": str(raw.get("id", "")),
        "title": raw.get("title", ""),
        "executor": executor,
        "depends_on": [str(d) for d in raw.get("depends_on", [])],
        "scope": list(raw.get("scope", [])),
        "inputs": list(raw.get("inputs", [])),
        "outputs": list(raw.get("outputs", [])),
        "accept": list(raw.get("accept", [])),
        "prompt": raw.get("prompt", ""),
        "review": raw.get("review", EXECUTORS.get(executor, {}).get("review", False)),
        # モデルはオーケストレーターがタスクの難易度で選ぶ。空なら実行者の既定
        "model": str(raw.get("model") or ""),
        "review_model": str(raw.get("review_model") or ""),
        "retry": retry,
        "timeout_sec": int(raw.get("timeout_sec", 1800)),
    }


def load_spec(session: str) -> dict:
    path = tasks_path(session)
    if not path.exists():
        raise SystemExit(
            f"tasks.yaml がありません: {path}\n先に `agr init --session {session}` を実行してください"
        )
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tasks = [normalize_task(t) for t in raw.get("tasks", [])]
    return {
        "session": raw.get("session", session),
        "goal": raw.get("goal", ""),
        "base_branch": raw.get("base_branch", ""),
        "tasks": tasks,
        "by_id": {t["id"]: t for t in tasks},
    }


def find_cycle(spec: dict) -> list[str]:
    # DFS で循環を探す。見つかれば循環に含まれる id を返す
    color: dict[str, int] = {}
    stack: list[str] = []

    def visit(task_id: str) -> list[str]:
        color[task_id] = 1
        stack.append(task_id)
        for dep in spec["by_id"][task_id]["depends_on"]:
            if dep not in spec["by_id"]:
                continue
            if color.get(dep) == 1:
                return stack[stack.index(dep) :]
            if color.get(dep, 0) == 0:
                found = visit(dep)
                if found:
                    return found
        stack.pop()
        color[task_id] = 2
        return []

    for task_id in spec["by_id"]:
        if color.get(task_id, 0) == 0:
            found = visit(task_id)
            if found:
                return found
    return []


def validate_spec(spec: dict) -> list[str]:
    errors: list[str] = []
    tasks = spec["tasks"]
    if not tasks:
        errors.append("tasks が空です")
    seen: set[str] = set()
    for task in tasks:
        tid = task["id"]
        if not ID_PATTERN.match(tid):
            errors.append(f"{tid!r}: id は英数字・-・_ のみ")
        if tid in seen:
            errors.append(f"{tid}: id が重複")
        seen.add(tid)
        if task["executor"] not in PLANNABLE_EXECUTORS:
            errors.append(
                f"{tid}: executor {task['executor']!r} は未定義（{', '.join(PLANNABLE_EXECUTORS)}）"
            )
        if not task["title"]:
            errors.append(f"{tid}: title が必要（辺ラベルになる）")
        for dep in task["depends_on"]:
            if dep not in spec["by_id"]:
                errors.append(f"{tid}: depends_on の {dep} が存在しない")
            if dep == tid:
                errors.append(f"{tid}: 自分自身に依存している")
        kind = EXECUTORS.get(task["executor"], {}).get("kind", "")
        if kind in ("codex", "claude") and not task["accept"]:
            errors.append(
                f"{tid}: accept（受け入れコマンド）が必要。機械検証できない委譲は禁止"
            )
        if kind == "codex" and not task["scope"]:
            errors.append(f"{tid}: codex タスクには scope（触ってよいファイル）が必要")
        if kind in ("codex", "claude") and not task["prompt"].strip():
            errors.append(f"{tid}: prompt が空")
        if task["retry"]["escalate_to"] not in PLANNABLE_EXECUTORS:
            errors.append(
                f"{tid}: retry.escalate_to {task['retry']['escalate_to']!r} は未定義"
            )
    cycle = find_cycle(spec)
    if cycle:
        errors.append("依存が循環しています: " + " → ".join(cycle))
    pr_tasks = [t for t in tasks if t["executor"] == "pr"]
    if len(pr_tasks) > 1:
        errors.append("pr タスクは 1 つまで")
    for pr in pr_tasks:
        ancestors = all_ancestors(spec, pr["id"])
        others = {t["id"] for t in tasks if t["id"] != pr["id"]}
        if not others <= ancestors:
            errors.append(
                f"{pr['id']}: pr タスクは他の全タスクの下流（最終ノード）に置く"
            )
        # PR は人の承認を経てから作る。上流に human の承認ゲートを必ず 1 つ以上置く
        if not any(
            EXECUTORS.get(spec["by_id"][a]["executor"], {}).get("kind") == "human"
            for a in ancestors
            if a in spec["by_id"]
        ):
            errors.append(
                f"{pr['id']}: pr タスクの上流に executor: human の承認ゲートが必要"
            )
    return errors


def all_ancestors(spec: dict, task_id: str) -> set[str]:
    seen: set[str] = set()
    frontier = list(spec["by_id"][task_id]["depends_on"])
    while frontier:
        current = frontier.pop()
        if current in seen or current not in spec["by_id"]:
            continue
        seen.add(current)
        frontier.extend(spec["by_id"][current]["depends_on"])
    return seen


def task_state(state: dict, task_id: str) -> dict:
    return state.setdefault(
        task_id,
        {
            "state": "planned",
            "attempts": 0,
            "executor": "",
            "feedback": "",
            "updated": "",
        },
    )


def is_ready(task: dict, state: dict) -> bool:
    own = state.get(task["id"], {}).get("state", "planned")
    if own != "planned":
        return False
    return all(state.get(dep, {}).get("state") == "done" for dep in task["depends_on"])


def ready_tasks(spec: dict, state: dict) -> list[dict]:
    return [t for t in spec["tasks"] if is_ready(t, state)]


def is_blocked_by_failure(task: dict, state: dict) -> bool:
    # 上流が終端の失敗状態なら、このタスクは永遠に ready にならない
    return any(
        state.get(dep, {}).get("state") in ("failed", "rejected")
        for dep in task["depends_on"]
    )


def summarize(spec: dict, state: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in spec["tasks"]:
        current = state.get(task["id"], {}).get("state", "planned")
        counts[current] = counts.get(current, 0) + 1
    return counts
