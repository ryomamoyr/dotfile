-- リーダーキー設定（lazy.nvim より先に必要）
vim.g.mapleader = " "
vim.g.maplocalleader = " "

-- bootstrap lazy.nvim, LazyVim and your plugins
require("config.lazy")
