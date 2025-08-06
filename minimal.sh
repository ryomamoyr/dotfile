#!/bin/bash

if [ -f "$HOME/.bashrc" ]; then
    mv "$HOME/.bashrc" "$HOME/.bashrc.bk"
fi

if [ -f "$HOME/.tmux.conf" ]; then
    mv "$HOME/.tmux.conf" "$HOME/.tmux.conf.bk"
fi

if [ -d "$HOME/.config/nvim" ]; then
    mv "$HOME/.config/nvim" "$HOME/.config/nvim.bk"
fi

ln -sf "$(pwd)/.bashrc" "$HOME/.bashrc"
ln -sf "$(pwd)/.tmux.conf" "$HOME/.tmux.conf"
mkdir -p "$HOME/.config"
ln -sf "$(pwd)/nvim" "$HOME/.config/nvim"

echo "# This is a symbolic link to the .bashrc file in the current directory" >> "$(pwd)/.bashrc"
