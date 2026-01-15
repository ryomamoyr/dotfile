# dotfiles

MacOSで環境構築するためのリポジトリ

## プロジェクト構成

```
.
├── README.md                   # このファイル
├── setup.sh                    # 初期セットアップスクリプト（フル）
├── setup-minimal.sh            # 最小限のセットアップスクリプト
├── Brewfile                    # brew bundle用パッケージ定義
├── shell/                      # シェル関連設定ファイル
│   ├── .zshrc                  # ZSHシェル設定
│   ├── .alias                  # エイリアス定義
│   ├── .function               # カスタム関数定義
│   ├── .bashrc                 # Bash設定
│   └── .tmux.conf              # tmux設定
├── .config/                    # アプリケーション設定
│   ├── alacritty/              # Alacritty設定
│   ├── nvim/                   # Neovim設定（LazyVimベース）
│   └── karabiner/              # Karabiner設定
├── .snippets/                  # コードスニペット（Cursor用）
│   ├── python.json             # Pythonスニペット
│   └── markdown.json           # Markdownスニペット
├── .claude/                    # Claude Code グローバル設定
│   ├── CLAUDE.md               # 個人共通ルール
│   ├── settings.json           # Claude Code設定
│   ├── rules/                  # 詳細ルール（uv, Python, Polars等）
│   └── skills/                 # カスタムスキル定義
└── .codex/                     # OpenAI Codex グローバル設定
    └── AGENTS.md               # 個人共通ルール
```

## セットアップ手順

### フルセットアップ

```sh
./setup.sh
```

### 最小限セットアップ

```sh
./setup-minimal.sh
```

## setup.shの実行内容

### 1. 各ソフトウェアをインストール

- **Xcode Command Line Tools**: 開発ツールの基盤
- **Homebrew**: macOSパッケージマネージャー
- **Nodebrew**: Node.jsバージョン管理
- **uv**: 高速Python パッケージマネージャー
- **Zinit**: zshプラグインマネージャー
- **Git**: バージョン管理システム
- **zsh-git-prompt**: Gitステータス表示

### 2. 設定ファイルのシンボリックリンク作成

| 元ファイル | リンク先 | 説明 |
|------------|----------|------|
| `shell/.zshrc` | `~/.zshrc` | zsh基本設定、.aliasと.functionを読み込み |
| `shell/.alias` | `~/.alias` | コマンドエイリアス定義 |
| `shell/.function` | `~/.function` | カスタム関数定義 |
| `shell/.bashrc` | `~/.bashrc` | Bash設定 |
| `shell/.tmux.conf` | `~/.tmux.conf` | tmux設定 |
| `.config/alacritty/alacritty.toml` | `~/.config/alacritty/alacritty.toml` | Alacritty設定 |
| `.config/alacritty/start_tmux.sh` | `~/.config/alacritty/start_tmux.sh` | tmux起動スクリプト |
| `.config/nvim/` | `~/.config/nvim/` | Neovim設定 |
| `.config/karabiner/karabiner.json` | `~/.config/karabiner/karabiner.json` | キーリマップ設定 |
| `.snippets/` | `~/Library/Application Support/Cursor/User/snippets/` | Cursorスニペット |
| `Brewfile` | `~/Brewfile` | brew bundle用パッケージ定義 |
| `.claude/CLAUDE.md` | `~/.claude/CLAUDE.md` | Claude Code共通ルール |
| `.claude/settings.json` | `~/.claude/settings.json` | Claude Code設定 |
| `.claude/rules/*.md` | `~/.claude/rules/` | Claude Code詳細ルール |
| `.claude/skills/*/` | `~/.claude/skills/` | Claude Codeカスタムスキル |
| `.codex/AGENTS.md` | `~/.codex/AGENTS.md` | Codex共通ルール |

### 3. Homebrewパッケージのインストール

`Brewfile`を使用して必要なCLIツールとGUIアプリケーションを一括インストール:

```sh
brew bundle
```

## 主要な機能

### シェル設定
- **Zinit**: 高速zshプラグインマネージャー
- **カスタムエイリアス**: よく使うコマンドの短縮形
- **カスタム関数**: `plamo_translate`など便利な関数群
- **Git統合**: プロンプトにGitステータス表示

### ターミナル環境
- **Alacritty**: GPU加速ターミナルエミュレータ
- **tmux**: ターミナルマルチプレクサ、セッション管理
- **カスタムキーバインド**: 効率的な操作のための設定

### 開発環境
- **Neovim**: LazyVimベースのモダンなエディタ設定
- **Cursor**: AI統合開発環境のスニペット連携
- **Karabiner**: キーリマップによる効率化

## 注意事項

- 既存の設定ファイルは自動的にバックアップされます
- セットアップ後は新しいターミナルセッションで設定が有効になります
- 個別にファイルを編集したい場合は、このリポジトリ内のファイルを直接編集してください（シンボリックリンクにより反映されます）
