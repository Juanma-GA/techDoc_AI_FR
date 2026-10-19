#!/usr/bin/env bash
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$APP_DIR/../.." && pwd)"
PORT="${PORT:-8085}"
if ! [[ "$PORT" =~ ^[0-9]+$ ]] || (( PORT < 1024 || PORT > 65515 )); then
    echo "[error] PORT must be between 1024 and 65515." >&2
    exit 1
fi
if [[ -f "$REPO_ROOT/scripts/build_pdf_toolkit.mjs" ]]; then
    node "$REPO_ROOT/scripts/build_pdf_toolkit.mjs" --allow-stale
fi
BINARY="$APP_DIR/backend/bin/pdf-toolkit-backend"
if [[ ! -x "$BINARY" ]]; then
    echo "[error] Missing PDF Toolkit binary: $BINARY" >&2
    exit 1
fi
command -v lsof >/dev/null || { echo "[error] lsof is required." >&2; exit 1; }
PORT_MAX=$((PORT + 20))
while lsof -iTCP:"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; do
    PORT=$((PORT + 1))
    if (( PORT > PORT_MAX )); then
        echo "[error] No free local port." >&2
        exit 1
    fi
done
export PDF_TOOLKIT_ADDR="127.0.0.1:$PORT"
export PDF_TOOLKIT_OPEN_BROWSER=0
echo "[run] Open http://$PDF_TOOLKIT_ADDR/ ; Ctrl+C to stop."
exec "$BINARY"
