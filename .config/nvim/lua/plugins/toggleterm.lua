-- lua/plugins/toggleterm.lua

return {
  "akinsho/toggleterm.nvim",
  version = "*",
  opts = {
    direction = "vertical",
    size = function(term)
      return math.floor(vim.o.columns * 0.3)
    end,
    open_mapping = [[<c-\>]],
  },
}