#!/bin/bash
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NO_COLOR='\033[0m'
msg() { echo -e "${YELLOW}$1${NO_COLOR}"; }
ok()  { echo -e "${GREEN}$1${NO_COLOR}"; }

# ----------------------------------------
# Homebrew インストール
# ----------------------------------------
if ! command -v brew &> /dev/null; then
    msg "Homebrew が見つかりません。インストールします..."
    NONINTERACTIVE=1 /bin/bash -c \
      "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # Apple Silicon / Intel でパスが違うので判定
    if [[ -d /opt/homebrew ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
    else
        eval "$(/usr/local/bin/brew shellenv)"
        echo 'eval "$(/usr/local/bin/brew shellenv)"' >> "$HOME/.zprofile"
    fi
    ok "Homebrew をインストールしました。"
else
    ok "Homebrew はすでにインストールされています。"
fi

# ----------------------------------------
# GUI (Cask) アプリ
# ----------------------------------------
cask_apps=(
    slack
    notion
    microsoft-teams
    zoom
    google-japanese-ime
    visual-studio-code
    cursor
    iterm2                # 高速レンダリングと分割タブが便利な高機能ターミナル
    docker                # コンテナ実行・管理 GUI 付きの公式 Docker Desktop
    brave-browser         # 広告ブロック標準搭載のプライバシー重視 Chromium 派生ブラウザ
    raycast               # ランチャー
    rectangle             # Win 的なスナップ操作が可能になるウインドウ整列ユーティリティ
    karabiner-elements    # キーボードリマップツール
)


for app in "${cask_apps[@]}"; do
  if ! brew list --cask "$app" &> /dev/null; then
    msg "Installing ${app}..."
    brew install --cask "$app"
  else
    ok "${app} is already installed."
  fi
done
