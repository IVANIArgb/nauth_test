#Requires -Version 5.1
<#
  Reads current Windows user from Active Directory and writes JSON for Docker (no manual DB).
  Run on host before: run-server.bat / update.bat
#>
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$CacheDir = Join-Path $Root "runtime\ad-cache"
New-Item -ItemType Directory -Force -Path $CacheDir | Out-Null

$login = if ($env:USERNAME) { $env:USERNAME.Trim().ToLower() } else { "" }
if (-not $login) {
    Write-Warning "USERNAME empty - skip AD cache"
    exit 0
}

function Get-Str($obj, [string[]]$names) {
    foreach ($n in $names) {
        if ($null -ne $obj.$n -and "$($obj.$n)".Trim()) { return "$($obj.$n)".Trim() }
    }
    return ""
}

function Convert-AdResult($GivenName, $MiddleName, $Surname, $Department, $Title) {
    @{
        first_name = $GivenName
        second_name = $MiddleName
        sur_name = $Surname
        department = $Department
        position = $Title
        login = $login
        source = "ad"
        updated_at = (Get-Date).ToUniversalTime().ToString("o")
    }
}

$profile = $null

try {
    Import-Module ActiveDirectory -ErrorAction Stop
    $u = Get-ADUser -Identity $login -Properties GivenName, Surname, MiddleName, Department, Title, DisplayName -ErrorAction Stop
    $profile = Convert-AdResult $u.GivenName $u.MiddleName $u.Surname $u.Department $u.Title
    Write-Host "AD: Get-ADUser OK"
} catch {
    Write-Host "Get-ADUser: $($_.Exception.Message) - try ADSI..."
}

if (-not $profile -and $env:USERDNSDOMAIN) {
    try {
        $root = "LDAP://$($env:USERDNSDOMAIN)"
        $searcher = New-Object System.DirectoryServices.DirectorySearcher
        $searcher.SearchRoot = New-Object System.DirectoryServices.DirectoryEntry($root)
        $searcher.Filter = "(&(objectCategory=person)(objectClass=user)(sAMAccountName=$login))"
        [void]$searcher.PropertiesToLoad.Add("givenName")
        [void]$searcher.PropertiesToLoad.Add("sn")
        [void]$searcher.PropertiesToLoad.Add("middleName")
        [void]$searcher.PropertiesToLoad.Add("department")
        [void]$searcher.PropertiesToLoad.Add("title")
        [void]$searcher.PropertiesToLoad.Add("displayName")
        $r = $searcher.FindOne()
        if ($r) {
            $p = $r.Properties
            $gn = ""; if ($p["givenname"]) { $gn = [string]$p["givenname"][0] }
            $sn = ""; if ($p["sn"]) { $sn = [string]$p["sn"][0] }
            $mid = ""; if ($p["middlename"]) { $mid = [string]$p["middlename"][0] }
            $dept = ""; if ($p["department"]) { $dept = [string]$p["department"][0] }
            $title = ""; if ($p["title"]) { $title = [string]$p["title"][0] }
            if (-not $gn -and -not $sn -and $p["displayname"]) {
                $parts = ([string]$p["displayname"][0]) -split "\s+"
                if ($parts.Count -ge 2) { $gn = $parts[0]; $sn = $parts[-1] }
            }
            $profile = Convert-AdResult $gn $mid $sn $dept $title
            Write-Host "AD: ADSI OK"
        }
    } catch {
        Write-Warning "ADSI: $($_.Exception.Message)"
    }
}

if (-not $profile) {
    Write-Warning "AD profile not loaded for $login"
    exit 1
}

$outPath = Join-Path $CacheDir "$login.json"
$profile | ConvertTo-Json -Compress | Set-Content -Path $outPath -Encoding UTF8
Write-Host "AD cache: $outPath"
Write-Host "  $($profile.sur_name) $($profile.first_name) - $($profile.department) / $($profile.position)"
