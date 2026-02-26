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
│   ├── .function               # カスタム関数定義（pj, jk, tm 等）
│   ├── .bashrc                 # Bash設定
│   └── .tmux.conf              # tmux設定
├── .config/                    # アプリケーション設定
│   ├── ghostty/                # Ghostty設定（tmux自動起動含む）
│   ├── nvim/                   # Neovim設定（LazyVimベース）
│   └── karabiner/              # Karabiner設定
├── .snippets/                  # コードスニペット（Cursor用）
├── .claude/                    # Claude Code グローバル設定
│   ├── CLAUDE.md               # 個人共通ルール
│   ├── settings.json           # Claude Code設定
│   ├── rules/                  # トピック別ルール
│   │   ├── 00-uv.md            # uv環境管理
│   │   ├── 10-python.md        # Pythonコーディング規約
│   │   ├── 20-polars.md        # Polars固定・Pandas禁止
│   │   ├── 30-viz.md           # Seaborn可視化ルール
│   │   ├── 40-notebook.md      # Notebook出力形式
│   │   └── 50-git.md           # Git運用ルール
│   └── skills/                 # カスタムスキル
│       ├── creating-rules/
│       ├── creating-skills/
│       ├── generating-commit-messages/
│       ├── improving-skills-and-rules/
│       └── jr-da-slides/
└── .codex/                     # OpenAI Codex グローバル設定
    ├── AGENTS.md               # 個人共通ルール
    └── config.toml
```

## セットアップ

```sh
git clone https://github.com/ryomamoyr/dotfile.git ~/00_project/dotfiles
cd ~/00_project/dotfiles
./setup.sh
brew bundle --file=~/Brewfile
```

`setup.sh` の実行内容：
1. Xcode Command Line Tools / Homebrew / Nodebrew / uv / Zinit をインストール
2. 全設定ファイルのシンボリックリンクを作成

## シンボリックリンク一覧

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
| `.snippets/` | `~/Library/Application Support/Cursor/User/snippets/` |
| `Brewfile` | `~/Brewfile` |
| `.claude/CLAUDE.md` | `~/.claude/CLAUDE.md` |
| `.claude/settings.json` | `~/.claude/settings.json` |
| `.claude/rules/*.md` | `~/.claude/rules/` |
| `.claude/skills/` | `~/.claude/skills/` |
| `.codex/AGENTS.md` | `~/.codex/AGENTS.md` |
| `.codex/config.toml` | `~/.codex/config.toml` |

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
| `pj [名前]` | tmux 作業ウィンドウ作成（新規 → リネーム → 左右分割） |
| `jk [名前]` | Jupyter カーネル登録（uv プロジェクト用） |
| `tm` | tmux セッションを fzf で選択して切替 |
| `vfz` | fzf でファイル検索 → Neovim で開く |
| `ifz` | 画像を fzf プレビュー → timg で表示 |
| `fd` / `fda` / `fdr` | fzf でディレクトリ移動 |

## 注意事項

- `.claude/` と `.codex/` は AI ツール用のグローバル設定（個人ルール）
- 設定変更はこのリポジトリを編集すればシンボリックリンク経由で即反映
