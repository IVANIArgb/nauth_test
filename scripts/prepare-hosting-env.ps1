#Requires -Version 5.1
# .env для hosting: SECRET_KEY, LDAP из домена Windows (%USERDNSDOMAIN%).
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

Set-EnvKey "TRUST_REMOTE_USER" "true"
Set-EnvKey "TRUST_REMOTE_USER_CONFIRM" "true"
Set-EnvKey "TERMINAL_ROLE_COMMANDS_ENABLED" "false"

if ($env:USERDNSDOMAIN) {
    $dns = $env:USERDNSDOMAIN.Trim()
    $realm = if ($env:USERDOMAIN) { $env:USERDOMAIN.Trim().ToUpper() } else { $dns.Split(".")[0].ToUpper() }
    $baseDn = ($dns.Split(".") | ForEach-Object { "DC=$_" }) -join ","
    Set-EnvKey "AD_DNS_DOMAIN" $dns
    Set-EnvKey "LDAP_SERVER" "ldap://$dns`:389"
    Set-EnvKey "LDAP_BASE_DN" $baseDn
    Set-EnvKey "KERBEROS_REALM" $realm
    Write-Host "LDAP from Windows: $dns / $baseDn / realm=$realm"
} else {
    Write-Warning "No USERDNSDOMAIN — fill LDAP_* in .env manually"
}

$sk = ""
$ldapPass = ""
$ldapUser = ""
foreach ($line in (Get-Content $envPath -Encoding UTF8)) {
    if ($line -match '^\s*SECRET_KEY\s*=\s*(.*)$') { $sk = $matches[1].Trim() }
    if ($line -match '^\s*LDAP_PASSWORD\s*=\s*(.*)$') { $ldapPass = $matches[1].Trim() }
    if ($line -match '^\s*LDAP_USER\s*=\s*(.*)$') { $ldapUser = $matches[1].Trim() }
}

if (-not $sk -or $sk.ToLower() -match "замените|replace|example|dev-key|not-for-production") {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    Set-EnvKey "SECRET_KEY" ([BitConverter]::ToString($bytes).Replace("-", "").ToLower())
    Write-Host "SECRET_KEY: auto-generated"
}

$hasBind = ($ldapUser -and $ldapPass -and $ldapPass -notmatch "ПАРОЛЬ|PASSWORD|замените|REPLACE|example|^$")
if ($hasBind) {
    Set-EnvKey "LDAP_ENABLED" "true"
} else {
    Set-EnvKey "LDAP_ENABLED" "true"
    Write-Host ""
    Write-Host ">>> Add to .env (from AD admin), then run update-hosting.bat again:"
    if ($env:USERDOMAIN) {
        Write-Host "    LDAP_USER=$($env:USERDOMAIN)\svc_ldap_read"
    } else {
        Write-Host "    LDAP_USER=DOMAIN\svc_ldap_read"
    }
    Write-Host "    LDAP_PASSWORD=<service account password>"
    Write-Host ""
}

Write-Host ".env ready"
