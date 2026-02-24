-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Add any additional options here

-- Python 3 プロバイダを有効化（molten-nvim に必要）
vim.g.loaded_python3_provider = nil
vim.g.python3_host_prog = vim.fn.expand("~/.virtualenvs/neovim/bin/python")
