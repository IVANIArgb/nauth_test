return {
  {
    "nvim-treesitter/nvim-treesitter",
    build = ":TSUpdate",
    config = function()
      require("nvim-treesitter.configs").setup({
        ensure_installed = {
          "bash",
          "c",
          "cpp",
          "go",
          "lua",
          "python",
          "rust",
          "vim",
          "vimdoc",
          "javascript",
          "typescript",
        },
        highlight = { enable = true },
        indent = { enable = true },
      })
    end,
  },
  {
    "nvim-lualine/lualine.nvim",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
      require("lualine").setup({
        options = {
          theme = "dracula",
          section_separators = "",
          component_separators = "",
        },
      })
    end,
  },
  {
    "Mofiqul/dracula.nvim",
    priority = 1000,
    config = function()
      vim.cmd.colorscheme("dracula")
    end,
  },
}
