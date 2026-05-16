# Auto-start Docker Desktop and wait for it, then build

Write-Host "Checking Docker Desktop..." -ForegroundColor Cyan

# Проверяем запущен ли Docker Desktop
$dockerProcess = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue

if (-not $dockerProcess) {
    Write-Host "Docker Desktop is not running. Attempting to start..." -ForegroundColor Yellow
    
    # Пробуем найти Docker Desktop в стандартных местах
    $dockerPaths = @(
        "${env:ProgramFiles}\Docker\Docker\Docker Desktop.exe",
        "${env:ProgramFiles(x86)}\Docker\Docker\Docker Desktop.exe",
        "$env:LOCALAPPDATA\Programs\Docker\Docker\Docker Desktop.exe"
    )
    
    $dockerExe = $null
    foreach ($path in $dockerPaths) {
        if (Test-Path $path) {
            $dockerExe = $path
            break
        }
    }
    
    if ($dockerExe) {
        Write-Host "Starting Docker Desktop from: $dockerExe" -ForegroundColor Cyan
        Start-Process -FilePath $dockerExe -WindowStyle Hidden
        Write-Host "Waiting for Docker Desktop to start (this may take 30-60 seconds)..." -ForegroundColor Yellow
    } else {
        Write-Host "ERROR: Docker Desktop executable not found in standard locations." -ForegroundColor Red
        Write-Host "Please start Docker Desktop manually and wait until it shows 'Running' in tray." -ForegroundColor Yellow
        Write-Host ""
        Read-Host "Press Enter after Docker Desktop is running, then we'll check again"
    }
}

# Ждём пока Docker engine запустится
Write-Host ""
Write-Host "Waiting for Docker engine to be ready..." -ForegroundColor Cyan
$maxWait = 60  # максимум 60 секунд
$waited = 0
$dockerReady = $false

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 2
    $waited += 2
    
    $ErrorActionPreferenceBackup = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    docker info *>$null
    if ($LASTEXITCODE -eq 0) {
        $dockerReady = $true
        break
    }
    $ErrorActionPreference = $ErrorActionPreferenceBackup
    
    Write-Host "." -NoNewline -ForegroundColor Gray
}

Write-Host ""

if ($dockerReady) {
    Write-Host "OK: Docker is ready!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Starting build script..." -ForegroundColor Cyan
    Write-Host ""
    & "$PSScriptRoot\build_docker_full.ps1"
} else {
    Write-Host ""
    Write-Host "ERROR: Docker engine did not start within $maxWait seconds." -ForegroundColor Red
    Write-Host "Please check Docker Desktop manually:" -ForegroundColor Yellow
    Write-Host "1. Open Docker Desktop" -ForegroundColor White
    Write-Host "2. Check if it shows any errors" -ForegroundColor White
    Write-Host "3. Wait until tray icon shows 'Running'" -ForegroundColor White
    Write-Host "4. Run: docker info (should work)" -ForegroundColor White
    Write-Host "5. Then run: .\scripts\docker\build_docker_full.ps1" -ForegroundColor White
}

