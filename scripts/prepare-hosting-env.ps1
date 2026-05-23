#Requires -Version 5.1
# Hosting .env: SECRET_KEY + LDAP from Windows USERDNSDOMAIN (ASCII-only for PS parser).
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
        if ($line -match '^\s*#') { $line; continue }
        if ($line -match ('^\s*' + [regex]::Escape($key) + '\s*=')) {
            $found = $true
            ($key + '=' + $value)
        } else { $line }
    }
    if (-not $found) { $out += ($key + '=' + $value) }
    $utf8 = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllLines($envPath, [string[]]$out, $utf8)
}

Set-EnvKey 'TRUST_REMOTE_USER' 'true'
Set-EnvKey 'TRUST_REMOTE_USER_CONFIRM' 'true'
Set-EnvKey 'TERMINAL_ROLE_COMMANDS_ENABLED' 'false'

if ($env:USERDNSDOMAIN) {
    $dns = $env:USERDNSDOMAIN.Trim()
    if ($env:USERDOMAIN) {
        $realm = $env:USERDOMAIN.Trim().ToUpper()
    } else {
        $realm = $dns.Split('.')[0].ToUpper()
    }
    $parts = @()
    foreach ($p in $dns.Split('.')) { $parts += ('DC=' + $p) }
    $baseDn = $parts -join ','
    Set-EnvKey 'AD_DNS_DOMAIN' $dns
    Set-EnvKey 'LDAP_SERVER' ('ldap://' + $dns + ':389')
    Set-EnvKey 'LDAP_BASE_DN' $baseDn
    Set-EnvKey 'KERBEROS_REALM' $realm
    Write-Host ('LDAP from Windows: ' + $dns + ' / ' + $baseDn + ' / realm=' + $realm)
} else {
    Write-Warning 'No USERDNSDOMAIN - set LDAP_* in .env manually'
}

$sk = ''
$ldapPass = ''
$ldapUser = ''
foreach ($line in (Get-Content $envPath -Encoding UTF8)) {
    if ($line -match '^\s*SECRET_KEY\s*=\s*(.*)$') { $sk = $matches[1].Trim() }
    if ($line -match '^\s*LDAP_PASSWORD\s*=\s*(.*)$') { $ldapPass = $matches[1].Trim() }
    if ($line -match '^\s*LDAP_USER\s*=\s*(.*)$') { $ldapUser = $matches[1].Trim() }
}

$skLow = $sk.ToLower()
$badSk = ($skLow -match 'zamenite|replace|example|dev-key|not-for-production|password')
if ((-not $sk) -or $badSk) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $newKey = [BitConverter]::ToString($bytes).Replace('-', '').ToLower()
    Set-EnvKey 'SECRET_KEY' $newKey
    Write-Host 'SECRET_KEY: auto-generated'
}

$passLow = $ldapPass.ToLower()
$badPass = ($passLow -match 'parol|password|replace|example|^$')
$hasBind = ($ldapUser -and $ldapPass -and (-not $badPass))
Set-EnvKey 'LDAP_ENABLED' 'true'

if (-not $hasBind) {
    Write-Host ''
    Write-Host '>>> Add to .env (from AD admin), then run update-hosting.bat again:'
    if ($env:USERDOMAIN) {
        Write-Host ('    LDAP_USER=' + $env:USERDOMAIN + '\svc_ldap_read')
    } else {
        Write-Host '    LDAP_USER=DOMAIN\svc_ldap_read'
    }
    Write-Host '    LDAP_PASSWORD=<service account password>'
    Write-Host ''
}

Write-Host '.env ready'
