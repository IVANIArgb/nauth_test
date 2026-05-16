param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,
    [string]$DestinationPath = ".\secrets\service.keytab"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $SourcePath)) {
    throw "File not found: $SourcePath"
}

$destDir = Split-Path -Parent $DestinationPath
if (-not (Test-Path $destDir)) {
    New-Item -ItemType Directory -Path $destDir | Out-Null
}

Copy-Item -Path $SourcePath -Destination $DestinationPath -Force

$bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $DestinationPath))
$size = $bytes.Length
$header = if ($size -ge 2) { "{0:x2}{1:x2}" -f $bytes[0], $bytes[1] } else { "n/a" }

Write-Host "Imported: $DestinationPath"
Write-Host "Size: $size bytes"
Write-Host "Header: $header"

if ($size -lt 64) {
    Write-Warning "Keytab is suspiciously small; file is likely corrupted or not a real keytab."
}

if ($header -notin @("0502", "0501")) {
    Write-Warning "Header is not a typical MIT keytab signature (expected 0502 or 0501)."
}
