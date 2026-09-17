# agent-graph

## 配置

スクリプト本体は `agent-graph/tool/`（`~/.local/share/agent-graph` にリンク）。
`uv run --project agent-graph/tool python agent-graph/tool/bin/<script>.py` で動く。
コマンドは `~/.local/bin` の `agr` / `agc` / `agd`。実体は `agent-graph/bin/` のラッパー。
タスクグラフの雛形は `agent-graph/tool/tasks.example.yaml`。
`agr init --session <識別子>` が雛形を `.agents/graph/<識別子>/tasks.yaml` にコピーする。

## セッション識別子

起動時に hook が識別子を通知する。形式は `<repo>-<No>`。
`agr` と `agc` には `--session <識別子>` を渡す。識別子はダッシュボードの根ノード名になる。

## 実行時生成物

利用側リポジトリ直下に生成される `.agents/`（`state/` `tasks/` `out/` `worktrees/` `graph/*/`）は、
起動時の hook が `.git/info/exclude` に追記して除外する。リポジトリの `.gitignore` は触らない。

## コマンド

`agr init` / `agr validate` / `agr launch` / `agr status` / `agr approve|retry|reject <id>`。
単発のコーディング委譲は `agc spawn --session <識別子> --accept "<検証コマンド>" --task-file <md>`。

## 委譲の規則

受け入れ条件の必須化とモデル選択の方針は `.claude/CLAUDE.md` を見る。
往復の上限も同じファイルにある。
