local run_commands = {
  python = function(file)
    if vim.fn.executable("python") == 1 then
      return "python " .. vim.fn.shellescape(file)
    end
    return "py " .. vim.fn.shellescape(file)
  end,
  javascript = function(file)
    return "node " .. vim.fn.shellescape(file)
  end,
  typescript = function(file)
    if vim.fn.executable("bun") == 1 then
      return "bun run " .. vim.fn.shellescape(file)
    end
    return "npx ts-node " .. vim.fn.shellescape(file)
  end,
  sh = function(file)
    return "bash " .. vim.fn.shellescape(file)
  end,
  lua = function(file)
    return "lua " .. vim.fn.shellescape(file)
  end,
  c = function(file)
    local out = vim.fn.stdpath("data") .. "/run_c.exe"
    return "gcc " .. vim.fn.shellescape(file) .. " -o " .. vim.fn.shellescape(out) .. " && " .. vim.fn.shellescape(out)
  end,
  cpp = function(file)
    local out = vim.fn.stdpath("data") .. "/run_cpp.exe"
    return "g++ " .. vim.fn.shellescape(file) .. " -std=c++17 -O2 -o " .. vim.fn.shellescape(out) .. " && " .. vim.fn.shellescape(out)
  end,
  go = function(file)
    return "go run " .. vim.fn.shellescape(file)
  end,
  rust = function(file)
    return "rustc " .. vim.fn.shellescape(file) .. " -o " .. vim.fn.shellescape(vim.fn.stdpath("data") .. "/run_rust.exe") .. " && " .. vim.fn.shellescape(vim.fn.stdpath("data") .. "/run_rust.exe")
  end,
}

local function executable_or_warn(binary)
  if vim.fn.executable(binary) == 1 then
    return true
  end
  vim.notify("Не найдено в PATH: " .. binary, vim.log.levels.ERROR)
  return false
end

local function run_current_file()
  local file = vim.api.nvim_buf_get_name(0)
  if file == "" then
    vim.notify("Сначала сохрани файл", vim.log.levels.WARN)
    return
  end

  vim.cmd("write")
  local ft = vim.bo.filetype
  local cmd_builder = run_commands[ft]
  if not cmd_builder then
    vim.notify("Нет команды запуска для filetype: " .. ft, vim.log.levels.WARN)
    return
  end

  if ft == "python" then
    if vim.fn.executable("python") ~= 1 and vim.fn.executable("py") ~= 1 then
      vim.notify("Не найдено в PATH: python или py", vim.log.levels.ERROR)
      return
    end
  end
  if ft == "javascript" and not executable_or_warn("node") then
    return
  end
  if ft == "typescript" and vim.fn.executable("bun") ~= 1 and vim.fn.executable("node") ~= 1 then
    vim.notify("Для TypeScript нужен bun или node/ts-node", vim.log.levels.ERROR)
    return
  end

  local command = cmd_builder(file)
  vim.cmd("botright 12new")
  vim.fn.termopen(command)
  vim.cmd("startinsert")
end

vim.api.nvim_create_user_command("RunFile", run_current_file, {
  desc = "Run current file in terminal split",
})

vim.api.nvim_create_autocmd("TextYankPost", {
  group = vim.api.nvim_create_augroup("highlight_yank", { clear = true }),
  callback = function()
    vim.highlight.on_yank({ timeout = 120 })
  end,
})
