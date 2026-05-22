#Requires -Version 5.1
# ASCII-only messages (Windows PowerShell encoding safe).
$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "docker command not found. Install Docker Desktop."
}

$envFile = Join-Path $ProjectRoot ".env"
if (-not (Test-Path $envFile)) {
    foreach ($t in @("docker.env.sso.example", "docker.env.example", "env.example")) {
        $src = Join-Path $ProjectRoot $t
        if (Test-Path $src) {
            Copy-Item -LiteralPath $src -Destination $envFile
            Write-Host "Created .env from $t"
            break
        }
    }
}

$composeFiles = @("-f", "docker-compose.yml")
if (Test-Path (Join-Path $ProjectRoot "docker-compose.sso.yml")) {
    $composeFiles += @("-f", "docker-compose.sso.yml")
}

Write-Host "Docker: build ..."
& docker compose @composeFiles build
if ($LASTEXITCODE -ne 0) { throw "docker compose build exit $LASTEXITCODE" }

Write-Host "Docker: up -d ..."
& docker compose @composeFiles up -d
if ($LASTEXITCODE -ne 0) { throw "docker compose up exit $LASTEXITCODE" }

$webPort = "8080"
if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile -Encoding UTF8) {
        if ($line -match '^\s*WEB_PORT\s*=\s*(\d+)\s*$') {
            $webPort = $matches[1]
            break
        }
    }
}

Write-Host ""
Write-Host "OK (Docker)." -ForegroundColor Green
if ($composeFiles -contains "docker-compose.sso.yml") {
    Write-Host "  Site: http://localhost:$webPort/"
    Write-Host "  API:  http://localhost:$webPort/api/current-user"
    Write-Host "  Direct: http://localhost:8000/healthz"
} else {
    Write-Host "  Site: http://localhost:8000/"
}
