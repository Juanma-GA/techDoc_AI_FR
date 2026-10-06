#!/usr/bin/env bash
# TEMPLATE — Lancement local Unix.
# Détection Python 3.11+, venv, deps, migrations, rebuild front auto, uvicorn.
# Le front React est reconstruit automatiquement quand frontend/dist est absent
# OU qu'une source front est plus récente (comparaison find -newer) : une modif
# du code front est prise en compte au prochain start.sh, sans supprimer dist.

set -euo pipefail

# Port unique (configurable via PORT), puis premier port libre suivant.
PORT="${PORT:-8003}"
REQUESTED_PORT="$PORT"
PORT_MAX=$((PORT + 20))

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="${APP_DIR}/backend"

echo "============================================================"
echo " Doc Reviewer - Lancement local"
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

# Reinstalle si le marker est absent OU si pyproject.toml a change depuis le
# dernier install (hash stocke dans le marker). H-02 hardening : un marker
# vide ne se reinvalide jamais -- une dependance ajoutee a pyproject.toml
# (ex. regex) ne s'installait plus du tout sur un poste ou doc-reviewer
# avait deja tourne avant le pull.
pyproject_hash() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum pyproject.toml | awk '{print $1}'
    else
        shasum -a 256 pyproject.toml | awk '{print $1}'
    fi
}
need_install=0
if [[ ! -f .venv/.installed ]]; then
    need_install=1
elif [[ "$(pyproject_hash)" != "$(cat .venv/.installed)" ]]; then
    need_install=1
fi
if [[ "$need_install" == "1" ]]; then
    echo "[setup] Installation des deps Python..."
    pip install --upgrade pip >/dev/null
    pip install -e .
    pyproject_hash > .venv/.installed
fi

# Auto-provision ENCRYPTION_KEY en posture locale (hardening H-03) : sans
# elle, POST /settings/mistral refuse TOUTE sauvegarde de cle Mistral (503)
# tant qu'un humain n'a pas genere+colle une cle Fernet a la main dans
# backend/.env. Inerte des que BIND_HOST s'ecarte du defaut local
# 127.0.0.1 : ce cas (deploiement palier 2/3) reste gere par
# app.main._validate_security_posture, qui EXIGE une cle fournie par l'IT
# et refuse de demarrer sans elle -- une auto-provision serait dangereuse
# hors du poste local du developpeur.
ENV_FILE=".env"
bind_host_value=""
[[ -f "$ENV_FILE" ]] && bind_host_value="$(grep -m1 '^BIND_HOST=' "$ENV_FILE" | cut -d= -f2-)"
encryption_key_value=""
[[ -f "$ENV_FILE" ]] && encryption_key_value="$(grep -m1 '^ENCRYPTION_KEY=' "$ENV_FILE" | cut -d= -f2-)"
if [[ ( -z "$bind_host_value" || "$bind_host_value" == "127.0.0.1" ) && -z "$encryption_key_value" ]]; then
    echo "[setup] Generation d'une cle de chiffrement locale (ENCRYPTION_KEY)..."
    new_key="$(python -c "from app.core.encryption import generate_key; print(generate_key())")"
    if [[ -z "$new_key" ]]; then
        echo "[erreur] Echec generation de la cle de chiffrement."
        exit 1
    fi
    echo "ENCRYPTION_KEY=${new_key}" >> "$ENV_FILE"
    echo "[setup] OK -- cle ecrite dans backend/.env."
fi

echo "[setup] Migrations Alembic..."
alembic upgrade head

# Chercher le premier port libre dans la plage autorisee.
if command -v lsof >/dev/null 2>&1; then
    while lsof -iTCP:"$PORT" -sTCP:LISTEN -P -n >/dev/null 2>&1; do
        if (( PORT >= PORT_MAX )); then
            echo "[erreur] Aucun port libre entre $REQUESTED_PORT et $PORT_MAX."
            exit 1
        fi
        PORT=$((PORT + 1))
    done
fi
if [[ "$PORT" != "$REQUESTED_PORT" ]]; then
    echo "[info] Le port $REQUESTED_PORT est occupe - bascule automatique sur $PORT."
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
