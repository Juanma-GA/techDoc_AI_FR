# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# doc-writer - image de deploiement (Azure Container Apps).
# Build context = RACINE du monorepo (le front consomme @internal/ui et
# @internal/design-tokens via le workspace pnpm).
#
#   az acr build -r <acr> -f apps/doc-writer/deploy/azure/Dockerfile -t doc-writer:<tag> .
#
# Palier 2 (deploiement expose) : voir apps/doc-writer/deploy/azure/README.md.
# Le garde-fou de securite (app/main._validate_security_posture) EXIGE
# ENCRYPTION_KEY + CORS_ORIGINS de prod des que BIND_HOST != 127.0.0.1.
# ---------------------------------------------------------------------------

# ==== Stage 1 : build du front React (Vite) ================================
FROM node:22-bookworm-slim AS frontend
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
WORKDIR /repo

# Manifeste workspace + lockfile + tsconfig de base (les tsconfig du front en
# heritent via ../../../tsconfig.base.json) d'abord (cache Docker).
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml tsconfig.base.json ./
# Uniquement les packages necessaires au build du front doc-writer.
COPY design-tokens ./design-tokens
COPY packages ./packages
COPY apps/doc-writer/frontend ./apps/doc-writer/frontend

# Install workspace (network propre dans ACR : pas de proxy TLS corporate,
# donc pas de blocage "in 1 minute" - cf. CLAUDE.md regle #12).
RUN pnpm install --no-frozen-lockfile
RUN pnpm --filter @apps/doc-writer-frontend build
# -> /repo/apps/doc-writer/frontend/dist

# ==== Stage 2 : runtime Python =============================================
FROM python:3.12-slim-bookworm AS runtime
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Deps systeme : Tesseract (repli OCR local best-effort), libs image pour
# PyMuPDF/pdf2docx, polices. Tout est facultatif au runtime (degradation
# gracieuse) mais evite les surprises.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng \
        fonts-dejavu-core \
        libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Backend (le package "app" + alembic + pyproject). data/ est exclu par
# .dockerignore : on n'embarque JAMAIS les donnees utilisateur.
WORKDIR /app/backend
COPY apps/doc-writer/backend/ /app/backend/
RUN pip install .

# Front buildé, place la ou main.py le cherche :
#   FRONTEND_DIST = <racine app>/frontend/dist  (=/app/frontend/dist)
COPY --from=frontend /repo/apps/doc-writer/frontend/dist /app/frontend/dist

COPY apps/doc-writer/deploy/azure/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Utilisateur non-root. On pre-cree /data (montage persistant OU dossier
# ephemere) et on le donne a appuser : sinon le mkdir/ecriture SQLite de
# l'entrypoint echoue en non-root et le conteneur crashe au demarrage.
RUN useradd -m -u 10001 appuser \
    && mkdir -p /data/storage \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
