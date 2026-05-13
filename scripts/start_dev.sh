#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "=== Starting Multi-Agent Framework (Development) ==="

# ---- Infrastructure ----
echo ""
echo "--- Starting infrastructure services ---"
cd "$ROOT"
docker compose up -d mysql redis milvus etcd minio 2>/dev/null || \
    docker-compose up -d mysql redis milvus etcd minio 2>/dev/null || \
    echo "Docker Compose not found — assuming services are already running"

# Wait for MySQL
echo "Waiting for MySQL..."
for i in $(seq 1 30); do
    if docker exec multi-agent-mysql mysqladmin ping -h localhost --silent 2>/dev/null; then
        echo "MySQL is ready"
        break
    fi
    sleep 2
done

# ---- Run Alembic migrations ----
echo ""
echo "--- Running database migrations ---"
cd "$ROOT/backend"
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi
alembic upgrade head || echo "Alembic migration skipped (DB may not be ready)"

# ---- Start backend ----
echo ""
echo "--- Starting backend (port 8000) ---"
cd "$ROOT/backend"
if [ -d "venv" ]; then
    source venv/bin/activate 2>/dev/null || source venv/Scripts/activate 2>/dev/null
fi
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# ---- Start frontend ----
echo ""
echo "--- Starting frontend (port 5173) ---"
cd "$ROOT/frontend"
npm run dev &
FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

# ---- Cleanup on exit ----
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null || true
    kill $FRONTEND_PID 2>/dev/null || true
    wait
}
trap cleanup EXIT INT TERM

echo ""
echo "=== Services running ==="
echo "  Backend:  http://localhost:8000"
echo "  Frontend: http://localhost:5173"
echo "  API Docs: http://localhost:8000/docs"
echo "Press Ctrl+C to stop all services"

wait
