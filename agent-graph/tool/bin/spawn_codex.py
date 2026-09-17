"""単発の Codex 委譲: herdr の pane で codex exec を走らせ、完了を待って最終出力を返す（グラフを使わない小さな作業向け）"""

from __future__ import annotations

import argparse
import shlex
import sys
from pathlib import Path

from common import (
    OUT_DIR,
    PROJECT_DIR,
    STATE_DIR,
    TASKS_DIR,
    append_event,
    ensure_dirs,
    load_json,
    next_counter,
    resolve_session,
    save_json,
)
from graph_model import CODEX_EXEC_FLAGS, EXECUTORS
from harness import run_accept
from herdr_runner import HerdrRunner, LocalRunner, create_runner, write_job_script


def allocate_node_id(session: str) -> str:
    return f"codex-{next_counter(STATE_DIR / f'codex_counter_{session}'):02d}"


def read_task(args: argparse.Namespace) -> str:
    return args.task if args.task else Path(args.task_file).read_text(encoding="utf-8")


def job_path(session: str, node_id: str) -> Path:
    return STATE_DIR / "jobs" / session / f"{node_id}.json"


def build_body(cwd: Path, prompt_path: Path, out_path: Path, model: str) -> str:
    # model が空なら -m を付けず、Codex 側の既定（~/.codex/config.toml）に任せる
    model_flag = f"-m {shlex.quote(model)} " if model else ""
    return (
        f"cd {shlex.quote(str(cwd))}\n"
        f"codex exec {model_flag}{CODEX_EXEC_FLAGS} "
        f"-o {shlex.quote(str(out_path))} - < {shlex.quote(str(prompt_path))}\n"
    )


def report(
    session: str,
    node_id: str,
    handle: str,
    out_path: Path,
    accept: list[str],
    cwd: Path,
    runner: HerdrRunner | LocalRunner,
    timeout_sec: int,
    close: bool,
) -> None:
    if not runner.wait(handle, node_id, timeout_sec):
        print(f"[agent-graph] {session}/{node_id} はまだ実行中です（{timeout_sec}s 待機）。再度 wait してください。")
        sys.exit(1)
    exit_code = runner.exit_code(handle, node_id)
    verify = run_accept(accept, cwd, timeout_sec) if accept else {"passed": True, "results": []}
    status = "done" if exit_code == 0 and out_path.exists() and verify["passed"] else "failed"
    append_event({"event": "codex_done", "session": session, "node_id": node_id, "status": status, "exit_code": exit_code, "verify": verify})
    if close:
        runner.close(handle)
    print(f"[agent-graph] {session}/{node_id} {status} (exit={exit_code}, handle={handle})")
    for result in verify["results"]:
        print(f"  受け入れ `{result['command']}`: {'合格' if result['code'] == 0 else '不合格'}")
        if result["code"] != 0:
            print(result["output"])
    print(f"--- Codex の最終メッセージ ({out_path}) ---")
    print(out_path.read_text(encoding="utf-8") if out_path.exists() else "(出力ファイルなし。pane の画面を確認してください)")


def launch(
    session: str,
    task: str,
    description: str,
    accept: list[str],
    parent: str,
    cwd: Path,
    runner: HerdrRunner | LocalRunner,
    model: str = "",
) -> tuple[str, str, Path]:
    # 採番 → 指示書とジョブスクリプトを置く → 実行開始 → 開始イベントとジョブ情報を記録
    node_id = allocate_node_id(session)
    prompt_path = TASKS_DIR / session / f"{node_id}.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(task, encoding="utf-8")
    out_path = OUT_DIR / session / f"{node_id}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    script = write_job_script(session, node_id, build_body(cwd, prompt_path, out_path, model))

    handle = runner.start(session, node_id, f"{session}/{node_id}", script, cwd)
    append_event({"event": "codex_start", "session": session, "node_id": node_id, "parent": parent, "pane": handle, "model": model, "description": description, "task": task, "out": str(out_path), "accept": accept})
    # description と prompt を残し、失敗時にダッシュボードから同じ内容で再実行できるようにする
    save_json(job_path(session, node_id), {"pane": handle, "out": str(out_path), "parent": parent, "accept": accept, "cwd": str(cwd), "description": description, "prompt": str(prompt_path), "model": model})
    print(f"[agent-graph] {session}/{node_id} を {handle} で開始しました。")
    return node_id, handle, out_path


def resolve_model(model: str) -> str:
    # 明示指定を優先。無ければ EXECUTORS の既定。それも空ならフラグ自体を省略する
    return model or EXECUTORS["codex"]["model"]


def spawn(args: argparse.Namespace) -> None:
    ensure_dirs()
    session = resolve_session(args.session)
    runner = create_runner(args.pane, args.direction)
    cwd = Path(args.cwd).resolve() if args.cwd else PROJECT_DIR
    model = resolve_model(args.model)
    node_id, handle, out_path = launch(session, read_task(args), args.description, args.accept, args.parent, cwd, runner, model)
    if args.no_wait:
        print(f"完了待ち: agc wait {node_id} --session {session}")
        return
    report(session, node_id, handle, out_path, args.accept, cwd, runner, args.timeout_sec, args.close)


def load_job(session: str, node_id: str) -> dict:
    job = load_json(job_path(session, node_id), {})
    if not job:
        sys.exit(f"ジョブ {session}/{node_id} が見つかりません。")
    return job


def wait(args: argparse.Namespace) -> None:
    session = resolve_session(args.session)
    job = load_job(session, args.node_id)
    runner = create_runner(job["pane"], "right")
    report(session, args.node_id, job["pane"], Path(job["out"]), job.get("accept", []), Path(job["cwd"]), runner, args.timeout_sec, args.close)


def rerun(args: argparse.Namespace) -> None:
    # 失敗・追跡不能になった単発ジョブを、同じ指示書・受け入れ条件で新しい番号として投げ直す
    ensure_dirs()
    session = resolve_session(args.session)
    job = load_job(session, args.node_id)
    prompt_path = Path(job.get("prompt") or TASKS_DIR / session / f"{args.node_id}.md")
    if not prompt_path.exists():
        sys.exit(f"指示書が見つかりません: {prompt_path}")
    runner = create_runner(args.pane, "right")
    cwd = Path(job["cwd"])
    model = resolve_model(job.get("model", ""))
    node_id, handle, out_path = launch(session, prompt_path.read_text(encoding="utf-8"), job.get("description", ""), job.get("accept", []), job.get("parent", "root"), cwd, runner, model)
    if args.no_wait:
        print(f"完了待ち: agc wait {node_id} --session {session}")
        return
    report(session, node_id, handle, out_path, job.get("accept", []), cwd, runner, args.timeout_sec, args.close)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codex を herdr の pane に spawn する（単発用）")
    sub = parser.add_subparsers(dest="command", required=True)

    spawn_parser = sub.add_parser("spawn", help="タスクを投げる")
    source = spawn_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--task", help="タスク本文")
    source.add_argument("--task-file", help="タスク本文を書いたファイル")
    spawn_parser.add_argument("--description", default="", help="グラフの辺に出る短い説明（40 字以内推奨）")
    spawn_parser.add_argument("--accept", action="append", default=[], help="受け入れコマンド（複数可）。通らなければ failed")
    spawn_parser.add_argument("--model", default="", help="Codex のモデル id。省略時は EXECUTORS の既定（graph_model.py）")
    spawn_parser.add_argument("--session", help="セッション識別子（省略時は現在のセッション）")
    spawn_parser.add_argument("--parent", default="root", help="親ノード id")
    spawn_parser.add_argument("--pane", help="分割元の pane id（省略時は環境変数）")
    spawn_parser.add_argument("--direction", default="right", choices=["right", "down"])
    spawn_parser.add_argument("--cwd", help="Codex の作業ディレクトリ（省略時はプロジェクト直下）")
    spawn_parser.add_argument("--timeout-sec", type=int, default=1800)
    spawn_parser.add_argument("--no-wait", action="store_true", help="投げてすぐ戻る（長いタスク向け）")
    spawn_parser.add_argument("--close", action="store_true", help="完了後に pane を閉じる")

    wait_parser = sub.add_parser("wait", help="--no-wait で投げたタスクの完了を待つ")
    wait_parser.add_argument("node_id")
    wait_parser.add_argument("--session")
    wait_parser.add_argument("--timeout-sec", type=int, default=1800)
    wait_parser.add_argument("--close", action="store_true")

    rerun_parser = sub.add_parser("rerun", help="失敗したタスクを同じ内容で投げ直す（新しい番号になる）")
    rerun_parser.add_argument("node_id")
    rerun_parser.add_argument("--session")
    rerun_parser.add_argument("--pane", help="分割元の pane id（省略時は環境変数）")
    rerun_parser.add_argument("--timeout-sec", type=int, default=1800)
    rerun_parser.add_argument("--no-wait", action="store_true")
    rerun_parser.add_argument("--close", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    {"spawn": spawn, "wait": wait, "rerun": rerun}[args.command](args)


if __name__ == "__main__":
    main()
