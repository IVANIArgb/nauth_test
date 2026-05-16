# Скрипт для целевого устройства: загрузить образ и запустить контейнер

$TAR_FILE = "learnsite-web-image.tar"
$TAR_DIR = "_docker_export"
$TAR_FULL_PATH = Join-Path $TAR_DIR $TAR_FILE

# Проверяем разные возможные пути
if (-not (Test-Path $TAR_FULL_PATH)) {
    # Пробуем в текущей директории
    if (Test-Path $TAR_FILE) {
        $TAR_FULL_PATH = $TAR_FILE
    } else {
        Write-Host "ERROR: Image file not found. Looking for:" -ForegroundColor Red
        Write-Host "  - $TAR_FULL_PATH" -ForegroundColor Yellow
        Write-Host "  - $TAR_FILE (current directory)" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Make sure you copied the .tar file to the same directory as this script." -ForegroundColor Yellow
        Read-Host "Press Enter to exit"
        exit 1
    }
}

$IMAGE_NAME = "learnsite:web"
$CONTAINER_NAME = "learnsite-web"

Write-Host ""
Write-Host "[1/3] Loading Docker image from $TAR_FULL_PATH..." -ForegroundColor Cyan
docker load -i $TAR_FULL_PATH
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to load image. Check if file exists and Docker is running." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "[2/3] Stopping old container if exists..." -ForegroundColor Cyan
$ErrorActionPreferenceBackup = $ErrorActionPreference
$ErrorActionPreference = "SilentlyContinue"
docker stop $CONTAINER_NAME 2>&1 | Out-Null
docker rm $CONTAINER_NAME 2>&1 | Out-Null
$ErrorActionPreference = $ErrorActionPreferenceBackup

Write-Host ""
Write-Host "[3/3] Starting container (TEST_MODE=true, all users are admins)..." -ForegroundColor Cyan
docker run -d -p 8000:8000 -e TEST_MODE=true --name $CONTAINER_NAME $IMAGE_NAME
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start container." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "CONTAINER STARTED SUCCESSFULLY" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "Open in browser: http://localhost:8000" -ForegroundColor Cyan
Write-Host ""
Write-Host "Container: $CONTAINER_NAME" -ForegroundColor White
Write-Host "Image: $IMAGE_NAME" -ForegroundColor White
Write-Host "Port: 8000" -ForegroundColor White
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  docker logs $CONTAINER_NAME     - view logs" -ForegroundColor Gray
Write-Host "  docker stop $CONTAINER_NAME     - stop container" -ForegroundColor Gray
Write-Host "  docker start $CONTAINER_NAME    - start container" -ForegroundColor Gray
Write-Host "  docker rm $CONTAINER_NAME       - remove container" -ForegroundColor Gray
Write-Host ""
Read-Host "Press Enter to exit"

