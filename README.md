# dotfiles

macOS環境のセットアップを自動化するdotfilesコレクションです。

## セットアップ

### フルセットアップ

```bash
chmod +x setup.sh
./setup.sh
```

### 最小限セットアップ

```bash
chmod +x setup-minimal.sh
./setup-minimal.sh
```

## セットアップ内容

### インストールされるツール

`setup.sh`は以下のツールを自動的にインストールします：

1. **Xcode Command Line Tools** - macOS開発に必要な基本ツール
2. **Homebrew** - macOS用パッケージマネージャー
3. **Nodebrew** - Node.js バージョン管理ツール
4. **uv** - Python パッケージマネージャー
5. **Zinit** - Zsh プラグインマネージャー
6. **git** - バージョン管理システム
7. **zsh-git-prompt** - Gitリポジトリ情報を表示するZshプロンプト

### 作成されるシンボリックリンク

セットアップ時に以下のファイルがホームディレクトリにリンクされます：

```
shell/.alias       → ~/.alias
shell/.function    → ~/.function
shell/.zshrc       → ~/.zshrc
shell/.bashrc      → ~/.bashrc
shell/.tmux.conf   → ~/.tmux.conf
.config/alacritty/alacritty.toml → ~/.config/alacritty/alacritty.toml
.config/alacritty/start_tmux.sh  → ~/.config/alacritty/start_tmux.sh
.config/nvim       → ~/.config/nvim
.snippets          → ~/Library/Application Support/Cursor/User/snippets
```

## ディレクトリ構成

```
.
├── README.md                   # このファイル
├── CLAUDE.md                   # Claude Code用の設定
├── setup.sh                    # フルセットアップスクリプト
├── setup-minimal.sh            # 最小限のセットアップスクリプト
├── .Brewfile                   # Homebrew GUIアプリ定義
├── shell/                      # シェル関連設定
│   ├── .zshrc                  # Zsh設定（Zinit、補完、履歴など）
│   ├── .alias                  # コマンドエイリアス
│   ├── .function               # カスタム関数
│   ├── .bashrc                 # Bash設定
│   └── .tmux.conf              # tmux設定
├── .config/
│   ├── alacritty/              # Alacrittyターミナル設定
│   └── nvim/                   # Neovim設定（LazyVimベース）
└── .snippets/                  # VSCode形式コードスニペット
```

## パッケージ（.Brewfile）

`.Brewfile`で管理されるアプリケーション・ツール：

### GUIアプリケーション（cask）

| アプリ | 用途 |
|--------|------|
| cursor | AI統合版VSCode |
| alacritty | 高速GPUアクセラレーション対応ターミナル |
| tmux | ターミナルマルチプレクサー |
| docker | Docker Desktop |
| brave-browser | プライバシー重視ブラウザ |
| google-japanese-ime | 日本語入力 |
| raycast | キーボードランチャー |
| rectangle | ウィンドウ管理 |
| karabiner-elements | キーリマップ |
| slack | チームコミュニケーション |
| notion | ドキュメント管理 |
| microsoft-teams | ビデオ会議 |
| zoom | ビデオ会議 |

### CLIツール（brew）

| ツール | 用途 |
|--------|------|
| git | バージョン管理システム |
| stow | シンボリックリンク管理 |
| neovim | モダンVim |
| ripgrep | 高速grep代替 |
| eza | lsコマンド代替 |

個別インストールの場合：

```bash
brew bundle --file=.Brewfile
```

## 使用後

セットアップ完了後はターミナルを再起動して設定を反映してください。
