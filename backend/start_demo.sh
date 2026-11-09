#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "[1/3] Starting PostgreSQL if needed..."
if ! pg_isready -h 127.0.0.1 -p 5432 -q; then
    sudo -n -u root pg_ctlcluster 16 main start
fi

echo "[2/3] Checking database..."
if ! .venv/bin/python - <<'PY'
from dotenv import dotenv_values
from sqlalchemy import create_engine, text

url = dotenv_values(".env")["DATABASE_URL"]
engine = create_engine(url, connect_args={"connect_timeout": 5})

try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("Database connection: OK")
finally:
    engine.dispose()
PY
then
    echo "Database connection failed."
    echo "Check PostgreSQL role/database or restore from backup."
    exit 1
fi

echo "[3/3] Starting FastAPI..."
export GEMINI_ENABLED=false

exec .venv/bin/python -B -m uvicorn main:app \
    --host 0.0.0.0 --port 8000 --workers 1
