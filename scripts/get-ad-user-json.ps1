#Requires -Version 5.1
param([Parameter(Mandatory = $true)][string]$Login)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$login = $Login.Trim().ToLower()
if (-not $login) { exit 2 }

function Out-Profile($gn, $mid, $sn, $dept, $title) {
    @{
        first_name = [string]$gn
        second_name = [string]$mid
        sur_name = [string]$sn
        department = [string]$dept
        position = [string]$title
    } | ConvertTo-Json -Compress
}

try {
    Import-Module ActiveDirectory -ErrorAction Stop
    $u = Get-ADUser -Identity $login -Properties GivenName, Surname, MiddleName, Department, Title -ErrorAction Stop
    Out-Profile $u.GivenName $u.MiddleName $u.Surname $u.Department $u.Title
    exit 0
} catch { }

if ($env:USERDNSDOMAIN) {
    $searcher = New-Object System.DirectoryServices.DirectorySearcher
    $searcher.SearchRoot = New-Object System.DirectoryServices.DirectoryEntry("LDAP://$($env:USERDNSDOMAIN)")
    $searcher.Filter = "(&(objectCategory=person)(objectClass=user)(sAMAccountName=$login))"
    [void]$searcher.PropertiesToLoad.AddRange(@("givenName", "sn", "middleName", "department", "title", "displayName"))
    $r = $searcher.FindOne()
    if ($r) {
        $p = $r.Properties
        $gn = ""; if ($p["givenname"]) { $gn = [string]$p["givenname"][0] }
        $sn = ""; if ($p["sn"]) { $sn = [string]$p["sn"][0] }
        $mid = ""; if ($p["middlename"]) { $mid = [string]$p["middlename"][0] }
        $dept = ""; if ($p["department"]) { $dept = [string]$p["department"][0] }
        $title = ""; if ($p["title"]) { $title = [string]$p["title"][0] }
        Out-Profile $gn $mid $sn $dept $title
        exit 0
    }
}
Write-Error "AD user not found: $login"
exit 1
