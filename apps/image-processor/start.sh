#!/usr/bin/env bash
# image-processor local launcher: PaddleOCR and LaMa on Python 3.11.

set -euo pipefail

PORT="${PORT:-8010}"
LAMA_PORT="${LAMA_PORT:-8011}"
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="${APP_DIR}/backend"
LAMA_DIR="${BACKEND_DIR}/lama_service"
FRONTEND_DIR="${APP_DIR}/frontend"

echo "============================================================"
echo " image-processor - Local launch"
echo "============================================================"

if command -v python3.11 >/dev/null 2>&1; then
    MAIN_BASE_PYTHON="$(command -v python3.11)"
elif command -v python3 >/dev/null 2>&1 && \
    python3 -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 11))'; then
    MAIN_BASE_PYTHON="$(command -v python3)"
else
    echo "[error] Python 3.11 is required for PaddleOCR."
    exit 1
fi

if ! command -v python3.11 >/dev/null 2>&1; then
    echo "[error] Python 3.11 is required for the local LaMa service."
    exit 1
fi
if ! command -v lsof >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
    echo "[error] lsof and curl are required by the local launcher."
    exit 1
fi

cd "${BACKEND_DIR}"
mkdir -p data/storage
if [[ ! -x .venv/bin/python ]]; then
    echo "[setup] Creating Python 3.11 OCR environment..."
    "${MAIN_BASE_PYTHON}" -m venv .venv
fi
MAIN_PYTHON="${BACKEND_DIR}/.venv/bin/python"
if ! "${MAIN_PYTHON}" -c 'import sys; raise SystemExit(sys.version_info[:2] != (3, 11))'; then
    echo "[error] Existing OCR environment is not Python 3.11."
    echo "[info] Remove backend/.venv and relaunch to recreate it."
    exit 1
fi
if [[ ! -f .venv/.image-processor-installed ]]; then
    echo "[setup] Installing PaddleOCR backend dependencies..."
    "${MAIN_PYTHON}" -m pip install --upgrade pip setuptools wheel
    "${MAIN_PYTHON}" -m pip install --no-build-isolation -e .
    touch .venv/.image-processor-installed
fi

if [[ ! -x "${LAMA_DIR}/.venv/bin/python" ]]; then
    echo "[setup] Creating Python 3.11 LaMa environment..."
    python3.11 -m venv "${LAMA_DIR}/.venv"
fi
LAMA_PYTHON="${LAMA_DIR}/.venv/bin/python"
if [[ ! -f "${LAMA_DIR}/.venv/.image-processor-lama-installed" ]]; then
    echo "[setup] Installing local LaMa dependencies..."
    "${LAMA_PYTHON}" -m pip install --upgrade pip setuptools wheel
    "${LAMA_PYTHON}" -m pip install --no-build-isolation -e "${LAMA_DIR}"
    touch "${LAMA_DIR}/.venv/.image-processor-lama-installed"
fi

port_is_listening() {
    lsof -iTCP:"$1" -sTCP:LISTEN -P -n >/dev/null 2>&1
}

PORT_START="$PORT"
PORT_MAX=$((PORT_START + 20))
while port_is_listening "$PORT"; do
    PORT=$((PORT + 1))
    if (( PORT > PORT_MAX )); then
        echo "[error] No free API port in the configured range."
        exit 1
    fi
done
if [[ "$PORT" != "$PORT_START" ]]; then
    echo "[info] API port ${PORT_START} is busy; using ${PORT}."
fi

LAMA_REUSE=0
LAMA_START="$LAMA_PORT"
LAMA_MAX=$((LAMA_START + 20))
while true; do
    if [[ "$LAMA_PORT" != "$PORT" ]]; then
        if [[ "$LAMA_PORT" == "8011" ]] && \
            curl -fsS --max-time 2 "http://127.0.0.1:${LAMA_PORT}/health" >/dev/null 2>&1; then
            LAMA_REUSE=1
            break
        fi
        if ! port_is_listening "$LAMA_PORT"; then
            break
        fi
    fi
    LAMA_PORT=$((LAMA_PORT + 1))
    if (( LAMA_PORT > LAMA_MAX )); then
        echo "[error] No free local port for the LaMa service."
        exit 1
    fi
done

LAMA_PID=""
cleanup() {
    if [[ -n "$LAMA_PID" ]]; then
        kill "$LAMA_PID" 2>/dev/null || true
        wait "$LAMA_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$LAMA_REUSE" == "0" ]]; then
    echo "[run] Starting local LaMa service on port ${LAMA_PORT}..."
    (
        cd "${LAMA_DIR}"
        exec "${LAMA_PYTHON}" -m uvicorn app:app --host 127.0.0.1 --port "${LAMA_PORT}"
    ) &
    LAMA_PID=$!

    lama_ready=0
    for _ in $(seq 1 180); do
        if curl -fsS --max-time 2 "http://127.0.0.1:${LAMA_PORT}/health" >/dev/null 2>&1; then
            lama_ready=1
            break
        fi
        if ! kill -0 "$LAMA_PID" 2>/dev/null; then
            echo "[error] LaMa service exited before becoming ready."
            exit 1
        fi
        sleep 1
    done
    if [[ "$lama_ready" != "1" ]]; then
        echo "[error] LaMa service did not become ready within 180 seconds."
        exit 1
    fi
fi

export LAMA_SERVICE_PORT="${LAMA_PORT}"
echo "[setup] Applying database migrations..."
"${MAIN_PYTHON}" -m alembic upgrade head

# Rebuild only when the bundle is absent or a frontend source is newer.
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
        echo "[setup] Building React frontend..."
        if [[ ! -d "${FRONTEND_DIR}/node_modules" ]] && \
            ! (cd "${FRONTEND_DIR}" && { [ -d node_modules ] || pnpm install; }); then
            echo "[error] Frontend dependencies could not be installed."
            exit 1
        fi
        if ! (cd "${FRONTEND_DIR}" && pnpm build); then
            if [[ ! -f "$dist_index" ]]; then
                echo "[error] Frontend build failed and no valid dist bundle is available."
                exit 1
            fi
            echo "[warn] Build failed; serving the existing frontend bundle."
        fi
    fi
fi

echo
echo "[run] App: http://127.0.0.1:${PORT}/"
echo "      LaMa: http://127.0.0.1:${LAMA_PORT}/health"
echo "      API docs: http://127.0.0.1:${PORT}/api/v1/docs"
echo "      Ctrl+C here to stop the services."
echo

if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 &
elif command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:${PORT}/" >/dev/null 2>&1 &
fi

"${MAIN_PYTHON}" -m uvicorn app.main:app --host 127.0.0.1 --port "${PORT}"
