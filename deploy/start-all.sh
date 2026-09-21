#!/bin/bash
# Arranca todos los backends AtexisPOCS.
# Llamado desde .coder-startup.sh al despertar el contenedor.
set -uo pipefail

declare -A PORTS=(
  [corpus-agent]=8001
  [doc-writer]=8002
  [doc-reviewer]=8003
  [xml-proofreader]=8004
  [catia-toolbox]=8006
  [ocr-vision]=8007
  [s1000d-extractor]=8008
)

BASE=/home/coder/atexispocs

for poc in corpus-agent doc-writer doc-reviewer xml-proofreader catia-toolbox ocr-vision s1000d-extractor; do
  port=${PORTS[$poc]}
  echo "[$(date -Is)] Starting $poc on port $port"
  pkill -f "uvicorn.*$port" 2>/dev/null || true
  sleep 1
  cd "$BASE/$poc/backend"
  . .venv/bin/activate
  BIND_HOST=127.0.0.1 BIND_PORT=$port nohup python -m uvicorn app.main:app --host 127.0.0.1 --port $port > "$BASE/$poc/backend.log" 2>&1 &
  deactivate
done

# --- Portal (MFA login + shared session cookie, port 8005) ---
echo "[$(date -Is)] Starting portal-backend on port 8005"
pkill -f "uvicorn.*port 8005" 2>/dev/null || true
sleep 1
cd "$BASE/portal-backend"
nohup ./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8005 > "$BASE/portal-backend/backend.log" 2>&1 &

sleep 5
echo "=== AtexisPOCS health checks ==="
for poc in corpus-agent doc-writer doc-reviewer xml-proofreader catia-toolbox ocr-vision s1000d-extractor; do
  port=${PORTS[$poc]}
  status=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:$port/api/v1/health 2>/dev/null)
  echo "$poc (:$port): $status"
done
status=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8005/api/health 2>/dev/null)
echo "portal (:8005): $status"
