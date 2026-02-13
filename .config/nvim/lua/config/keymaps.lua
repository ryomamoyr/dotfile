function RunCurrentFile()
  local buftype = vim.bo.buftype
  if buftype ~= "" then
    vim.notify("実行可能なファイルではありません", vim.log.levels.WARN)
    return
  end

  -- 実行前にファイルを保存
  if vim.bo.modified then
    vim.cmd("silent write")
  end

  local filetype = vim.bo.filetype
  local filepath = vim.fn.expand("%:p")
  local command

  if filetype == "python" then
    command = "uv run " .. filepath
  elseif filetype == "sh" then
    command = "bash " .. filepath
  elseif filetype == "javascript" then
    command = "node " .. filepath
  elseif filetype == "go" then
    command = "go run " .. filepath
  else
    vim.notify("このファイルタイプ用の実行コマンドがありません: " .. filetype, vim.log.levels.WARN)
    return
  end

  vim.cmd("TermExec cmd='" .. command .. "' direction=vertical go_back=0")
  vim.defer_fn(function()
    vim.cmd("startinsert")
  end, 100)
end

-- これ以降に local keymap = vim.keymap.set ... の記述が続く
local keymap = vim.keymap.set
local opts = { silent = true, noremap = true }

-- リーダーキーをスペースキーに設定 (LazyVimのデフォルト)
vim.g.mapleader = " "
vim.g.maplocalleader = " "

-- モード設定
-- jjでインサートモードを抜ける (押しやすい)
keymap("i", "jj", "<Esc>", { desc = "インサートモードを抜ける" })

-- 基本的な編集操作
keymap("v", "<", "<gv", opts)
keymap("v", ">", ">gv", opts)

-- Alt + j/k で選択行を上下に移動
keymap("n", "<A-j>", ":m .+1<CR>==", { desc = "行を下に移動" })
keymap("n", "<A-k>", ":m .-2<CR>==", { desc = "行を上に移動" })
keymap("v", "<A-j>", ":m '>+1<CR>gv=gv", { desc = "選択範囲を下に移動" })
keymap("v", "<A-k>", ":m '<-2<CR>gv=gv", { desc = "選択範囲を上に移動" })

-- Ctrl+sで保存
keymap({ "i", "n", "v" }, "<C-s>", "<cmd>w<cr><esc>", { desc = "ファイルを保存" })

-- Escキー2回でハイライトを消す
keymap("n", "<Esc><Esc>", "<cmd>nohlsearch<CR>", opts)

-- ウィンドウ分割
keymap("n", "<leader>sv", "<C-w>v", { desc = "垂直にウィンドウを分割" }) -- split vertical
keymap("n", "<leader>sh", "<C-w>s", { desc = "水平にウィンドウを分割" }) -- split horizontal

-- ウィンドウ間の移動
keymap("n", "<C-h>", "<C-w>h", { desc = "左のウィンドウへ移動" })
keymap("n", "<C-j>", "<C-w>j", { desc = "下のウィンドウへ移動" })
keymap("n", "<C-k>", "<C-w>k", { desc = "上のウィンドウへ移動" })
keymap("n", "<C-l>", "<C-w>l", { desc = "右のウィンドウへ移動" })

-- バッファの操作
keymap("n", "<S-l>", "<cmd>bnext<CR>", { desc = "次のバッファへ" })
keymap("n", "<S-h>", "<cmd>bprevious<CR>", { desc = "前のバッファへ" })
keymap("n", "<leader>bd", "<cmd>bdelete<CR>", { desc = "現在のバッファを閉じる" }) -- buffer delete

-- その他
keymap("n", "<leader>'", "<cmd>ToggleTerm<cr>", { desc = "ターミナルを開く/閉じる" })
