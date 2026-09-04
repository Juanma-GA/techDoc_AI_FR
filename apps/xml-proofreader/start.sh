#!/usr/bin/env bash
# XML Proofreader — Lancement local Unix.
# Détection Python 3.11+, venv, deps, migrations, rebuild front auto, uvicorn.
# Le front React est reconstruit automatiquement quand frontend/dist est absent
# OU qu'une source front est plus récente (comparaison find -newer) : une modif
# du code front est prise en compte au prochain start.sh, sans supprimer dist.

set -euo pipefail

# Port unique (à ajuster par POC : 8001, 8002, ...)
PORT="${PORT:-8000}"

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="${APP_DIR}/backend"

echo "============================================================"
echo " XML Proofreader - Lancement local"
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

# Vérifier que le port est libre
if command -v lsof >/dev/null 2>&1 && lsof -iTCP:"$PORT" -sTCP:LISTEN -P -n >/dev/null 2>&1; then
    echo "[erreur] Le port $PORT est deja utilise :"
    lsof -iTCP:"$PORT" -sTCP:LISTEN -P -n
    exit 1
fi

# Front React : rebuild auto si dist absent OU sources front plus recentes que
# le dernier build. Restart instantane si rien n'a change. Si pnpm est absent,
# on sert le dist existant tel quel (pas de rebuild).
FRONTEND_DIR="${APP_DIR}/frontend"
if command -v pnpm >/dev/null 2>&1; then
    need_build=0
    dist_index="${FRONTEND_DIR}/dist/index.html"
    if [[ ! -f "$dist_index" ]]; then
        need_build=1
    else
        newer="$(find "${FRONTEND_DIR}/src" "${FRONTEND_DIR}/index.html" \
            "${FRONTEND_DIR}/package.json" "${FRONTEND_DIR}/vite.config.ts" \
            "${FRONTEND_DIR}/tailwind.config.ts" "${FRONTEND_DIR}/postcss.config.js" \
            -newer "$dist_index" -print -quit 2>/dev/null || true)"
        [[ -n "$newer" ]] && need_build=1
    fi
    if [[ "$need_build" == "1" ]]; then
        echo "[setup] Build du front React - dist absent ou sources modifiees..."
        ( cd "${FRONTEND_DIR}" && { [ -d node_modules ] || pnpm install; } && pnpm build ) \
            || echo "[warn] Build front echoue : on sert le dist existant."
    fi
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
