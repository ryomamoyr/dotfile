# agent-graph（dotfiles 版）

どのリポジトリで `claude` を起こしても、同じハーネス・タスクグラフ・可視化・sandbox が効く構成。実体は dotfiles に置き、`install.sh` が各所へ symlink する。リポジトリ側に置くファイルは無い。

解説は `docs/architecture.html`（ブラウザで開く）。

```
agent-graph/
├─ install.sh                    symlink を張る（何度実行しても同じ）
├─ bin/agr, agc, agd             → ~/.local/bin/   タスクグラフ / 単発 Codex / ダッシュボード
├─ claude/
│   ├─ settings.merged.json      現行 ~/.claude/settings.json に統合した完成版（diff して置き換える）
│   ├─ CLAUDE.md                 → ~/.claude/CLAUDE.md に追記（オーケストレーション方針）
│   ├─ hooks/agent-graph-hook.sh → ~/.claude/hooks/
│   ├─ agents/{doc-light,doc-heavy,reviewer}.md → ~/.claude/agents/
│   └─ skills/{plan,codex}/      → ~/.claude/skills/
├─ codex/
│   ├─ AGENTS.md                 → ~/.codex/AGENTS.md（全リポジトリ共通のコーディング規約）
│   └─ config.snippet.toml       ~/.codex/config.toml に追記（model = gpt-6-astra）
├─ tool/                         → ~/.local/share/agent-graph/
│   ├─ bin/*.py, graph.html      スクリプト本体
│   ├─ tasks.example.yaml        agr init が置く雛形
│   ├─ runner/Dockerfile, build.sh   sandbox イメージ
│   └─ pyproject.toml, uv.lock
├─ zsh/agent-graph.zsh           pj / pjs / agw
└─ docs/architecture.html        構成解説（人向け）
```

## 前提

- macOS + Homebrew、uv、jq、herdr、Claude Code、Codex CLI 0.153.0 以降（`codex login` 済み）
- PR まで回すなら `gh` と各リポジトリの `origin`
- sandbox を使うなら Docker

## 導入

```bash
mv agent-graph ~/00_project/dotfiles/agent-graph
~/00_project/dotfiles/agent-graph/install.sh
```

`install.sh` は symlink を張り、`~/.claude/CLAUDE.md` に方針を追記し、`~/.codex/AGENTS.md` を置き、uv 環境を作る。既に実ファイルがある場所は触らず、その旨を表示する。

手で行うのは 3 つ。

1. `~/.claude/settings.json` を `claude/settings.merged.json` と diff して置き換える。差分は agent-graph の hooks（SessionStart / SessionEnd / PreToolUse / PostToolUse / SubagentStart / SubagentStop）、`permissions.allow` と `deny`、`env` の 2 行。既存の hooks（tmux-notify、guard-*、auto-format、herdr-agent-state）はそのまま残している
2. `.zshrc` に `source ~/00_project/dotfiles/agent-graph/zsh/agent-graph.zsh` を追加する。`pj` が「左 pane で `HERDR_PANE_ID` を持って claude を起動する」版に置き換わる
3. `~/.codex/config.toml` に `codex/config.snippet.toml` の内容を追記する

sandbox を使うなら `tool/runner/build.sh` でイメージを作り、`.zshrc` で `export AGENT_GRAPH_SANDBOX=docker`。

## 日々の流れ

```bash
cd ~/00_project/<repo>
pj                                  # tab を作り、左で claude が起動。識別子 <repo>-<No> が通知される
agd                                 # 右 pane で。ブラウザで http://127.0.0.1:8765/

agr init     --session <識別子>     # 雛形を .agents/graph/<識別子>/tasks.yaml に置く（/plan が書き換える）
agr validate --session <識別子>
agr launch   --session <識別子>     # スケジューラが別 tab で走る
agr status   --session <識別子>
agr approve <id> --session <識別子> # retry / reject も同様。herdr の gate tab で a/r/x でも可

agc spawn --session <識別子> --description "…" --accept "uv run pytest -q" --task-file …   # 単発 Codex
```

- エージェントは仕事ごとに herdr の tab を持つ（`AGENT_GRAPH_PLACEMENT=tab`）。done の tab は自動で閉じ、failed / 判断待ちは残る。以前の分割方式は `=split`
- スケジューラが止まっても状態は残る。同じ `agr launch` で続きから再開する
- herdr なしで試すときは `AGENT_GRAPH_RUNNER=local`（出力は `<repo>/.agents/state/logs/`）

## リポジトリに何が生えるか

起動時の hook が `<repo>/.agents/` を作り、`.git/info/exclude` に `.agents/` を追記する。リポジトリの `.gitignore` は触らない。中身は `state/`（イベント・実行状態・採番）、`graph/`（tasks.yaml、report.md）、`worktrees/`、`out/`、`tasks/`。

## 動作確認

- 任意のリポジトリで `claude` を起こし、`[agent-graph] このセッションの識別子は <repo>-001 です` と出る
- `git status` が変わらず、`.git/info/exclude` に `.agents/` がある
- Claude に `git push origin main` を頼むと hook が拒否し、理由が返る
- `agr init && agr validate` が通る

## 既知の制約

- herdr の JSON 形は起動スクリプトから確認済み。未確認は `herdr tab create --no-focus` の有無
- docker sandbox モードは実機未検証
- Claude サブエージェントへの委譲文は開始時点で先着順の対応付け。完了時に transcript から補正される
- ruff は `uvx` 経由のため初回はネットワークが必要。リポジトリの `.gitignore` に `__pycache__/` と `.venv/` を入れておく
- git 管理外のディレクトリでも hooks は効くが、スケジューラは動かない
- 実機の herdr / Codex / Claude headless では未検証。偽物で、空リポジトリに `.agents/` が生えるところから PR までを通している
