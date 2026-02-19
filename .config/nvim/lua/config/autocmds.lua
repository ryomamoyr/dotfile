-- Autocmds are automatically loaded on the VeryLazy event
-- Default autocmds that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/autocmds.lua
-- Add any additional autocmds here

-- 起動時にneo-tree + toggletermを自動で開く（IDE風3カラムレイアウト）
vim.api.nvim_create_autocmd("VimEnter", {
  callback = function()
    local is_dir = vim.fn.argc() == 0 or vim.fn.isdirectory(vim.fn.argv(0)) == 1
    if is_dir then
      vim.cmd("Neotree show")
      vim.defer_fn(function()
        require("toggleterm").toggle(1)
        -- ディレクトリで開いた場合はneo-treeにフォーカス
        vim.cmd("Neotree focus")
      end, 100)
    end
  end,
})
