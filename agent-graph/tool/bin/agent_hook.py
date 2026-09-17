"""Claude Code hooks の受け口: 採番・記録に加え、危険操作の拒否・lint・受け入れ検証を決定的に強制する"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

from common import (
    COUNTER_PATH,
    CURRENT_SESSION_PATH,
    EVENTS_PATH,
    PROJECT_DIR,
    SESSIONS_PATH,
    append_event,
    ensure_dirs,
    load_json,
    locked_events,
    next_counter,
    read_events,
    save_json,
    tasks_path,
)
from graph_model import load_spec
from harness import check_bash, check_path, lint_file, run_accept

ROOT_MODEL = "fable"
# pj() が claude 起動時に export する pane id。根 pane にセッション名を付けるのに使う
HERDR_PANE_ENV = "HERDR_PANE_ID"
# スケジューラが起こした子セッションであることを示す環境変数
PARENT_SESSION_ENV = "AGENT_GRAPH_PARENT_SESSION"
TASK_ENV = "AGENT_GRAPH_TASK"
SYSTEM_REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
TASK_TAG = re.compile(r"\[(T[A-Za-z0-9_-]+)\]")
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
BULLET = re.compile(r"^\s*(?:[-*・•]|\d+[.)])\s+(.*)")
HEADING = re.compile(r"^\s*#+\s*")
SUMMARY_LINES = 3
SUMMARY_WIDTH = 80
REPLY_LIMIT = 6000
# 子の最終報告をノードに保持する上限
RESULT_LIMIT = 4000
# 最終応答の書き込み待ち: 0.4 秒 × 5 回
REPLY_WAIT_SEC = 0.4
REPLY_WAIT_TRIES = 5


def latest_turn_session() -> str:
    # 末尾から遡り、最初に見つかった turn_start / turn_done のセッション名を返す
    if not EVENTS_PATH.exists():
        return ""
    for line in reversed(EVENTS_PATH.read_text(encoding="utf-8").splitlines()):
        if not line.strip().endswith("}"):
            continue
        record = json.loads(line)
        if record.get("event") in ("turn_start", "turn_done"):
            return record.get("session", "")
    return ""


def current_session_name() -> str:
    if not CURRENT_SESSION_PATH.exists():
        return ""
    return CURRENT_SESSION_PATH.read_text().strip()


def next_unused_name(used: set[str]) -> str:
    # カウンタと実際の使用済み名前がずれていても、衝突したら次の番号へ進む
    while True:
        name = f"{PROJECT_DIR.name}-{next_counter(COUNTER_PATH):03d}"
        if name not in used:
            return name


def resolve_session_name(session_id: str, source: str = "") -> str:
    # 同じ session_id（resume / compact）は既存名を引き継ぎ、新規のみ採番する
    sessions = load_json(SESSIONS_PATH, {})
    if session_id in sessions:
        return sessions[session_id]
    # fork は session_id が変わるだけで会話は同じ。直近の会話名を継承し採番しない
    inherited = (latest_turn_session() or current_session_name()) if source == "fork" else ""
    # 既に他の session_id へ割り当て済みの名前は、新規採番では使わない
    name = inherited or next_unused_name(set(sessions.values()))
    sessions[session_id] = name
    save_json(SESSIONS_PATH, sessions)
    return name


def register_child_session(session_id: str, parent: str) -> None:
    sessions = load_json(SESSIONS_PATH, {})
    sessions[session_id] = parent
    save_json(SESSIONS_PATH, sessions)


def lookup_session_name(data: dict) -> str:
    sessions = load_json(SESSIONS_PATH, {})
    return sessions.get(
        data.get("session_id", ""), os.environ.get(PARENT_SESSION_ENV, "unknown")
    )


def rename_herdr_pane(label: str) -> None:
    pane = os.environ.get(HERDR_PANE_ENV, "")
    if not pane or not shutil.which("herdr"):
        return
    subprocess.run(
        ["herdr", "pane", "rename", pane, label], capture_output=True, text=True
    )


def extract_first_user_text(transcript_path: str) -> str:
    # サブエージェントの transcript の最初の user メッセージ = 親が渡したタスク本文
    path = Path(transcript_path).expanduser()
    if not transcript_path or not path.exists():
        return ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().endswith("}"):
            continue
        record = json.loads(line)
        if record.get("type") != "user":
            continue
        content = record.get("message", {}).get("content", "")
        if isinstance(content, str):
            return SYSTEM_REMINDER.sub("", content).strip()
        texts = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return SYSTEM_REMINDER.sub("", "\n".join(texts)).strip()
    return ""


def _text_of(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
        ).strip()
    return ""


def _reply_after_last_prompt(path: Path) -> str:
    # 直近の「人の指示」（tool_result ではない user レコード）より後にある assistant 本文のうち最後のもの
    last_user = -1
    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().endswith("}"):
            continue
        record = json.loads(line)
        records.append(record)
        if record.get("type") == "user":
            content = record.get("message", {}).get("content", "")
            is_tool_result = isinstance(content, list) and any(
                isinstance(b, dict) and b.get("type") == "tool_result" for b in content
            )
            if not is_tool_result and _text_of(content):
                last_user = len(records) - 1
    last = ""
    for record in records[last_user + 1 :]:
        if record.get("type") == "assistant":
            body = _text_of(record.get("message", {}).get("content", ""))
            if body:
                last = body
    return last


def extract_last_assistant_text(transcript_path: str) -> str:
    # Stop の時点で最終応答が transcript に書かれていないことがある。書かれるまで短く待つ（最大 2 秒）
    if not transcript_path:
        return ""
    path = Path(transcript_path).expanduser()
    if not path.exists():
        return ""
    for _ in range(REPLY_WAIT_TRIES):
        reply = _reply_after_last_prompt(path)
        if reply:
            return reply
        time.sleep(REPLY_WAIT_SEC)
    return ""


def extract_handback_message(transcript_path: str) -> str:
    # 子は SubagentHandback ツール呼び出しの input.message で報告する。その最後の値を返す。無ければ空文字
    if not transcript_path:
        return ""
    path = Path(transcript_path).expanduser()
    if not path.exists():
        return ""
    message = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip().endswith("}"):
            continue
        record = json.loads(line)
        if record.get("type") != "assistant":
            continue
        content = record.get("message", {}).get("content", "")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("name") != "SubagentHandback":
                continue
            candidate = block.get("input", {}).get("message", "")
            if candidate:
                message = candidate
    return message


def summarize_reply(text: str) -> list[str]:
    # 箇条書きがあればそれを優先し、無ければ見出し以外の先頭行。ダッシュボードの履歴に出す
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    bullets = [m.group(1) for ln in lines for m in [BULLET.match(ln)] if m]
    picked = bullets or [HEADING.sub("", ln) for ln in lines if not ln.startswith("```")]
    cleaned = [re.sub(r"[*`_]", "", p).strip() for p in picked]
    return [
        p if len(p) <= SUMMARY_WIDTH else p[: SUMMARY_WIDTH - 1] + "…"
        for p in cleaned
        if p
    ][:SUMMARY_LINES]


def deny(reason: str) -> None:
    # exit 2 = ツール実行を止め、理由を Claude に返す
    print(f"[harness] 拒否: {reason}", file=sys.stderr)
    sys.exit(2)


# ---------- セッション ----------


def handle_session_start(data: dict) -> None:
    # どのリポジトリで起動しても <repo>/.agents/ を作り、.git/info/exclude で除外する
    ensure_dirs()
    session_id = data["session_id"]
    parent = os.environ.get(PARENT_SESSION_ENV, "")
    if parent:
        register_child_session(session_id, parent)
        append_event(
            {
                "event": "child_session_start",
                "session": parent,
                "task_id": os.environ.get(TASK_ENV, ""),
                "session_id": session_id,
            }
        )
        print(
            f"[agent-graph] あなたはセッション {parent} のタスク {os.environ.get(TASK_ENV, '')} の実行者です。渡された指示の範囲で作業してください。"
        )
        return
    source = data.get("source", "")
    known = session_id in load_json(SESSIONS_PATH, {})
    # 未知の session_id には採番しない。人の最初の指示（UserPromptSubmit）まで遅らせる
    name = resolve_session_name(session_id, source) if known or source == "fork" else ""
    if name:
        CURRENT_SESSION_PATH.write_text(name)
    append_event(
        {
            "event": "session_start",
            "session": name,
            "session_id": session_id,
            "source": source,
            "cwd": data.get("cwd", ""),
            "model": data.get("model") or ROOT_MODEL,
        }
    )
    if not name:
        return
    rename_herdr_pane(name)
    announce_session(name)


def has_recorded_turn(session_id: str) -> bool:
    # session_id を持たない旧形式の turn_start は、セッション名の一致で保護する
    name = load_json(SESSIONS_PATH, {}).get(session_id, "")
    return any(
        e.get("event") == "turn_start"
        and (
            e.get("session_id") == session_id
            or ("session_id" not in e and name and e.get("session") == name)
        )
        for e in read_events()
    )


def drop_session_events(session_id: str) -> None:
    # 一時ファイルに書いてから置換する。途中で落ちても events.jsonl を壊さない
    # 読み込みから置換までロックを保持し、その間の追記を取りこぼさない
    with locked_events():
        if not EVENTS_PATH.exists():
            return
        kept = [
            line
            for line in EVENTS_PATH.read_text(encoding="utf-8").splitlines(keepends=True)
            if not (
                line.strip().endswith("}")
                and json.loads(line).get("session_id") == session_id
            )
        ]
        temp = EVENTS_PATH.with_name(EVENTS_PATH.name + ".tmp")
        temp.write_text("".join(kept), encoding="utf-8")
        temp.replace(EVENTS_PATH)


def forget_session(session_id: str) -> None:
    sessions = load_json(SESSIONS_PATH, {})
    if sessions.pop(session_id, None):
        save_json(SESSIONS_PATH, sessions)


def handle_session_end(data: dict) -> None:
    if os.environ.get(PARENT_SESSION_ENV):
        return
    session_id = data.get("session_id", "")
    # 一度も指示が無かったセッションは記録ごと消す。空の会話を履歴に残さない
    if session_id and not has_recorded_turn(session_id):
        drop_session_events(session_id)
        forget_session(session_id)
        return
    append_event(
        {
            "event": "session_end",
            "session": lookup_session_name(data),
            "reason": data.get("reason", ""),
        }
    )


def announce_session(name: str) -> None:
    # SessionStart / 初回 UserPromptSubmit の stdout は Claude のコンテキストに追加される
    print(
        f"[agent-graph] このセッションの識別子は {name} です。"
        f"タスクグラフは .agents/graph/{name}/tasks.yaml、Codex 委譲や run_graph には --session {name} を渡すこと。"
        f"コマンドは `agr <サブコマンド>`（= run_graph.py）と `agc`（= spawn_codex.py）で呼べる。"
    )


def ensure_session_named(session_id: str) -> None:
    # 人が最初の指示を出した時点で採番する。始まらなかった会話に番号を使わせない
    if not session_id or session_id in load_json(SESSIONS_PATH, {}):
        return
    name = resolve_session_name(session_id)
    CURRENT_SESSION_PATH.write_text(name)
    rename_herdr_pane(name)
    announce_session(name)


def record_turn_state(data: dict) -> None:
    if os.environ.get(PARENT_SESSION_ENV) or data.get("agent_id"):
        return
    event = "turn_done" if data["hook_event_name"] == "Stop" else "turn_start"
    if event == "turn_start":
        ensure_session_named(data.get("session_id", ""))
    record = {
        "event": event,
        "session": lookup_session_name(data),
        # 名前を共有する fork と区別するため、削除判定用に session_id も残す
        "session_id": data.get("session_id", ""),
        "prompt": data.get("prompt", ""),
    }
    if event == "turn_done":
        reply = (data.get("last_assistant_message") or "").strip() or extract_last_assistant_text(
            data.get("transcript_path", "")
        )
        record["summary"] = summarize_reply(reply)
        record["reply"] = reply[:REPLY_LIMIT]
    append_event(record)


# ---------- ツール呼び出し（記録と拒否） ----------


def record_safely(build: Callable[[], dict]) -> None:
    # 記録の失敗で判定結果を変えない。状態ファイルが壊れていても拒否は拒否のまま残す
    try:
        append_event(build())
    except Exception as error:  # noqa: BLE001
        print(f"[harness] 記録に失敗しました: {error}", file=sys.stderr)


def handle_pre_tool_use(data: dict) -> None:
    # 検査を記録より先に行う。記録側で例外が出ても拒否は取り消さない
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}
    command = tool_input.get("command") or ""
    path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
    # Codex の shell ツールは名前が異なりうる。command を持つ入力はすべて Bash として検査する
    if tool != "Agent" and isinstance(command, str) and command:
        reason = check_bash(command, PROJECT_DIR)
        if reason:
            record_safely(
                lambda: {
                    "event": "denied",
                    "session": lookup_session_name(data),
                    "tool": tool,
                    "reason": reason,
                    "command": command[:300],
                }
            )
            deny(reason)
    if tool in EDIT_TOOLS and isinstance(path, str):
        reason = check_path(path, PROJECT_DIR)
        if reason:
            record_safely(
                lambda: {
                    "event": "denied",
                    "session": lookup_session_name(data),
                    "tool": tool,
                    "reason": reason,
                    "path": path,
                }
            )
            deny(reason)
    if tool == "Agent":
        record_safely(
            lambda: {
                "event": "task_dispatch",
                "session": lookup_session_name(data),
                "task_id": os.environ.get(TASK_ENV, ""),
                "tool_use_id": data.get("tool_use_id", ""),
                "parent": data.get("agent_id") or "root",
                "agent_type": tool_input.get("subagent_type", "general-purpose"),
                "description": tool_input.get("description", ""),
                "prompt": tool_input.get("prompt", ""),
                "model": tool_input.get("model", ""),
            }
        )


def handle_post_tool_use(data: dict) -> None:
    # 編集直後に lint。落ちたら exit 2 で結果を Claude に返し、その場で直させる
    if data.get("tool_name") not in EDIT_TOOLS:
        return
    path = data.get("tool_input", {}).get("file_path", "")
    ok, output = lint_file(path)
    if not ok:
        print(f"[harness] lint 失敗 ({path}):\n{output}", file=sys.stderr)
        sys.exit(2)


# ---------- サブエージェント ----------


def handle_subagent_start(data: dict) -> None:
    append_event(
        {
            "event": "agent_start",
            "session": lookup_session_name(data),
            "task_id": os.environ.get(TASK_ENV, ""),
            "agent_id": data.get("agent_id", ""),
            "agent_type": data.get("agent_type", ""),
        }
    )


def enforce_acceptance(session: str, task_text: str, cwd: str) -> None:
    # 委譲文に [T1] のようなタスク id があれば、そのタスクの受け入れコマンドを通すまで終わらせない
    # tasks.yaml は Edit と Bash の書き込み先検査で守るが、python -c のような間接書き込みまでは塞げない
    match = TASK_TAG.search(task_text)
    if not match or not tasks_path(session).exists():
        return
    task = load_spec(session)["by_id"].get(match.group(1))
    if not task or not task["accept"]:
        return
    verify = run_accept(
        task["accept"], Path(cwd) if cwd else PROJECT_DIR, task["timeout_sec"]
    )
    append_event(
        {
            "event": "task_verify",
            "session": session,
            "task_id": task["id"],
            "passed": verify["passed"],
            "via": "subagent_stop",
        }
    )
    if verify["passed"]:
        return
    failed = [r for r in verify["results"] if r["code"] != 0]
    detail = "\n".join(
        f"- `{r['command']}` (exit={r['code']})\n{r['output']}" for r in failed
    )
    print(
        f"[harness] タスク {task['id']} の受け入れ条件が未達です。修正して再度実行してください:\n{detail}",
        file=sys.stderr,
    )
    sys.exit(2)


def handle_subagent_stop(data: dict) -> None:
    session = lookup_session_name(data)
    task_text = extract_first_user_text(data.get("agent_transcript_path", ""))
    # Claude Code 内部のバックグラウンドエージェント（種別も指示も無い）は記録しない
    if not data.get("agent_type") and not task_text:
        return
    # 報告は SubagentHandback の input.message を出典にする。無ければ最終応答本文に落とす
    result_text = extract_handback_message(
        data.get("agent_transcript_path", "")
    ) or extract_last_assistant_text(data.get("agent_transcript_path", ""))
    append_event(
        {
            "event": "agent_stop",
            "session": session,
            "task_id": os.environ.get(TASK_ENV, ""),
            "agent_id": data.get("agent_id", ""),
            "agent_type": data.get("agent_type", ""),
            "task": task_text,
            "result": result_text[:RESULT_LIMIT],
            "summary": summarize_reply(result_text),
        }
    )
    enforce_acceptance(session, task_text, data.get("cwd", ""))


HANDLERS = {
    "Stop": record_turn_state,
    "UserPromptSubmit": record_turn_state,
    "SessionStart": handle_session_start,
    "SessionEnd": handle_session_end,
    "PreToolUse": handle_pre_tool_use,
    "PostToolUse": handle_post_tool_use,
    "SubagentStart": handle_subagent_start,
    "SubagentStop": handle_subagent_stop,
}


def main() -> None:
    data = json.load(sys.stdin)
    handler = HANDLERS.get(data.get("hook_event_name", ""))
    if handler is not None:
        handler(data)


if __name__ == "__main__":
    main()
