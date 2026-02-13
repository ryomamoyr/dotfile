#!/bin/bash

# 色のコード
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NO_COLOR='\033[0m'

# Xcode Command Line Toolsが未インストールの場合にインストール
if ! xcode-select -p &> /dev/null; then
    echo -e "${YELLOW}Installing Xcode Command Line Tools...${NO_COLOR}"
    xcode-select --install
else
    echo -e "${GREEN}Xcode Command Line Tools are already installed.${NO_COLOR}"
fi

# Homebrewをインストール
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}Installing Homebrew...${NO_COLOR}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> /Users/$(whoami)/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo -e "${GREEN}Homebrew is already installed.${NO_COLOR}"
fi

# Nodebrewをインストール
if ! command -v nodebrew &> /dev/null; then
    echo -e "${YELLOW}Installing Nodebrew...${NO_COLOR}"
    curl -L git.io/nodebrew | perl - setup
    export PATH="$HOME/.nodebrew/current/bin:$PATH"
    nodebrew install-binary stable
    nodebrew use stable
else
    echo -e "${GREEN}Nodebrew is already installed.${NO_COLOR}"
fi

# uvをインストール
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}Installing uv...${NO_COLOR}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
else
    echo -e "${GREEN}uv is already installed.${NO_COLOR}"
fi

# Zinitが未インストールの場合のみインストール
if [ ! -f "$HOME/.local/share/zinit/zinit.git/zinit.zsh" ]; then
    echo -e "${YELLOW}Installing Zinit...${NO_COLOR}"
    bash -c "$(curl --fail --show-error --silent --location https://raw.githubusercontent.com/zdharma-continuum/zinit/HEAD/scripts/install.sh)"
else
    echo -e "${GREEN}Zinit is already installed.${NO_COLOR}"
fi

# Homebrewをインストール
if ! brew list git &> /dev/null; then
    echo -e "${YELLOW}Installing git...${NO_COLOR}"
    brew install git
else
    echo -e "${GREEN}git is already installed.${NO_COLOR}"
fi

if ! brew list zsh-git-prompt &> /dev/null; then
    echo -e "${YELLOW}Installing zsh-git-prompt...${NO_COLOR}"
    brew install zsh-git-prompt
else
    echo -e "${GREEN}zsh-git-prompt is already installed.${NO_COLOR}"
fi

mkdir -p "$HOME/.config/alacritty"
mkdir -p "$HOME/.config/karabiner"
mkdir -p "$HOME/.claude/rules"
mkdir -p "$HOME/.codex"
# シンボリックリンクを作成
ln -sf "$(pwd)/shell/.alias" "$HOME/.alias"
ln -sf "$(pwd)/shell/.function" "$HOME/.function"
ln -sf "$(pwd)/shell/.zshrc" "$HOME/.zshrc"
ln -sf "$(pwd)/shell/.bashrc" "$HOME/.bashrc"
ln -sf "$(pwd)/shell/.tmux.conf" "$HOME/.tmux.conf"
ln -sf "$(pwd)/.config/nvim" "$HOME/.config/nvim"
ln -sf "$(pwd)/.config/alacritty/alacritty.toml" "$HOME/.config/alacritty/alacritty.toml"
ln -sf "$(pwd)/.config/alacritty/start_tmux.sh" "$HOME/.config/alacritty/start_tmux.sh"
rm -rf "$HOME/Library/Application Support/Cursor/User/snippets"
ln -sf "$(pwd)/.snippets" "$HOME/Library/Application Support/Cursor/User/snippets"
ln -sf "$(pwd)/Brewfile" "$HOME/Brewfile"
ln -sf "$(pwd)/.claude/CLAUDE.md" "$HOME/.claude/CLAUDE.md"
ln -sf "$(pwd)/.claude/settings.json" "$HOME/.claude/settings.json"
for f in "$(pwd)/.claude/rules"/*.md; do
    ln -sf "$f" "$HOME/.claude/rules/$(basename "$f")"
done
rm -rf "$HOME/.claude/skills"
ln -sf "$(pwd)/.claude/skills" "$HOME/.claude/skills"
ln -sf "$(pwd)/.codex/AGENTS.md" "$HOME/.codex/AGENTS.md"
ln -sf "$(pwd)/.codex/config.toml" "$HOME/.codex/config.toml"

chmod +x "$HOME/.config/alacritty/start_tmux.sh"

echo -e "${GREEN}Installation is complete and symbolic links have been created.${NO_COLOR}"
echo -e "${YELLOW}Please restart your terminal to apply the changes.${NO_COLOR}"
