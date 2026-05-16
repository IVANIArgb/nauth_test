param(
    [Parameter(Mandatory = $true)][string]$DomainFqdn,
    [Parameter(Mandatory = $true)][string]$ServiceAccount,
    [Parameter(Mandatory = $true)][string]$ServicePassword,
    [Parameter(Mandatory = $true)][string]$SpnHostname
)

$ErrorActionPreference = "Stop"

Write-Host "Проверка прав сервисной учетной записи..."
Import-Module ActiveDirectory

$serviceUser = Get-ADUser -Identity $ServiceAccount -Properties ServicePrincipalName,MemberOf
if (-not $serviceUser) {
    throw "Сервисная учетная запись не найдена: $ServiceAccount"
}

$spn = "HTTP/$SpnHostname"
Write-Host "Регистрация SPN: $spn"
setspn -S $spn $ServiceAccount

$keytabPath = Join-Path $PSScriptRoot "service.keytab"
$principal = "$spn@$($DomainFqdn.ToUpper())"

Write-Host "Генерация keytab через ktpass..."
ktpass `
    /princ $principal `
    /mapuser "$ServiceAccount@$DomainFqdn" `
    /pass $ServicePassword `
    /crypto AES256-SHA1 `
    /ptype KRB5_NT_PRINCIPAL `
    /out $keytabPath `
    /kvno 0

Write-Host "Проверка SPN у пользователя:"
Get-ADUser -Identity $ServiceAccount -Properties ServicePrincipalName |
    Select-Object -ExpandProperty ServicePrincipalName

Write-Host "Проверка членства в группах (для LDAP read):"
Get-ADPrincipalGroupMembership -Identity $ServiceAccount | Select-Object Name

Write-Host "Готово. Keytab: $keytabPath"
