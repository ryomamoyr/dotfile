# dotfiles

MacOSで環境構築するためのリポジトリ

## ディレクトリ構成

```
.
├── README.md                   # このファイル
├── CLAUDE.md                   # Claude Code用の設定
├── init.sh                     # 初期セットアップスクリプト
├── minimal.sh                  # 最小限のbashrc設定
├── config/                     # dotfiles設定ファイル
│   ├── .zshrc                  # ZSHシェル設定
│   ├── .alias                  # エイリアス定義
│   ├── .function               # カスタム関数定義
│   ├── .bashrc                 # Bash設定
│   └── .tmux.conf              # tmux設定
├── scripts/                    # 各種設定・管理ファイル
│   └── Brewfile               # brew bundle用パッケージ定義
├── nvim/                       # Neovim設定
└── snippets/                   # コードスニペット
    └── python.json
```

## 実行内容

`init.sh` に権限を付与

```sh
chmod +x init.sh
```

`init.sh` を実行

```sh
./init.sh
```

1. 各ソフトをインストールする

   * Xcodeのインストール
   * Homebrewのインストール
   * Nodebrewのインストール
   * uvのインストール
   * zintのインストール
     * zshのプラグインマネージャー

2. 各dotfileにシンボリックリンクを作成する

   * `config/.zshrc`のシンボリックリンクを `$HOME/.zshrc`に作成
     * zshの基本的な設定を記述
     * `config/.alias`と `config/.function`を読み込む
   * `config/.alias`のシンボリックリンクを `$HOME/.alias`に作成
     * aliasはここにすべてここに記述
   * `config/.function`のシンボリックリンクを `$HOME/.function`に作成
     * 自作定義した関数はすべてここに記述
   * `config/.tmux.conf`のシンボリックリンクを `$HOME/.tmux.conf`に作成
     * tmuxの基本的な設定
   * シンボリックリンクを設定することで各dotfileがここで編集できる

3. Homebrew で各 GUI ソフトをインストールする
   `scripts/Brewfile` を使用して GUI アプリケーションを一括インストールします。

   **インストール対象**

   | App | 用途／特徴 |
   |-----|-----------|
   | iterm2 | 高機能ターミナル。分割ペイン・マウスレス操作が快適 |
   | docker | Docker Desktop。GUI でコンテナ管理が可能 |
   | brave-browser | プライバシー重視の Chromium 系ブラウザ。広告ブロック標準 |
   | visual-studio-code | 拡張が豊富なコードエディタ／軽量 IDE |
   | cursor | AI コード補完・チャット統合版 VS Code |
   | raycast | Spotlight 代替のキーボードランチャー＋自動化ハブ |
   | rectangle | 画面スナップ・ウインドウ整列ユーティリティ |
   | karabiner-elements | キーリマップツール。Caps ⇄ Ctrl/Esc 入替え等 |
   | google-japanese-ime | 高精度の日本語入力システム |
   | slack | チームコミュニケーションツール |
   | notion | ドキュメント＋DB 管理のオールインワン Wiki |
   | microsoft-teams | 企業向けチャット／ビデオ会議（Office365 連携） |
   | zoom | 汎用ビデオ会議アプリ |

## 使用方法

### 自動セットアップ

```sh
chmod +x init.sh
./init.sh
```

### 個別セットアップ

Brewfileのみ実行する場合:

```sh
brew bundle --file=scripts/Brewfile
```
