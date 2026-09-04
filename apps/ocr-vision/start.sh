#!/usr/bin/env bash
# OCR Vision — Lancement local Unix.
# Détection Python 3.11+, venv, deps, migrations, uvicorn.

set -euo pipefail

# Port unique (à ajuster par POC : 8001, 8002, ...)
PORT="${PORT:-8003}"

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="${APP_DIR}/backend"

echo "============================================================"
echo " OCR Vision - Lancement local"
echo "============================================================"

if ! command -v python3 >/dev/null 2>&1; then
    echo "[erreur] Python 3.11+ introuvable. Installe-le et relance."
    exit 1
fi

cd "${BACKEND_DIR}"
mkdir -p data/storage

if [[ ! -d .venv ]]; then
    echo "[setup] Création du venv..."
    python3 -m venv .venv
fi
# shellcheck source=/dev/null
source .venv/bin/activate

if [[ ! -f .venv/.installed ]]; then
    echo "[setup] Installation des deps Python..."
    pip install --upgrade pip >/dev/null
    pip install -e .
    touch .venv/.installed
fi

echo "[setup] Migrations Alembic..."
alembic upgrade head

FRONTEND_DIR="${APP_DIR}/frontend"
if command -v pnpm >/dev/null 2>&1; then
    NEED_BUILD=0
    if [[ ! -f "${FRONTEND_DIR}/dist/index.html" ]]; then
        NEED_BUILD=1
    elif find "${FRONTEND_DIR}/src" "${FRONTEND_DIR}/index.html" "${FRONTEND_DIR}/package.json" \
        "${FRONTEND_DIR}/vite.config.ts" "${FRONTEND_DIR}/tailwind.config.ts" \
        "${FRONTEND_DIR}/postcss.config.js" -type f -newer "${FRONTEND_DIR}/dist/index.html" \
        -print -quit | grep -q .; then
        NEED_BUILD=1
    fi
    if [[ "$NEED_BUILD" -eq 1 ]]; then
        echo "[setup] Build du front React - dist absent ou sources modifiees..."
        cd "${FRONTEND_DIR}"
        [ -d node_modules ] || pnpm install
        pnpm build
        cd "${BACKEND_DIR}"
    fi
fi

# Vérifier que le port est libre
if command -v lsof >/dev/null 2>&1 && lsof -iTCP:"$PORT" -sTCP:LISTEN -P -n >/dev/null 2>&1; then
    echo "[erreur] Le port $PORT est deja utilise :"
    lsof -iTCP:"$PORT" -sTCP:LISTEN -P -n
    exit 1
fi

echo
echo "[run] Backend sur http://127.0.0.1:${PORT}/"
echo "      OpenAPI docs : http://127.0.0.1:${PORT}/api/v1/docs"
echo "      Ctrl+C ici pour arrêter."
echo

if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:${PORT}/api/v1/docs" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:${PORT}/api/v1/docs" >/dev/null 2>&1 &
fi

exec python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
