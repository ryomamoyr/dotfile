#!/bin/bash

ln -sf "$(pwd)/shell/.bashrc" "$HOME/.bashrc"
ln -sf "$(pwd)/shell/.tmux.conf" "$HOME/.tmux.conf"
mkdir -p "$HOME/.config"
ln -sf "$(pwd)/nvim" "$HOME/.config/nvim"

echo "# This is a symbolic link to the .bashrc file in the current directory" >> "$(pwd)/shell/.bashrc"
