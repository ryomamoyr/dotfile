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
# Brewfile を使用したパッケージインストール
# ----------------------------------------
if [[ -f "Brewfile" ]]; then
    msg "Brewfile を使用してパッケージをインストールします..."
    brew bundle --file=Brewfile
    ok "Brewfile からのインストールが完了しました。"
else
    msg "Brewfile が見つかりません。スキップします。"
fi
