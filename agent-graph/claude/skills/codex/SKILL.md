---
name: codex
description: 単発のコーディング作業（小さな実装・修正・テスト作成）を Codex (gpt-6-astra) に委譲する手順。複数ステップや依存があるなら /plan でタスクグラフにする。
---

# 単発の Codex 委譲

Codex は herdr の別 tab で `codex exec` として動く。呼び出しは `agc`（spawn_codex.py）だけを使う。

## 1. タスク本文を書く

Write ツールで `.agents/tasks/_draft/<短い名前>.md` に、自己完結の指示を書く。

- 目的（何ができれば完了か）
- 対象ファイル
- 受け入れ条件（コマンド）
- 制約（触ってはいけない場所、依存追加の可否）

コーディング規約は繰り返さない。Codex はリポジトリ直下の `AGENTS.md` を自動で読む。

## 2. spawn する

```bash
agc spawn \
  --session <セッション識別子> \
  --description "<40 字以内の要約>" \
  --accept "uv run pytest tests/test_x.py -q" \
  --task-file .agents/tasks/_draft/<短い名前>.md
```

- `--accept` は必ず付ける。通らなければ `failed` として返る
- `--description` はグラフの辺ラベルになる。「動詞＋対象」で書く
- 5 分を超えそうなら `--no-wait` で投げ、後で `agc wait <node_id> --session <識別子>` する（Bash ツールのタイムアウト回避）

## 3. 結果を統合する

- 標準出力に受け入れ結果と Codex の最終メッセージが返る
- `git diff --stat` で変更範囲を確認し、受け入れ条件を自分でも検証する
- 不足があれば、差分を踏まえた追加タスクを新しく spawn する

## 単発をやめてグラフにする目安

- タスクが 2 つ以上で依存がある
- worktree で隔離したい（同時に複数走らせる）
- レビューと PR まで自動で回したい
