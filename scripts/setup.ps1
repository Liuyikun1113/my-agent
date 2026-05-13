# Multi-Agent Framework Setup (Windows PowerShell)
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $PSScriptRoot

Write-Host "=== Multi-Agent Framework Setup ===" -ForegroundColor Cyan
Write-Host "Root: $ROOT"

# ---- Backend ----
Write-Host "`n--- Setting up backend ---" -ForegroundColor Yellow
Set-Location "$ROOT\backend"

if (-not (Test-Path "venv")) {
    python -m venv venv
    Write-Host "Created Python virtual environment"
}

& .\venv\Scripts\activate.ps1
pip install --upgrade pip -q
pip install -r requirements.txt -q
Write-Host "Backend dependencies installed"

if (-not (Test-Path ".env")) {
    Copy-Item "$ROOT\.env.example" "$ROOT\backend\.env"
    Write-Host "Created backend/.env from .env.example — update secrets before production use"
}

# ---- Frontend ----
Write-Host "`n--- Setting up frontend ---" -ForegroundColor Yellow
Set-Location "$ROOT\frontend"
npm install
Write-Host "Frontend dependencies installed"

# ---- Docker services ----
Write-Host "`n--- Starting infrastructure (MySQL, Redis, Milvus) ---" -ForegroundColor Yellow
Set-Location $ROOT
try {
    docker compose up -d mysql redis milvus etcd minio
} catch {
    try {
        docker-compose up -d mysql redis milvus etcd minio
    } catch {
        Write-Host "Docker Compose not available; start MySQL, Redis, Milvus manually" -ForegroundColor Red
    }
}

Write-Host "`n=== Setup complete ===" -ForegroundColor Green
Write-Host "Run '.\scripts\start_dev.ps1' to start the application"
Write-Host "Or manually:"
Write-Host "  backend: cd backend; .\venv\Scripts\activate; uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"
Write-Host "  frontend: cd frontend; npm run dev"
