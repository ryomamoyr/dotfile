# dotfiles

![macOS](https://img.shields.io/badge/macOS-000?logo=apple&logoColor=white)
![Neovim](https://img.shields.io/badge/Neovim-57A143?logo=neovim&logoColor=white)
![Ghostty](https://img.shields.io/badge/Ghostty-000?logo=ghostty&logoColor=white)
![tmux](https://img.shields.io/badge/tmux-1BB91F?logo=tmux&logoColor=white)
![Claude Code](https://img.shields.io/badge/Claude_Code-D97757?logo=anthropic&logoColor=white)

## プロジェクト構成

```
.
├── setup.sh                    # 初期セットアップスクリプト（フル）
├── setup-minimal.sh            # 最小限のセットアップスクリプト
├── Brewfile                    # brew bundle用パッケージ定義
├── shell/                      # シェル関連設定ファイル
│   ├── .zshrc                  # zsh基本設定
│   ├── .alias                  # エイリアス定義
│   ├── .abbr                   # 略語展開定義
│   ├── .function               # カスタム関数定義（pj, pjs, jk, tm 等）
│   ├── .bashrc                 # Bash設定
│   └── .tmux.conf              # tmux設定
├── .config/                    # アプリケーション設定
│   ├── ghostty/                # Ghostty設定（tmux/herdr起動スクリプト含む）
│   ├── herdr/                  # herdr（AIエージェント向けターミナルマルチプレクサ）設定
│   ├── nvim/                   # Neovim設定（LazyVimベース）
│   ├── karabiner/               # Karabiner設定
│   ├── zed/                    # Zed設定（settings/tasks/keymap）
│   └── borders/                # JankyBorders設定
├── .snippets/                  # コードスニペット（Cursor/VS Code共用）
├── .claude/                    # Claude Code グローバル設定
│   ├── CLAUDE.md               # 個人共通ルール
│   ├── settings.json           # Claude Code設定
│   ├── rules/                  # トピック別ルール
│   ├── skills/                 # カスタムスキル
│   └── hooks/                  # PreToolUse/SessionStart等のフック
├── .codex/                     # OpenAI Codex グローバル設定
│   ├── AGENTS.md               # 個人共通ルール
│   ├── config.toml
│   └── hooks.json.template     # setup.shが~/.codex/hooks.jsonへ生成する雛形
├── agent-graph/                # Claude Code/Codex/herdrを繋ぐタスクグラフ・可視化ツール一式
└── docs/
    └── agents/                 # AI agent向け参照文書（agent-graph.md 等）
```

## セットアップ

```sh
git clone https://github.com/ryomamoyr/dotfile.git <任意のディレクトリ>
cd <任意のディレクトリ>
./setup.sh
brew bundle --file=~/Brewfile
```

`setup.sh` の実行内容：
1. Xcode Command Line Tools / Homebrew / Nodebrew / uv / Zinit をインストール
2. 各設定ファイルのシンボリックリンクを作成（下表）
3. `.codex/hooks.json.template` を絶対パス展開して `~/.codex/hooks.json` を生成
4. agent-graph（`agr` / `agc` / `agd`）へのリンクを作成
5. `git config --global core.excludesfile` を `.gitignore_global` に設定

## シンボリックリンク一覧

| 元ファイル | リンク先 |
|------------|----------|
| `shell/.zshrc` | `~/.zshrc` |
| `shell/.alias` | `~/.alias` |
| `shell/.function` | `~/.function` |
| `shell/.bashrc` | `~/.bashrc` |
| `shell/.tmux.conf` | `~/.tmux.conf` |
| `shell/.abbr` | `~/.abbr` |
| `.config/nvim/` | `~/.config/nvim/` |
| `.config/ghostty/config` | `~/.config/ghostty/config` |
| `.config/ghostty/start_tmux.sh` | `~/.config/ghostty/start_tmux.sh` |
| `.config/ghostty/start_herdr.sh` | `~/.config/ghostty/start_herdr.sh` |
| `.config/herdr/config.toml` | `~/.config/herdr/config.toml` |
| `.config/karabiner/karabiner.json` | `~/.config/karabiner/karabiner.json` |
| `.config/borders/bordersrc` | `~/.config/borders/bordersrc` |
| `.config/zed/settings.json` | `~/.config/zed/settings.json` |
| `.config/zed/tasks.json` | `~/.config/zed/tasks.json` |
| `.config/zed/keymap.json` | `~/.config/zed/keymap.json` |
| `.snippets/` | `~/Library/Application Support/Cursor/User/snippets` |
| `.snippets/` | `~/Library/Application Support/Code/User/snippets` |
| `.vscode/User/settings.json` | `~/Library/Application Support/Code/User/settings.json` |
| `.vscode/User/keybindings.json` | `~/Library/Application Support/Code/User/keybindings.json` |
| `.cursor/User/settings.json` | `~/Library/Application Support/Cursor/User/settings.json` |
| `.cursor/User/keybindings.json` | `~/Library/Application Support/Cursor/User/keybindings.json` |
| `Brewfile` | `~/Brewfile` |
| `.gitignore_global` | `~/.gitignore_global` |
| `.claude/CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `.claude/settings.json` | `~/.claude/settings.json` |
| `.claude/rules/*.md` | `~/.claude/rules/` |
| `.claude/skills/` | `~/.claude/skills/` |
| `.claude/hooks/` | `~/.claude/hooks/` |
| `.codex/AGENTS.md` | `~/.codex/AGENTS.md` |
| `.codex/config.toml` | `~/.codex/config.toml` |
| `.codex/hooks.json.template` | `~/.codex/hooks.json`（絶対パス展開して生成、symlinkではない） |
| `agent-graph/claude/agents/` | `~/.claude/agents/` |
| `agent-graph/tool/` | `~/.local/share/agent-graph/` |
| `agent-graph/bin/{agr,agc,agd}` | `~/.local/bin/{agr,agc,agd}` |

## agent-graph

Claude Code / Codex CLI / herdr を横断するタスクグラフ実行基盤。`agent-graph/` に実体を置き、
`setup.sh` が `~/.local/bin`（`agr`/`agc`/`agd`）と `~/.claude/agents`、`~/.local/share/agent-graph` へ
リンクする。

- `agr init / validate / launch / status / approve|retry|reject` — 要望を `tasks.yaml` に分解し、
  スケジューラで自律実行・承認待ちを管理する
- `agc spawn --accept "<検証コマンド>"` — 単発のコーディング作業を Codex（gpt-6-astra）に委譲する
- `agd` — 実行状況を可視化するダッシュボード（`http://127.0.0.1:8765/`）
- 起動時の hook が利用側リポジトリに `.agents/`（state/graph/worktrees 等）を生成し、
  `.git/info/exclude` に追記して除外する（リポジトリの `.gitignore` は触らない）

詳細・導入手順・既知の制約は `agent-graph/README.md` を参照。AI agent向けの利用規約は
`docs/agents/agent-graph.md` にまとめている。

## Neovim プラグイン

LazyVim ベースで以下を追加：

| プラグイン | 役割 |
|-----------|------|
| neo-tree.nvim | ファイルツリー |
| toggleterm.nvim | 統合ターミナル |
| molten-nvim | Jupyter カーネル実行 |
| image.nvim | インライン画像表示（Kitty Graphics Protocol） |
| jupytext.nvim | `.ipynb` ↔ `.py` 自動変換 |
| NotebookNavigator.nvim | セル間移動・セル実行 |

## 便利なシェル関数

| コマンド | 動作 |
|---------|------|
| `pj [claudeオプション...] [名前]` | herdr が起動中なら herdr の tab を作り、左 pane で `claude` を起動・右 pane で `agd` をバックグラウンド起動してダッシュボードを開く。herdr 未起動なら tmux にフォールバックし、左右分割して左にフォーカスする |
| `pjs [名前]` | herdr が起動中なら herdr の tab を作り、上下分割（上にフォーカス）。herdr 未起動なら tmux にフォールバックし、上下分割して上にフォーカスする |
| `agw [識別子]` | agent-graph の状態（`agr status`）を5秒ごとに表示 |
| `jk [名前]` | Jupyter カーネル登録（uv プロジェクト用） |
| `tm [セッション名]` | tmux セッションに attach/switch。名前省略時は fzf で選択 |
| `ftpane` | tmux の pane を fzf で選択して切替 |
| `vfz` | fzf でファイル検索 → vim で開く |
| `cfz` | fzf でファイル検索 → cursor で開く |
| `ifz` | 画像を fzf + chafa プレビュー → timg で表示 |
| `fd` / `fda` / `fdr` | fzf でディレクトリ移動（カレント直下 / 再帰 / 親方向） |
| `tmuxkillf` | tmux セッションを fzf で複数選択して終了 |

`pj` / `pjs` は herdr の稼働状態（`herdr status server` の応答）で分岐する。herdr は
`.config/herdr/config.toml` を通じてこのdotfilesの正式な一部として管理している。

## カスタムスキル（`.claude/skills/`）

| スキル | 用途 |
|--------|------|
| analysis-reporting | 分析結果のレポート作成（Notebookセル実行結果からMarkdown化） |
| codex（agent-graph由来） | 単発のコーディング作業をCodex (gpt-6-astra) に委譲する手順 |
| creating-rules | Claude Code用Ruleの新規作成 |
| generating-commit-messages | git diffからコミットメッセージを生成 |
| grill-me | 実装前にユーザーの計画を深掘りするQ&A |
| herdr | herdr（AIエージェント向けターミナルマルチプレクサ）の操作 |
| html-slides | HTMLスライド（報告書・発表資料）の作成・修正規約 |
| import-to-claude-code | `claude import` で移せなかった設定の仕上げ |
| improving-skills-and-rules | Skills/Rulesの改善提案・更新 |
| jr-da-slides | 日本語PowerPointスライドをpython-pptxで生成 |
| plan（agent-graph由来） | 要望/Issueをタスクグラフ化し自律実行を始める手順 |
| skill-creator | 新規スキルの作成・改善・評価 |

`codex` と `plan` は `agent-graph/claude/skills/` へのシンボリックリンク。

## Rules（`.claude/rules/`）

| ファイル | 内容 |
|---------|------|
| `gh.md` | GitHub CLI（gh）運用ルール |
| `git.md` | Git運用ルール（禁止操作・コミットメッセージ規約） |
| `no-fabrication.md` | 完了報告・検証における捏造禁止 |
| `notebook.md` | Notebook出力形式 |
| `output.md` | ファイル出力ルール（ファイル名・PDF変換） |
| `polars.md` | Polars固定・Pandas禁止 |
| `python.md` | Pythonコーディング規約 |
| `role.md` | 統括リーダーとしての役割 |
| `token-compress.md` | 出力トークン圧縮 |
| `uv.md` | uv環境管理 |
| `viz.md` | Seaborn可視化ルール |

## 注意事項

- `.claude/` と `.codex/` は AI ツール用のグローバル設定（個人ルール）
- 設定変更はこのリポジトリを編集すればシンボリックリンク経由で即反映
- `.codex/hooks.json` のみシンボリックリンクではなく、`hooks.json.template` から絶対パス展開して生成する（別マシンでも動くようにするため）
