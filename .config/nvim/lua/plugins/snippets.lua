return {
  {
    "saghen/blink.cmp",
    opts = {
      keymap = {
        ["<Tab>"] = { "snippet_forward", "select_and_accept", "fallback" },
        ["<S-Tab>"] = { "snippet_backward", "fallback" },
      },
      sources = {
        providers = {
          snippets = {
            opts = {
              search_paths = { vim.fn.stdpath("config") .. "/snippets" },
            },
          },
        },
      },
    },
  },
}
