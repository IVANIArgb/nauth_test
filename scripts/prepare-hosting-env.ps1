#Requires -Version 5.1
# Подготовка .env для hosting: SECRET_KEY, предупреждения по LDAP.
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envPath = Join-Path $Root ".env"

if (-not (Test-Path $envPath)) {
    Copy-Item (Join-Path $Root "docker.env.hosting.example") $envPath
    Write-Host "Created .env from docker.env.hosting.example"
}

function Set-EnvKey([string]$key, [string]$value) {
    $lines = Get-Content $envPath -Encoding UTF8
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*#") { $line; continue }
        if ($line -match "^\s*$([regex]::Escape($key))\s*=") {
            $found = $true
            "$key=$value"
        } else { $line }
    }
    if (-not $found) { $out += "$key=$value" }
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($envPath, [string[]]$out, $utf8)
}

$sk = ""
$ldapPass = ""
foreach ($line in (Get-Content $envPath -Encoding UTF8)) {
    if ($line -match '^\s*SECRET_KEY\s*=\s*(.*)$') { $sk = $matches[1].Trim() }
    if ($line -match '^\s*LDAP_PASSWORD\s*=\s*(.*)$') { $ldapPass = $matches[1].Trim() }
}

$skLow = $sk.ToLower()
if (-not $sk -or $skLow -match "замените|replace|example|dev-key|not-for-production") {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $newKey = [BitConverter]::ToString($bytes).Replace("-", "").ToLower()
    Set-EnvKey "SECRET_KEY" $newKey
    Write-Host "SECRET_KEY: auto-generated"
}

if (-not $ldapPass -or $ldapPass -match "ПАРОЛЬ|PASSWORD|замените|REPLACE|example") {
    Write-Warning "LDAP_PASSWORD is placeholder — set real AD bind password in .env or container stays unhealthy."
}

Write-Host ".env ready for docker compose hosting"
