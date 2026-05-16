# Build and export Docker image LearningSiteSV (DB, all folders, TEST_MODE on)

$ErrorActionPreference = "Stop"

$IMAGE_NAME = "learnsite:web"
$OUT_DIR = "_docker_export"
$TAR_FILE = Join-Path $OUT_DIR "learnsite-web-image.tar"
$CONTAINER_NAME = "learnsite-web"

if (-not (Test-Path $OUT_DIR)) {
    New-Item -ItemType Directory -Path $OUT_DIR | Out-Null
}

Write-Host ""
Write-Host "[0.5/4] Checking Docker..." -ForegroundColor Cyan

# Проверяем запущен ли Docker Desktop процесс
$dockerDesktopRunning = Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue
if (-not $dockerDesktopRunning) {
    Write-Host "Docker Desktop process not found. Starting check..." -ForegroundColor Yellow
}

# Игнорируем WARNING от битых плагинов, проверяем только код выхода
$ErrorActionPreferenceBackup = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
try {
    $dockerOutput = docker info 2>&1 | Out-String
    $dockerOk = $LASTEXITCODE -eq 0
} catch {
    $dockerOk = $false
}
$ErrorActionPreference = $ErrorActionPreferenceBackup

if (-not $dockerOk) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "DOCKER DAEMON NOT RUNNING" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Steps to fix:" -ForegroundColor Yellow
    Write-Host "1. Open Docker Desktop application" -ForegroundColor White
    Write-Host "2. Wait until tray icon shows 'Running' (not 'Starting')" -ForegroundColor White
    Write-Host "3. Right-click Docker icon -> Switch to Linux containers (if needed)" -ForegroundColor White
    Write-Host "4. Wait 20-30 seconds for engine to fully start" -ForegroundColor White
    Write-Host "5. Test: docker info (should show 'Server:' section)" -ForegroundColor White
    Write-Host "6. Re-run this script" -ForegroundColor White
    Write-Host ""
    Write-Host "Current status:" -ForegroundColor Cyan
    if ($dockerDesktopRunning) {
        Write-Host "  Docker Desktop process: RUNNING" -ForegroundColor Green
        Write-Host "  Docker engine: NOT READY (wait a bit longer)" -ForegroundColor Yellow
    } else {
        Write-Host "  Docker Desktop process: NOT RUNNING" -ForegroundColor Red
        Write-Host "  Docker engine: NOT AVAILABLE" -ForegroundColor Red
    }
    Write-Host ""
    exit 1
}
Write-Host "OK: Docker daemon is running" -ForegroundColor Green

Write-Host ""
Write-Host "[0/4] Checking DB file..." -ForegroundColor Cyan
$dbPath = Join-Path "database" "users_courses.db"
if (Test-Path $dbPath) {
    Write-Host "OK: $dbPath found (included in image)." -ForegroundColor Green
} else {
    Write-Host "WARNING: $dbPath NOT found. Image will have empty DB path." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "[1/4] Building Docker image..." -ForegroundColor Cyan
docker build -t $IMAGE_NAME .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed. Check Docker and Dockerfile." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "[2/4] Exporting image to file..." -ForegroundColor Cyan
docker save -o $TAR_FILE $IMAGE_NAME
if ($LASTEXITCODE -ne 0) {
    Write-Host "Export failed." -ForegroundColor Red
    exit 1
}
Write-Host "Image saved: $TAR_FILE" -ForegroundColor Green

Write-Host ""
Write-Host "[3/4] Stopping old container if exists..." -ForegroundColor Cyan
$ErrorActionPreferenceBackup = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
docker stop $CONTAINER_NAME 2>&1 | Out-Null
docker rm $CONTAINER_NAME 2>&1 | Out-Null
$ErrorActionPreference = $ErrorActionPreferenceBackup

Write-Host ""
Write-Host "[4/4] Run container (TEST_MODE=all users are admins):" -ForegroundColor Cyan
Write-Host "  docker run -d -p 8000:8000 -e TEST_MODE=true --name $CONTAINER_NAME $IMAGE_NAME" -ForegroundColor White
Write-Host ""

$startNow = Read-Host "Start container now? (y/n, default n)"
if ($startNow -eq "y" -or $startNow -eq "Y") {
    docker run -d -p 8000:8000 -e TEST_MODE=true --name $CONTAINER_NAME $IMAGE_NAME
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Container start failed." -ForegroundColor Red
        exit 1
    }
    Write-Host ""
    Write-Host "Container started. Open http://localhost:8000" -ForegroundColor Green
} else {
    Write-Host "Container not started. Use command above to start." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "TRANSFER TO ANOTHER DEVICE" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "1. Copy these files to target device:" -ForegroundColor White
Write-Host "   - $TAR_FILE" -ForegroundColor Yellow
Write-Host "   - scripts\\docker\\load_and_run_docker.ps1 (or .bat)" -ForegroundColor Yellow
Write-Host ""
Write-Host "2. On target device, run:" -ForegroundColor White
Write-Host "   .\\scripts\\docker\\load_and_run_docker.ps1" -ForegroundColor Green
Write-Host ""
Write-Host "   Or manually:" -ForegroundColor Gray
Write-Host "   docker load -i $TAR_FILE" -ForegroundColor Gray
Write-Host "   docker run -d -p 8000:8000 -e TEST_MODE=true --name $CONTAINER_NAME $IMAGE_NAME" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Open: http://localhost:8000" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to exit"

