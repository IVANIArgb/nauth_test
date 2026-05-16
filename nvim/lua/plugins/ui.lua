return {
  {
    "goolord/alpha-nvim",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
      local dashboard = require("alpha.themes.dashboard")
      dashboard.section.header.val = {
        "███╗   ██╗███████╗ ██████╗ ██╗   ██╗██╗███╗   ███╗",
        "████╗  ██║██╔════╝██╔═══██╗██║   ██║██║████╗ ████║",
        "██╔██╗ ██║█████╗  ██║   ██║██║   ██║██║██╔████╔██║",
        "██║╚██╗██║██╔══╝  ██║   ██║╚██╗ ██╔╝██║██║╚██╔╝██║",
        "██║ ╚████║███████╗╚██████╔╝ ╚████╔╝ ██║██║ ╚═╝ ██║",
        "╚═╝  ╚═══╝╚══════╝ ╚═════╝   ╚═══╝  ╚═╝╚═╝     ╚═╝",
      }
      dashboard.section.buttons.val = {
        dashboard.button("e", "New file", "<cmd>ene<cr>"),
        dashboard.button("f", "Find file", "<cmd>Telescope find_files<cr>"),
        dashboard.button("r", "Recent files", "<cmd>Telescope oldfiles<cr>"),
        dashboard.button("s", "Restore session", "<cmd>SessionRestore<cr>"),
        dashboard.button("q", "Quit", "<cmd>qa<cr>"),
      }
      require("alpha").setup(dashboard.opts)
    end,
  },
  {
    "nvim-neo-tree/neo-tree.nvim",
    branch = "v3.x",
    dependencies = {
      "nvim-lua/plenary.nvim",
      "nvim-tree/nvim-web-devicons",
      "MunifTanjim/nui.nvim",
    },
    config = function()
      require("neo-tree").setup({
        close_if_last_window = true,
        popup_border_style = "rounded",
        filesystem = {
          filtered_items = { hide_dotfiles = false },
          follow_current_file = { enabled = true },
          use_libuv_file_watcher = true,
        },
        window = {
          width = 34,
          mappings = { ["l"] = "open", ["h"] = "close_node" },
        },
      })
    end,
  },
  {
    "akinsho/bufferline.nvim",
    version = "*",
    dependencies = { "nvim-tree/nvim-web-devicons" },
    config = function()
      require("bufferline").setup({
        options = {
          mode = "buffers",
          diagnostics = "nvim_lsp",
          separator_style = "slant",
          always_show_bufferline = true,
          numbers = "ordinal",
          show_buffer_close_icons = true,
          show_close_icon = false,
          modified_icon = "●",
          buffer_close_icon = "",
          close_icon = "",
          diagnostics_indicator = function(_, _, diag)
            local s = ""
            if diag.error then
              s = s .. " E" .. diag.error
            end
            if diag.warning then
              s = s .. " W" .. diag.warning
            end
            return s
          end,
          offsets = {
            {
              filetype = "neo-tree",
              text = "Project",
              text_align = "left",
            },
          },
        },
      })
    end,
  },
  {
    "SmiteshP/nvim-navic",
    dependencies = { "neovim/nvim-lspconfig" },
    config = function()
      require("nvim-navic").setup({
        highlight = true,
        separator = " > ",
      })
    end,
  },
  {
    "folke/drop.nvim",
    enabled = false,
  },
  {
    "utilyre/barbecue.nvim",
    name = "barbecue",
    version = "*",
    dependencies = {
      "SmiteshP/nvim-navic",
      "nvim-tree/nvim-web-devicons",
    },
    config = function()
      require("barbecue").setup({
        attach_navic = false,
      })
    end,
  },
  {
    "folke/which-key.nvim",
    event = "VeryLazy",
    config = function()
      require("which-key").setup()
    end,
  },
  {
    "lewis6991/gitsigns.nvim",
    config = function()
      require("gitsigns").setup()
    end,
  },
  {
    "lukas-reineke/indent-blankline.nvim",
    main = "ibl",
    config = function()
      require("ibl").setup({
        indent = { char = "│" },
        scope = { enabled = false },
      })
    end,
  },
  {
    "nvim-telescope/telescope.nvim",
    dependencies = { "nvim-lua/plenary.nvim" },
    config = function()
      local telescope = require("telescope")
      telescope.setup({
        defaults = {
          layout_config = { prompt_position = "top" },
          sorting_strategy = "ascending",
          winblend = 4,
        },
      })
    end,
  },
  {
    "akinsho/toggleterm.nvim",
    version = "*",
    config = function()
      require("toggleterm").setup({
        direction = "horizontal",
        size = 12,
        open_mapping = [[<c-\>]],
        shade_terminals = true,
      })
    end,
  },
  {
    "rmagatti/auto-session",
    config = function()
      require("auto-session").setup({
        auto_restore_enabled = true,
        auto_save_enabled = true,
        auto_session_suppress_dirs = { "C:/", "C:/Users", "C:/Users/Пользователь" },
      })
    end,
  },
}
