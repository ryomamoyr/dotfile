# AGENTS.md

このファイルは、このリポジトリ内のコードを扱うときにAIコーディングエージェントへのガイダンスを提供します。

## リポジトリの概要

macOS用の環境セットアップを自動化するdotfilesコレクションです。シェル設定、開発環境、AIツール設定を管理します。

## 主要なファイルと構造

```
.
├── setup.sh                    # 初期セットアップスクリプト
├── setup-minimal.sh            # 最小限のセットアップ
├── Brewfile                    # Homebrewパッケージ定義
├── shell/                      # シェル関連設定
│   ├── .zshrc, .alias, .abbr, .function, .bashrc, .tmux.conf
├── .config/                    # アプリケーション設定
│   ├── ghostty/, nvim/, karabiner/, zed/, borders/, herdr/
├── .snippets/                  # Cursor用コードスニペット
├── .claude/                    # Claude Code設定
│   ├── CLAUDE.md, settings.json, rules/*.md, skills/*, hooks/*
├── .codex/                     # OpenAI Codex設定
│   ├── AGENTS.md, config.toml
│   └── hooks.json.template     # setup.shが~/.codex/hooks.jsonへ生成する雛形
├── agent-graph/                # Claude Code/Codex/herdrを繋ぐタスクグラフ・可視化ツール一式
└── docs/
    └── agents/                 # AI agent向け参照文書
```

## セットアップコマンド

```bash
# フルセットアップ
./setup.sh

# 最小限セットアップ
./setup-minimal.sh
```

## シンボリックリンク一覧

setup.sh実行時に以下のリンクが作成されます：

| 元ファイル | リンク先 |
|------------|----------|
| `shell/.zshrc` | `~/.zshrc` |
| `shell/.alias` | `~/.alias` |
| `shell/.function` | `~/.function` |
| `shell/.bashrc` | `~/.bashrc` |
| `shell/.tmux.conf` | `~/.tmux.conf` |
| `.config/nvim/` | `~/.config/nvim/` |
| `.config/ghostty/config` | `~/.config/ghostty/config` |
| `.config/ghostty/start_tmux.sh` | `~/.config/ghostty/start_tmux.sh` |
| `.config/ghostty/start_herdr.sh` | `~/.config/ghostty/start_herdr.sh` |
| `.config/herdr/config.toml` | `~/.config/herdr/config.toml` |
| `.config/zed/settings.json` | `~/.config/zed/settings.json` |
| `.config/zed/tasks.json` | `~/.config/zed/tasks.json` |
| `.config/zed/keymap.json` | `~/.config/zed/keymap.json` |
| `shell/.abbr` | `~/.abbr` |
| `.snippets/` | `~/Library/Application Support/Cursor/User/snippets` |
| `.snippets/` | `~/Library/Application Support/Code/User/snippets` |
| `.vscode/User/settings.json` | `~/Library/Application Support/Code/User/settings.json` |
| `.vscode/User/keybindings.json` | `~/Library/Application Support/Code/User/keybindings.json` |
| `.cursor/User/settings.json` | `~/Library/Application Support/Cursor/User/settings.json` |
| `.cursor/User/keybindings.json` | `~/Library/Application Support/Cursor/User/keybindings.json` |
| `.claude/CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `.claude/settings.json` | `~/.claude/settings.json` |
| `.claude/rules/*.md` | `~/.claude/rules/` |
| `.codex/AGENTS.md` | `~/.codex/AGENTS.md` |
| `.codex/config.toml` | `~/.codex/config.toml` |
| `.codex/hooks.json.template` | `~/.codex/hooks.json`（絶対パス展開して生成、symlinkではない） |
| `.config/borders/bordersrc` | `~/.config/borders/bordersrc` |
| `Brewfile` | `~/Brewfile` |
| `.gitignore_global` | `~/.gitignore_global` |
| `agent-graph/claude/agents/` | `~/.claude/agents/` |
| `agent-graph/tool/` | `~/.local/share/agent-graph/` |
| `agent-graph/bin/{agr,agc,agd}` | `~/.local/bin/{agr,agc,agd}` |

## herdrとtmux

Ghostty起動時のデフォルトは `start_herdr.sh`（herdr）。tmuxは `pj`/`pjs`/`tm` がherdr未起動時に
フォールバックする用途、および `start_tmux.sh` を手動実行したときの独自レイアウト用途に限って残す。
新規のマルチプレクサ連携はherdrを前提に設計する。

## agent-graph

Claude Code / Codex CLI / herdr を横断するタスクグラフ実行基盤。実体は `agent-graph/`。
使い方・受け入れ条件付き委譲の作法は `agent-graph/README.md` と `docs/agents/agent-graph.md` を参照。
`agent-graph/tool/bin/harness.py` の改ざん防止のためのroot所有ガードが `agent-graph/stage/guard/` にある
（`agent-graph/stage/guard/DESIGN.md` 参照。導入はsudoが要るため人が行う）。

## 注意事項

- `.claude/` と `.codex/` はAIツール用のグローバル設定（個人ルール）
- このリポジトリ直下の `CLAUDE.md` / `AGENTS.md` はリポジトリ固有の説明
