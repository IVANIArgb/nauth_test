local function trim(s)
  return (s:gsub("^%s+", ""):gsub("%s+$", ""))
end

local function detect_python312()
  if vim.fn.executable("py") == 1 then
    local out = vim.fn.systemlist('py -3.12 -c "import sys; print(sys.executable)"')
    if vim.v.shell_error == 0 and out and out[1] and out[1] ~= "" then
      local p = trim(out[1])
      if vim.fn.filereadable(p) == 1 then
        return p
      end
    end
  end
  return nil
end

local python312 = detect_python312()
if python312 then
  vim.g.python3_host_prog = python312
end
