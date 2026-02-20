# CLAUDE.md

このファイルは、このリポジトリ内のコードを扱うときにClaude Code（claude.ai/code）へのガイダンスを提供します。

## リポジトリの概要

macOS用の環境セットアップを自動化するdotfilesコレクションです。シェル設定、開発環境、AIツール設定を管理します。

## 主要なファイルと構造

```
.
├── setup.sh                    # 初期セットアップスクリプト
├── setup-minimal.sh            # 最小限のセットアップ
├── Brewfile                    # Homebrewパッケージ定義
├── shell/                      # シェル関連設定
│   ├── .zshrc, .alias, .function, .bashrc, .tmux.conf
├── .config/                    # アプリケーション設定
│   ├── ghostty/, nvim/, karabiner/
├── .snippets/                  # Cursor用コードスニペット
├── .claude/                    # Claude Code設定
│   ├── CLAUDE.md, settings.json, rules/*.md
└── .codex/                     # OpenAI Codex設定
    ├── AGENTS.md
    └── config.toml
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
| `.snippets/` | `~/Library/Application Support/Cursor/User/snippets` |
| `.claude/CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `.claude/settings.json` | `~/.claude/settings.json` |
| `.claude/rules/*.md` | `~/.claude/rules/` |
| `.codex/AGENTS.md` | `~/.codex/AGENTS.md` |
| `.codex/config.toml` | `~/.codex/config.toml` |
| `Brewfile` | `~/Brewfile` |

## 注意事項

- `.claude/` と `.codex/` はAIツール用のグローバル設定（個人ルール）
- このリポジトリ直下の `CLAUDE.md` / `AGENTS.md` はリポジトリ固有の説明
