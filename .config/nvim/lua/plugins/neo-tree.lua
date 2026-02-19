return {
  "nvim-neo-tree/neo-tree.nvim",
  opts = {
    window = {
      width = 48,
      mappings = {
        ["<cr>"] = "open",
      },
    },
    filesystem = {
      filtered_items = { visible = true, hide_dotfiles = false },
      use_libuv_file_watcher = true,
    },
    default_component_configs = {
      indent = { with_markers = true, indent_marker = "│", last_indent_marker = "└" },
      git_status = {
        symbols = { added = "✚", modified = "●", deleted = "✖", renamed = "➜", untracked = "★" },
      },
    },
  },
}
