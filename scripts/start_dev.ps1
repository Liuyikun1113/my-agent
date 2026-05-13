# Multi-Agent Framework Development Start (Windows PowerShell)
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host "=== Starting Multi-Agent Framework (Development) ===" -ForegroundColor Cyan

# ---- Infrastructure ----
Write-Host "`n--- Starting infrastructure services ---" -ForegroundColor Yellow
Set-Location $ROOT
try {
    docker compose up -d mysql redis milvus etcd minio
} catch {
    try {
        docker-compose up -d mysql redis milvus etcd minio
    } catch {
        Write-Host "Docker Compose not found — assuming services are already running" -ForegroundColor Red
    }
}

# Wait for MySQL
Write-Host "Waiting for MySQL..."
for ($i = 1; $i -le 30; $i++) {
    $healthy = docker exec multi-agent-mysql mysqladmin ping -h localhost --silent 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "MySQL is ready"
        break
    }
    Start-Sleep -Seconds 2
}

# ---- Run Alembic migrations ----
Write-Host "`n--- Running database migrations ---" -ForegroundColor Yellow
Set-Location "$ROOT\backend"
if (Test-Path "venv") {
    & .\venv\Scripts\activate.ps1
}
try {
    alembic upgrade head
} catch {
    Write-Host "Alembic migration skipped (DB may not be ready)" -ForegroundColor Red
}

# ---- Start backend ----
Write-Host "`n--- Starting backend (port 8000) ---" -ForegroundColor Yellow
Set-Location "$ROOT\backend"
if (Test-Path "venv") {
    & .\venv\Scripts\activate.ps1
}
$backendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location "$root\backend"
    & .\venv\Scripts\python.exe -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
} -ArgumentList $ROOT

# ---- Start frontend ----
Write-Host "`n--- Starting frontend (port 5173) ---" -ForegroundColor Yellow
Set-Location "$ROOT\frontend"
$frontendJob = Start-Job -ScriptBlock {
    param($root)
    Set-Location "$root\frontend"
    npm run dev
} -ArgumentList $ROOT

Write-Host "`n=== Services running ===" -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8000"
Write-Host "  Frontend: http://localhost:5173"
Write-Host "  API Docs: http://localhost:8000/docs"
Write-Host "`nRun the following to stop:"
Write-Host "  Stop-Job *; Remove-Job *"
Write-Host "`nOr press Ctrl+C and then run Stop-Job * to clean up"

try {
    while ($true) {
        Receive-Job -Job $backendJob
        Receive-Job -Job $frontendJob
        Start-Sleep -Seconds 2
    }
} finally {
    Stop-Job -Job $backendJob -ErrorAction SilentlyContinue
    Stop-Job -Job $frontendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job -Job $frontendJob -ErrorAction SilentlyContinue
    Write-Host "Services stopped"
}
