#Requires -Version 5.1
# Sync .env for hosting from Windows domain (every update-all.bat run).
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envPath = Join-Path $Root ".env"
$tplPath = Join-Path $Root "docker.env.hosting.example"

if (-not (Test-Path $envPath)) {
    if (Test-Path $tplPath) { Copy-Item $tplPath $envPath }
    else { New-Item -ItemType File -Path $envPath -Force | Out-Null }
    Write-Host "Created .env"
}

function Get-EnvKey([string]$key) {
    foreach ($line in (Get-Content $envPath -Encoding UTF8)) {
        if ($line -match ('^\s*' + [regex]::Escape($key) + '\s*=\s*(.*)$')) {
            return $matches[1].Trim()
        }
    }
    return ""
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

function Test-BadLdapPassword([string]$p) {
    if (-not $p) { return $true }
    $l = $p.ToLower()
    return ($l -match 'parol|password|replace|example|zamenite|^<|^$')
}

function Test-BadLdapUser([string]$u) {
    if (-not $u) { return $true }
    return ($u -match 'DOMAIN\\|svc_ldap_read|TVOR_DOMEN')
}

# --- always refresh hosting defaults ---
Set-EnvKey 'WEB_PORT' '8080'
Set-EnvKey 'FLASK_ENV' 'production'
Set-EnvKey 'TRUST_REMOTE_USER' 'true'
Set-EnvKey 'TRUST_REMOTE_USER_CONFIRM' 'true'
Set-EnvKey 'DOCKER_AUTH_FALLBACK' 'false'
Set-EnvKey 'TEST_MODE' 'false'
Set-EnvKey 'TERMINAL_ROLE_COMMANDS_ENABLED' 'false'
Set-EnvKey 'KERBEROS_GSSAPI_ENABLED' 'false'
Set-EnvKey 'LDAP_ENABLED' 'true'
Set-EnvKey 'LDAP_USE_SSL' 'false'
Set-EnvKey 'TRUSTED_PROXY_IPS' '10.0.0.0/8,172.16.0.0/12,127.0.0.1,::1'

$strict = Get-EnvKey 'HOSTING_STRICT_SSO'
if (-not $strict) {
    Set-EnvKey 'HOSTING_STRICT_SSO' 'false'
    Write-Host 'HOSTING_STRICT_SSO=false (local test; set true on server with IIS)'
}

# --- domain from Windows ---
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
    $dnsLow = $dns.ToLower()
    Set-EnvKey 'AD_DNS_DOMAIN' $dns
    if ($dnsLow -match 'grouphms\.local') {
        Set-EnvKey 'LDAP_SERVER' ('ldaps://' + $dnsLow + ':636')
        Set-EnvKey 'LDAP_USE_SSL' 'true'
    } else {
        Set-EnvKey 'LDAP_SERVER' ('ldap://' + $dnsLow + ':389')
        Set-EnvKey 'LDAP_USE_SSL' 'false'
    }
    Set-EnvKey 'LDAP_BASE_DN' $baseDn
    Set-EnvKey 'KERBEROS_REALM' $realm
    Write-Host ('.env LDAP: ' + $dnsLow + ' | ' + $baseDn + ' | realm=' + $realm)
} else {
    Write-Warning 'No USERDNSDOMAIN - LDAP_SERVER/LDAP_BASE_DN not auto-filled'
}

# --- SECRET_KEY ---
$sk = Get-EnvKey 'SECRET_KEY'
$skLow = $sk.ToLower()
if ((-not $sk) -or ($skLow -match 'zamenite|replace|example|dev-key|not-for-production')) {
    $bytes = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    Set-EnvKey 'SECRET_KEY' ([BitConverter]::ToString($bytes).Replace('-', '').ToLower())
    Write-Host 'SECRET_KEY: auto-generated'
}

# --- LDAP bind (optional one-shot: set LDAP_SETUP_USER / LDAP_SETUP_PASS before script) ---
if ($env:LDAP_SETUP_USER) {
    Set-EnvKey 'LDAP_USER' $env:LDAP_SETUP_USER.Trim()
    Write-Host 'LDAP_USER: from LDAP_SETUP_USER'
}
if ($env:LDAP_SETUP_PASS) {
    Set-EnvKey 'LDAP_PASSWORD' $env:LDAP_SETUP_PASS
    Write-Host 'LDAP_PASSWORD: from LDAP_SETUP_PASS'
}

$ldapUser = Get-EnvKey 'LDAP_USER'
$ldapPass = Get-EnvKey 'LDAP_PASSWORD'

if (Test-BadLdapUser $ldapUser) {
    if ($env:USERDOMAIN) {
        Set-EnvKey 'LDAP_USER' ($env:USERDOMAIN + '\svc_ldap_read')
        Write-Host ('LDAP_USER: ' + $env:USERDOMAIN + '\svc_ldap_read (template - replace if admin gave other login)')
    }
} else {
    Write-Host ('LDAP_USER: kept ' + $ldapUser)
}

if (Test-BadLdapPassword $ldapPass) {
    Write-Host 'LDAP_PASSWORD: still placeholder - set real password from AD admin in .env'
} else {
    Write-Host 'LDAP_PASSWORD: set (kept)'
}

Write-Host ('.env updated: ' + $envPath)
