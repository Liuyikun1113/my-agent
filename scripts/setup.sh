#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
echo "=== Multi-Agent Framework Setup ==="
echo "Root: $ROOT"

# ---- Backend ----
echo ""
echo "--- Setting up backend ---"
cd "$ROOT/backend"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "Created Python virtual environment"
fi

source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "Backend dependencies installed"

# Copy .env if missing
if [ ! -f ".env" ]; then
    cp ../.env.example .env
    echo "Created backend/.env from .env.example — update secrets before production use"
fi

# ---- Frontend ----
echo ""
echo "--- Setting up frontend ---"
cd "$ROOT/frontend"
npm install
echo "Frontend dependencies installed"

# ---- Docker services ----
echo ""
echo "--- Starting infrastructure (MySQL, Redis, Milvus) ---"
cd "$ROOT"
docker compose up -d mysql redis milvus etcd minio 2>/dev/null || \
    docker-compose up -d mysql redis milvus etcd minio 2>/dev/null || \
    echo "Docker Compose not available; start MySQL, Redis, Milvus manually"

echo ""
echo "=== Setup complete ==="
echo "Run './scripts/start_dev.sh' to start the application"
echo "Or manually:"
echo "  backend: cd backend && source venv/bin/activate && uvicorn src.main:app --reload --host 0.0.0.0 --port 8000"
echo "  frontend: cd frontend && npm run dev"
