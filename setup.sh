#!/bin/bash

# Color codes
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NO_COLOR='\033[0m'

# Install Xcode Command Line Tools if not installed
if ! xcode-select -p &> /dev/null; then
    echo -e "${YELLOW}Installing Xcode Command Line Tools...${NO_COLOR}"
    xcode-select --install
else
    echo -e "${GREEN}Xcode Command Line Tools are already installed.${NO_COLOR}"
fi

# Install Homebrew
if ! command -v brew &> /dev/null; then
    echo -e "${YELLOW}Installing Homebrew...${NO_COLOR}"
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> /Users/$(whoami)/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo -e "${GREEN}Homebrew is already installed.${NO_COLOR}"
fi

# Install Nodebrew
if ! command -v nodebrew &> /dev/null; then
    echo -e "${YELLOW}Installing Nodebrew...${NO_COLOR}"
    curl -L git.io/nodebrew | perl - setup
    export PATH="$HOME/.nodebrew/current/bin:$PATH"
    nodebrew install-binary stable
    nodebrew use stable
else
    echo -e "${GREEN}Nodebrew is already installed.${NO_COLOR}"
fi
# Install uv
if ! command -v uv &> /dev/null; then
    echo -e "${YELLOW}Installing uv...${NO_COLOR}"
    curl -LsSf https://astral.sh/uv/install.sh | sh
else
    echo -e "${GREEN}uv is already installed.${NO_COLOR}"
fi

# Install Zinit
if [ ! -f "$HOME/.local/share/zinit/zinit.git/zinit.zsh" ]; then
    echo -e "${YELLOW}Installing Zinit...${NO_COLOR}"
    mkdir -p "$HOME/.local/share/zinit"
    chmod g-rwX "$HOME/.local/share/zinit"
    git clone https://github.com/zdharma-continuum/zinit "$HOME/.local/share/zinit/zinit.git"
else
    echo -e "${GREEN}Zinit is already installed.${NO_COLOR}"
fi

# Install necessary Homebrew packages
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

# Backup existing files and create symbolic links
backup_message=""
timestamp=$(date +%Y%m%d%H%M)

if [ -f "$HOME/.alias" ]; then
    mv "$HOME/.alias" "$HOME/.alias.bk.$timestamp"
    backup_message+="Backup created for .alias as .alias.bk.$timestamp\n"
fi

if [ -f "$HOME/.function" ]; then
    mv "$HOME/.function" "$HOME/.function.bk.$timestamp"
    backup_message+="Backup created for .function as .function.bk.$timestamp\n"
fi

if [ -f "$HOME/.zshrc" ]; then
    mv "$HOME/.zshrc" "$HOME/.zshrc.bk.$timestamp"
    backup_message+="Backup created for .zshrc as .zshrc.bk.$timestamp\n"
fi

if [ -f "$HOME/.tmux.conf" ]; then
    mv "$HOME/.tmux.conf" "$HOME/.tmux.conf.bk.$timestamp"
    backup_message+="Backup created for .tmux.conf as .tmux.conf.bk.$timestamp\n"
fi

if [ -d "$HOME/.config/nvim" ]; then
    mv "$HOME/.config/nvim" "$HOME/.config/nvim.bk.$timestamp"
    backup_message+="Backup created for .config/nvim as .config/nvim.bk.$timestamp\n"
fi

ln -sf "$(pwd)/config/.alias" "$HOME/.alias"
ln -sf "$(pwd)/config/.function" "$HOME/.function"
ln -sf "$(pwd)/config/.zshrc" "$HOME/.zshrc"
ln -sf "$(pwd)/config/.tmux.conf" "$HOME/.tmux.conf"
mkdir -p "$HOME/.config"
ln -sf "$(pwd)/nvim" "$HOME/.config/nvim"
ln -sf "$(pwd)/snippets" "$HOME/Library/Application Support/Cursor/User/snippets"

# ----------------------------------------
# Brewfile を使用したパッケージインストール
# ----------------------------------------
if [[ -f "scripts/Brewfile" ]]; then
    echo -e "${YELLOW}Brewfile を使用してパッケージをインストールします...${NO_COLOR}"
    brew bundle --file=scripts/Brewfile
    echo -e "${GREEN}Brewfile からのインストールが完了しました。${NO_COLOR}"
else
    echo -e "${YELLOW}Brewfile が見つかりません。スキップします。${NO_COLOR}"
fi

echo -e "${GREEN}Installation is complete and symbolic links have been created.${NO_COLOR}"

if [ -n "$backup_message" ]; then
    echo -e "${YELLOW}$backup_message${NO_COLOR}"
fi

echo -e "${YELLOW}Please add any necessary settings to .zshrc${NO_COLOR}"
