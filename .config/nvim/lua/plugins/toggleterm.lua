-- lua/plugins/toggleterm.lua

return {
  "akinsho/toggleterm.nvim",
  version = "*",
  opts = {
    -- ここでターミナルの設定ができます
    direction = "float", -- フローティングウィンドウで開く
    open_mapping = [[<c-\>]], -- インサートモードでも開けるようにする設定
  },
}