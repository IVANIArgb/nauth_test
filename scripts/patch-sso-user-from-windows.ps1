#Requires -Version 5.1
# If .env still has SSO_DEFAULT_USER=testadmin, set to current Windows username.
$ErrorActionPreference = "SilentlyContinue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envPath = Join-Path $root ".env"
if (-not (Test-Path $envPath)) { exit 0 }

$winUser = if ($env:USERNAME) { $env:USERNAME.Trim() } else { "" }
if (-not $winUser) { exit 0 }

$lines = Get-Content $envPath -Encoding UTF8
$out = @()
$found = $false
$changed = $false
foreach ($line in $lines) {
    if ($line -match '^\s*SSO_DEFAULT_USER\s*=\s*(.*)$') {
        $found = $true
        $cur = $matches[1].Trim()
        if ($cur -eq "" -or $cur -ieq "testadmin") {
            $out += "SSO_DEFAULT_USER=$winUser"
            $changed = $true
            Write-Host "SSO_DEFAULT_USER -> $winUser (from Windows login)"
        } else {
            $out += $line
        }
    } else {
        $out += $line
    }
}
if (-not $found) {
    $out += "SSO_DEFAULT_USER=$winUser"
    $changed = $true
}
if ($changed) {
    $out | Set-Content $envPath -Encoding UTF8
}
