#Requires -Version 5.1
# Auto .env for Docker: Windows login as SSO user, AD host cache, optional LDAP discovery (no manual profile).
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
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($envPath, [string[]]$out, $utf8)
}

if (-not (Test-Path $envPath)) {
    $tpl = Join-Path $Root "docker.env.sso-ad.example"
    if (-not (Test-Path $tpl)) { $tpl = Join-Path $Root "docker.env.sso.example" }
    if (Test-Path $tpl) { Copy-Item $tpl $envPath }
    else { Set-Content $envPath "# auto-generated" -Encoding UTF8 }
}

$login = if ($env:USERNAME) { $env:USERNAME.Trim().ToLower() } else { "user" }
Set-EnvKey "SSO_DEFAULT_USER" $login
Set-EnvKey "TRUST_REMOTE_USER" "true"
Set-EnvKey "DOCKER_AUTH_FALLBACK" "false"
Set-EnvKey "KERBEROS_GSSAPI_ENABLED" "false"
Set-EnvKey "AD_HOST_PROFILE_CACHE_ENABLED" "true"
Set-EnvKey "AD_HOST_PROFILE_CACHE_DIR" "/app/runtime/ad-cache"

$ldapUser = ""
$ldapPass = ""
foreach ($line in (Get-Content $envPath -Encoding UTF8 -ErrorAction SilentlyContinue)) {
    if ($line -match '^\s*LDAP_USER\s*=\s*(.*)$') { $ldapUser = $matches[1].Trim() }
    if ($line -match '^\s*LDAP_BIND_DN\s*=\s*(.*)$') { if (-not $ldapUser) { $ldapUser = $matches[1].Trim() } }
    if ($line -match '^\s*LDAP_PASSWORD\s*=\s*(.*)$') { $ldapPass = $matches[1].Trim() }
}

if ($env:USERDNSDOMAIN) {
    $dns = $env:USERDNSDOMAIN.Trim()
    Set-EnvKey "AD_DNS_DOMAIN" $dns
    Set-EnvKey "LDAP_SERVER" "ldap://$dns`:389"
    $parts = $dns.Split(".") | ForEach-Object { "DC=$_" }
    Set-EnvKey "LDAP_BASE_DN" ($parts -join ",")
    if ($env:USERDOMAIN) { Set-EnvKey "KERBEROS_REALM" ($env:USERDOMAIN.ToUpper()) }
    $hasBind = ($ldapUser -and $ldapPass -and $ldapPass -notmatch 'ПАРОЛЬ|PASSWORD|замените|REPLACE')
    if ($hasBind) {
        Set-EnvKey "LDAP_ENABLED" "true"
        Write-Host ".env: SSO=$login LDAP=$dns (bind OK)"
    } else {
        Set-EnvKey "LDAP_ENABLED" "false"
        Write-Host ".env: SSO=$login AD cache + LDAP off (no LDAP_USER/PASSWORD)"
    }
} else {
    Set-EnvKey "LDAP_ENABLED" "false"
    Write-Host ".env: SSO=$login (no domain - AD cache only if refresh OK)"
}

# SECRET_KEY if placeholder
$sk = ""
foreach ($line in (Get-Content $envPath -Encoding UTF8)) {
    if ($line -match '^\s*SECRET_KEY\s*=\s*(.*)$') { $sk = $matches[1].Trim(); break }
}
if (-not $sk -or $sk -match "ЗАМЕНИТЕ|замените|REPLACE|example|dev-key") {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $newKey = [BitConverter]::ToString($bytes).Replace("-", "").ToLower()
    Set-EnvKey "SECRET_KEY" $newKey
}
