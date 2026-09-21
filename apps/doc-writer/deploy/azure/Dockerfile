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
# F-08 (hardening) : pin par digest (immuable) plutot que par tag seul (un tag
# peut etre re-pousse vers une image differente en amont). Digest resout
# `node:22-bookworm-slim` au moment ou ce commentaire a ete ecrit ; regenerer
# via `docker buildx imagetools inspect node:22-bookworm-slim` si le tag doit
# etre rafraichi (nouveau patch de securite en amont, par ex.).
FROM node:22-bookworm-slim@sha256:83f487e0a63425e5b4d146fb5e5be574bcbe1b7b843d3ebafdd95eaf7767a7e5 AS frontend
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
# F-07 (hardening) : --frozen-lockfile (pas --no-frozen-lockfile) -> le build
# echoue si pnpm-lock.yaml et les package.json divergent, au lieu de re-resoudre
# silencieusement des versions differentes de celles verrouillees (build non
# reproductible). Le lockfile est copie juste au-dessus (COPY ... pnpm-lock.yaml).
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @apps/doc-writer-frontend build
# -> /repo/apps/doc-writer/frontend/dist

# ==== Stage 2 : runtime Python =============================================
# F-08 (hardening) : pin par digest, meme raison que le stage frontend
# ci-dessus. Regenerer via `docker buildx imagetools inspect
# python:3.12-slim-bookworm` si le tag doit etre rafraichi.
FROM python:3.12-slim-bookworm@sha256:782412e85d0f0984994c290652577d4018aff08145c85b262bb63dc0c7522254 AS runtime
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
# F-07 (hardening) : deps verrouillees + hash-verifiees (requirements.lock.txt)
# au lieu de re-resoudre les bornes ">=" de pyproject.toml a chaque build ->
# image reproductible. --no-deps ensuite : le paquet local seul.
RUN pip install -r requirements.lock.txt && pip install . --no-deps

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
