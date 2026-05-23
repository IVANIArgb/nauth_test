#Requires -Version 5.1
<#
  Reads user from Active Directory -> UTF-8 JSON for Docker (no keytab, no manual DB).
  Run on domain PC before run-server.bat / update.bat
#>
param(
    [string]$Login = ""
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CacheDir = Join-Path $Root "runtime\ad-cache"
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

if (-not $Login) {
    $Login = if ($env:USERNAME) { $env:USERNAME.Trim().ToLower() } else { "" }
} else {
    $Login = $Login.Trim().ToLower()
}

if (-not $Login) {
    Write-Warning "Login empty - skip AD cache"
    exit 0
}

function Convert-AdResult($GivenName, $MiddleName, $Surname, $Department, $Title, $Mail) {
    @{
        first_name = [string]$GivenName
        second_name = [string]$MiddleName
        sur_name = [string]$Surname
        department = [string]$Department
        position = [string]$Title
        email = [string]$Mail
        login = $Login
        source = "ad"
        updated_at = (Get-Date).ToUniversalTime().ToString("o")
    }
}

$profile = $null

try {
    Import-Module ActiveDirectory -ErrorAction Stop
    $u = Get-ADUser -Identity $Login -Properties GivenName, Surname, MiddleName, Department, Title, DisplayName, Mail -ErrorAction Stop
    $profile = Convert-AdResult $u.GivenName $u.MiddleName $u.Surname $u.Department $u.Title $u.Mail
    Write-Host "AD: Get-ADUser OK"
} catch {
    Write-Host "Get-ADUser: $($_.Exception.Message) - try ADSI..."
}

if (-not $profile -and $env:USERDNSDOMAIN) {
    try {
        $root = "LDAP://$($env:USERDNSDOMAIN)"
        $searcher = New-Object System.DirectoryServices.DirectorySearcher
        $searcher.SearchRoot = New-Object System.DirectoryServices.DirectoryEntry($root)
        $searcher.Filter = "(&(objectCategory=person)(objectClass=user)(sAMAccountName=$Login))"
        [void]$searcher.PropertiesToLoad.Add("givenName")
        [void]$searcher.PropertiesToLoad.Add("sn")
        [void]$searcher.PropertiesToLoad.Add("middleName")
        [void]$searcher.PropertiesToLoad.Add("department")
        [void]$searcher.PropertiesToLoad.Add("title")
        [void]$searcher.PropertiesToLoad.Add("displayName")
        [void]$searcher.PropertiesToLoad.Add("mail")
        $r = $searcher.FindOne()
        if ($r) {
            $p = $r.Properties
            $gn = ""; if ($p["givenname"]) { $gn = [string]$p["givenname"][0] }
            $sn = ""; if ($p["sn"]) { $sn = [string]$p["sn"][0] }
            $mid = ""; if ($p["middlename"]) { $mid = [string]$p["middlename"][0] }
            $dept = ""; if ($p["department"]) { $dept = [string]$p["department"][0] }
            $title = ""; if ($p["title"]) { $title = [string]$p["title"][0] }
            $mail = ""; if ($p["mail"]) { $mail = [string]$p["mail"][0] }
            if (-not $gn -and -not $sn -and $p["displayname"]) {
                $parts = ([string]$p["displayname"][0]) -split "\s+"
                if ($parts.Count -ge 2) { $gn = $parts[0]; $sn = $parts[-1] }
            }
            $profile = Convert-AdResult $gn $mid $sn $dept $title $mail
            Write-Host "AD: ADSI OK"
        }
    } catch {
        Write-Warning "ADSI: $($_.Exception.Message)"
    }
}

if (-not $profile) {
    Write-Warning "AD profile not loaded for $Login"
    exit 1
}

$outPath = Join-Path $CacheDir "$Login.json"
$json = $profile | ConvertTo-Json -Compress -Depth 4
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($outPath, $json, $utf8)
Write-Host "AD cache: $outPath"
Write-Host "  $($profile.sur_name) $($profile.first_name) $($profile.second_name) - $($profile.department) / $($profile.position)"
