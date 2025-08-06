# dotfiles

MacOSで環境構築するためのリポジトリ

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

   * `.zshrc`のシンボリックリンクを `$HOME/.zshrc`に作成
     * zshの基本的な設定を記述
     * `.alias`と `.function`を読み込む
   * `.alias`のシンボリックリンクを `$HOME/.alias`に作成
     * aliasはここにすべてここに記述
   * `.function`のシンボリックリンクを `$HOME/.function`に作成
     * 自作定義した関数はすべてここに記述
   * `.tmux.conf`のシンボリックリンクを `$HOME/.tmux.conf`に作成
     * tmuxの基本的な設定
   * シンボリックリンクを設定することで各dotfileがここで編集できる

3. Homebrew で各 GUI ソフトをインストールする
   `brew_packages.sh` が Homebrew のセットアップとアプリ導入を一括で行います。


   **インストール対象（cask_apps 配列）**

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

   ```sh
    chmod +x brew_packages.sh
   ```

   ```sh
   ./brew_packages.sh
