return {
  -- image.nvim: Kitty Graphics Protocolでインライン画像表示
  {
    "3rd/image.nvim",
    ft = { "python", "markdown" },
    opts = {
      backend = "kitty",
      integrations = {
        markdown = { enabled = true },
      },
      max_width = 100,
      max_height = 30,
      tmux_show_only_in_active_window = true,
    },
  },

  -- molten-nvim: Jupyter実行エンジン
  {
    "benlubas/molten-nvim",
    version = "^1.0.0",
    build = ":UpdateRemotePlugins",
    dependencies = { "3rd/image.nvim" },
    ft = { "python" },
    init = function()
      vim.g.molten_image_provider = "image.nvim"
      vim.g.molten_output_win_max_height = 20
      vim.g.molten_auto_open_output = false
      vim.g.molten_virt_text_output = true
      vim.g.molten_virt_lines_off_by_1 = true
    end,
  },

  -- jupytext.nvim: .ipynb → .py 自動変換
  {
    "GCBallesteros/jupytext.nvim",
    lazy = false,
    opts = {
      style = "hydrogen",
      output_extension = "auto",
      force_ft = "python",
    },
  },

  -- NotebookNavigator.nvim: セル移動・実行
  {
    "GCBallesteros/NotebookNavigator.nvim",
    dependencies = {
      "echasnovski/mini.comment",
      "echasnovski/mini.hipatterns",
      "benlubas/molten-nvim",
    },
    ft = { "python" },
    config = function()
      local nn = require("notebook-navigator")
      nn.setup({
        repl_provider = "molten",
      })
      -- setup() 後に minihipatterns_spec が生成されるので、ここで mini.hipatterns を設定
      require("mini.hipatterns").setup({
        highlighters = {
          notebook_cell = nn.minihipatterns_spec,
        },
      })
    end,
    keys = {
      { "]h", function() require("notebook-navigator").move_cell("d") end, desc = "次のセルへ" },
      { "[h", function() require("notebook-navigator").move_cell("u") end, desc = "前のセルへ" },
      { "<leader>jx", "<cmd>lua require('notebook-navigator').run_cell()<cr>", desc = "セルを実行" },
      { "<leader>ja", "<cmd>lua require('notebook-navigator').run_and_move()<cr>", desc = "セルを実行して次へ" },
    },
  },
}
