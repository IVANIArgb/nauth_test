#Requires -Version 5.1
# Native run.py on domain PC: real realm, no Docker LDAP/cache overrides from .env
$ErrorActionPreference = "SilentlyContinue"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envPath = Join-Path $Root ".env"

function Set-EnvKey([string]$key, [string]$value) {
    $lines = @()
    if (Test-Path $envPath) { $lines = Get-Content $envPath -Encoding UTF8 }
    $found = $false
    $out = foreach ($line in $lines) {
        if ($line -match "^\s*#") { $line; continue }
        if ($line -match "^\s*$([regex]::Escape($key))\s*=") {
            $found = $true
            "$key=$value"
        } else { $line }
    }
    if (-not $found) { $out += "$key=$value" }
    $out | Set-Content $envPath -Encoding UTF8
}

if (-not $env:USERDOMAIN -or $env:USERDOMAIN -eq "WORKGROUP") {
    Write-Host ".env: not a domain PC, skip native sync"
    exit 0
}

$realm = if ($env:USERDNSDOMAIN) { $env:USERDNSDOMAIN.Trim().ToUpper() } else { $env:USERDOMAIN.Trim().ToUpper() }
Set-EnvKey "KERBEROS_REALM" $realm
Set-EnvKey "LDAP_ENABLED" "false"
Set-EnvKey "AD_HOST_PROFILE_CACHE_ENABLED" "false"
Write-Host ".env: native AD realm=$realm LDAP off cache off"
