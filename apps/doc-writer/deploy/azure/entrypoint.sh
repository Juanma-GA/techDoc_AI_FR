#!/bin/sh
# doc-writer - entrypoint conteneur (Azure Container Apps).
# 1) prepare le volume persistant (SQLite + fichiers), 2) migrations Alembic,
# 3) prefetch police Inter (best-effort), 4) uvicorn expose sur 0.0.0.0:8000.
set -e

: "${STORAGE_DIR:=/data/storage}"
: "${PORT:=8000}"

mkdir -p "$STORAGE_DIR"
# Le repertoire de la DB SQLite (DATABASE_URL=sqlite:////data/doc-writer.db).
mkdir -p /data

echo "[entrypoint] Migrations Alembic..."
alembic upgrade head

echo "[entrypoint] Police Inter (best-effort)..."
python -c "from app.core.fonts import ensure_inter; ensure_inter()" 2>/dev/null \
    || echo "[entrypoint] Inter non telechargee, exports PDF en Helvetica."

echo "[entrypoint] uvicorn 0.0.0.0:${PORT}"
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
