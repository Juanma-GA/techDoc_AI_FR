#!/usr/bin/env bash
# scripts/new_poc.sh
# Instancie un nouveau POC a partir de apps/_template/ en effectuant
# toutes les substitutions identifiees dans STANDARD_POC.md section 11.
#
# Usage :
#     bash scripts/new_poc.sh <slug> [<port>]
#
# Exemples :
#     bash scripts/new_poc.sh mon-poc          # port auto (prochain libre >= 8000)
#     bash scripts/new_poc.sh mon-poc 8005     # port explicite
#
# Ce que le script fait :
#     1. Verifie que apps/<slug>/ n'existe pas, que <slug> est en kebab-case,
#        et que le port choisi n'est pas deja pris par un autre POC du repo.
#     2. Copie apps/_template/ -> apps/<slug>/.
#     3. Substitue tous les marqueurs TEMPLATE / 8000 / 'template' dans :
#          - pyproject.toml, config.py, alembic.ini, .env.example
#          - _run.bat, start.bat, package.bat, _package.bat, start.sh
#          - frontend/package.json, vite.config.ts, index.html
#          - frontend/src/locales/{fr,en}.json
#     4. Genere scripts/package_<slug>.py depuis package_TEMPLATE.py
#        (avec APP_NAME / APP_SLUG / EMBED_PREFIX adaptes).
#     5. Ajoute dev:<slug>, test:e2e:<slug>, openapi:gen:<slug> dans le
#        package.json racine.
#     6. Ecrase apps/<slug>/README.md par un stub avec banniere "A REECRIRE".
#     7. Execute scripts/check_standard.sh pour valider l'instanciation.
#
# Apres ca, l'utilisateur doit :
#     - Reecrire apps/<slug>/README.md (titre + description metier + endpoints)
#     - Ajouter sa logique metier dans backend/app/api/ + frontend/src/routes/
#     - Adapter backend/app/templates/preview.html si mode preview HTML utilise
#
# Sortie : exit 0 = OK, exit 1 = echec (rollback du dossier copie).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ----------------------------------------------------------------------
# 1. Parse args + validation
# ----------------------------------------------------------------------
SLUG="${1:-}"
PORT_ARG="${2:-}"

if [[ -z "$SLUG" ]]; then
    echo "[erreur] Usage : bash scripts/new_poc.sh <slug> [<port>]"
    echo "         <slug> doit etre en kebab-case (ex. mon-poc, ocr-vision)."
    exit 1
fi

if ! [[ "$SLUG" =~ ^[a-z][a-z0-9]*(-[a-z0-9]+)*$ ]]; then
    echo "[erreur] '$SLUG' n'est pas en kebab-case."
    echo "         Format attendu : lettres minuscules + chiffres + tirets,"
    echo "         demarre par une lettre. Ex. 'mon-poc', 'doc-reviewer'."
    exit 1
fi

if [[ "$SLUG" == "_template" ]] || [[ "$SLUG" == "template" ]]; then
    echo "[erreur] '$SLUG' est reserve."
    exit 1
fi

APP_DIR="apps/$SLUG"
if [[ -d "$APP_DIR" ]]; then
    echo "[erreur] $APP_DIR existe deja. Choisis un autre slug ou supprime le dossier."
    exit 1
fi

if [[ ! -d "apps/_template" ]]; then
    echo "[erreur] apps/_template/ introuvable. Ce repo n'est pas un monorepo POC valide."
    exit 1
fi

# Detection Python portable (Unix : python3 ; Git Bash sur Windows : python).
PYTHON_BIN=""
for candidate in python3 python py; do
    if command -v "$candidate" >/dev/null 2>&1; then
        # Filtre les alias Windows qui ne sont pas Python (App execution alias).
        if "$candidate" --version >/dev/null 2>&1; then
            PYTHON_BIN="$candidate"
            break
        fi
    fi
done
if [[ -z "$PYTHON_BIN" ]]; then
    echo "[erreur] Python 3.11+ introuvable (cherche : python3, python, py)."
    exit 1
fi

# ----------------------------------------------------------------------
# 2. Resolution du port
# ----------------------------------------------------------------------
declare -A USED_PORTS=()
for runbat in apps/*/_run.bat; do
    [[ -f "$runbat" ]] || continue
    [[ "$runbat" == "apps/_template/_run.bat" ]] && continue
    p=$(grep -oE 'set "PORT=[0-9]+"' "$runbat" | head -1 | grep -oE '[0-9]+' || true)
    [[ -n "$p" ]] && USED_PORTS[$p]=1
done

if [[ -n "$PORT_ARG" ]]; then
    if ! [[ "$PORT_ARG" =~ ^[0-9]+$ ]] || (( PORT_ARG < 1024 || PORT_ARG > 65535 )); then
        echo "[erreur] Port '$PORT_ARG' invalide (attendu : entier entre 1024 et 65535)."
        exit 1
    fi
    if [[ -n "${USED_PORTS[$PORT_ARG]:-}" ]]; then
        echo "[erreur] Port $PORT_ARG est deja utilise par un autre POC du repo."
        echo "         Ports occupes :" "${!USED_PORTS[@]}"
        exit 1
    fi
    PORT="$PORT_ARG"
else
    PORT=8000
    while [[ -n "${USED_PORTS[$PORT]:-}" ]]; do
        PORT=$((PORT + 1))
        if (( PORT > 8099 )); then
            echo "[erreur] Aucun port libre entre 8000 et 8099."
            exit 1
        fi
    done
fi

echo "[info] Slug      : $SLUG"
echo "[info] Port      : $PORT"
echo "[info] Cible     : $APP_DIR"
echo

# ----------------------------------------------------------------------
# 3. Copie du template
# ----------------------------------------------------------------------
cp -r apps/_template "$APP_DIR"
# Filets : retire venv / caches / data eventuels (jamais committes mais
# au cas ou le dev aurait teste le template localement).
rm -rf "$APP_DIR/backend/.venv" \
       "$APP_DIR/backend/__pycache__" \
       "$APP_DIR/backend/data" \
       "$APP_DIR/frontend/node_modules" \
       "$APP_DIR/frontend/dist" \
       "$APP_DIR/dist"

# Rollback en cas d'echec
ROLLBACK_DIR="$APP_DIR"
trap 'echo; echo "[erreur] Instanciation interrompue, rollback de $ROLLBACK_DIR/."; rm -rf "$ROLLBACK_DIR"' ERR

# ----------------------------------------------------------------------
# 4. Substitutions
# ----------------------------------------------------------------------
# Titre humain : "ocr-vision" -> "Ocr Vision" (l'utilisateur raffine apres).
TITLE_HUMAN="$(echo "$SLUG" | sed -E 's/(^|-)([a-z])/\1\u\2/g; s/-/ /g')"

# In-place sed portable (suffix .bak puis suppression).
sed_inplace() {
    local file="$1"; shift
    sed -i.bak "$@" "$file"
    rm -f "$file.bak"
}

# Backend
sed_inplace "$APP_DIR/backend/pyproject.toml" \
    -e "s|TEMPLATE-backend|${SLUG}-backend|g" \
    -e "s|TEMPLATE —|${TITLE_HUMAN} —|g"

sed_inplace "$APP_DIR/backend/app/config.py" \
    -e "s|app_name: str = \"TEMPLATE\"|app_name: str = \"${TITLE_HUMAN}\"|g" \
    -e "s|'TEMPLATE.db'|'${SLUG}.db'|g"

sed_inplace "$APP_DIR/backend/alembic.ini" \
    -e "s|sqlite:///./data/TEMPLATE.db|sqlite:///./data/${SLUG}.db|g"

sed_inplace "$APP_DIR/backend/.env.example" \
    -e "s|APP_NAME=TEMPLATE|APP_NAME=${TITLE_HUMAN}|g" \
    -e "s|./data/TEMPLATE.db|./data/${SLUG}.db|g"

# Lanceurs Windows : remplacer TEMPLATE comme nom d'app + le port
sed_inplace "$APP_DIR/_run.bat" \
    -e "s|set \"PORT=8000\"|set \"PORT=${PORT}\"|g" \
    -e "s|TEMPLATE|${SLUG}|g" \
    -e "s|\\.${SLUG}_installed|.${SLUG}_installed|g"

sed_inplace "$APP_DIR/start.bat" \
    -e "s|TEMPLATE|${SLUG}|g"

sed_inplace "$APP_DIR/_package.bat" \
    -e "s|scripts\\\\package_TEMPLATE\\.py|scripts\\\\package_${SLUG}.py|g" \
    -e "s|apps\\\\_template\\\\dist|apps\\\\${SLUG}\\\\dist|g" \
    -e "s|TEMPLATE|${SLUG}|g"

sed_inplace "$APP_DIR/package.bat" \
    -e "s|TEMPLATE|${SLUG}|g"

# Lanceur Unix
sed_inplace "$APP_DIR/start.sh" \
    -e "s|PORT:-8000|PORT:-${PORT}|g" \
    -e "s|TEMPLATE|${SLUG}|g"

# Frontend
sed_inplace "$APP_DIR/frontend/package.json" \
    -e "s|@apps/TEMPLATE-frontend|@apps/${SLUG}-frontend|g" \
    -e "s|127\\.0\\.0\\.1:8000|127.0.0.1:${PORT}|g"

sed_inplace "$APP_DIR/frontend/index.html" \
    -e "s|<title>TEMPLATE</title>|<title>${TITLE_HUMAN}</title>|g"

sed_inplace "$APP_DIR/frontend/vite.config.ts" \
    -e "s|127\\.0\\.0\\.1:8000|127.0.0.1:${PORT}|g"

# Locales : remplace la valeur "TEMPLATE" du champ app.title.
sed_inplace "$APP_DIR/frontend/src/locales/fr.json" \
    -e "s|\"title\": \"TEMPLATE\"|\"title\": \"${TITLE_HUMAN}\"|g"

sed_inplace "$APP_DIR/frontend/src/locales/en.json" \
    -e "s|\"title\": \"TEMPLATE\"|\"title\": \"${TITLE_HUMAN}\"|g"

# Backend README + docstring SQLAlchemy + preview HTML + App.tsx + E2E test.
# Note : _TEMPLATE_PATH dans api/preview.py est un nom de variable interne
# (chemin vers backend/app/templates/preview.html), on le laisse.
sed_inplace "$APP_DIR/backend/README.md" \
    -e "s|^# TEMPLATE\b|# ${TITLE_HUMAN}|"

sed_inplace "$APP_DIR/backend/app/db/models.py" \
    -e "s|squelette TEMPLATE|squelette ${TITLE_HUMAN}|g"

# preview.html a ete supprime par la migration React-only : on ne le sed que
# s'il existe encore (retro-compat template ancien).
if [[ -f "$APP_DIR/backend/app/templates/preview.html" ]]; then
    sed_inplace "$APP_DIR/backend/app/templates/preview.html" \
        -e "s|<title>TEMPLATE</title>|<title>${TITLE_HUMAN}</title>|g" \
        -e "s|class=\"brand\">TEMPLATE</span>|class=\"brand\">${TITLE_HUMAN}</span>|g"
fi

sed_inplace "$APP_DIR/frontend/src/App.tsx" \
    -e "s|>TEMPLATE<|>${TITLE_HUMAN}<|g"

sed_inplace "$APP_DIR/frontend/tests/e2e/home.spec.ts" \
    -e "s|/TEMPLATE/|/${TITLE_HUMAN}/|g"

# Fixe le port CORS par defaut dans config.py : la ligne 8000 du template
# doit pointer sur le port reel du POC pour autoriser les requetes depuis
# le preview backend lui-meme.
sed_inplace "$APP_DIR/backend/app/config.py" \
    -e "s|\"http://localhost:8000\"|\"http://localhost:${PORT}\"|g"

# ----------------------------------------------------------------------
# 5. Script de packaging
# ----------------------------------------------------------------------
PKG_SRC="scripts/package_TEMPLATE.py"
PKG_DST="scripts/package_${SLUG}.py"
if [[ ! -f "$PKG_SRC" ]]; then
    echo "[erreur] $PKG_SRC introuvable."
    exit 1
fi

cp "$PKG_SRC" "$PKG_DST"
EMBED_PREFIX="${SLUG//-/_}"

sed_inplace "$PKG_DST" \
    -e "1,30 s|TEMPLATE|${SLUG}|g" \
    -e "s|APP_NAME = \"TEMPLATE\"|APP_NAME = \"${TITLE_HUMAN}\"|" \
    -e "s|APP_SLUG = \"_template\"|APP_SLUG = \"${SLUG}\"|" \
    -e "s|EMBED_PREFIX = \"template\"|EMBED_PREFIX = \"${EMBED_PREFIX}\"|"

# ----------------------------------------------------------------------
# 6. README stub (banniere claire)
# ----------------------------------------------------------------------
cat > "$APP_DIR/README.md" <<EOF
# ${SLUG}

> **A REECRIRE.** Ce README a ete genere automatiquement par
> \`scripts/new_poc.sh\`. Remplacez ce contenu par la description metier
> du POC (cf. \`apps/doc-writer/README.md\` ou \`apps/doc-reviewer/README.md\`
> comme references).

Conforme a [\`STANDARD_POC.md\`](../../STANDARD_POC.md). Bootstrap depuis
[\`apps/_template\`](../_template/).

## Auth

**Palier** : 1 - local seul, bind \`127.0.0.1\`, pas d'authentification.

## Stack

| Couche | Choix |
|---|---|
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog |
| LLM | Mistral via \`httpx\` async (pas de SDK) |
| Frontend | React 18 + TS + Vite + Tailwind + RHF + Zod + i18next + Zustand + TanStack Query |
| UI | \`@internal/ui\` exclusivement |
| Persistance | SQLite par defaut (\`backend/data/${SLUG}.db\`), Alembic des J1 |

## Demarrage rapide

Double-clic sur \`start.bat\` (Windows) ou \`bash start.sh\` (Unix). Le backend
ecoute sur http://127.0.0.1:${PORT}/.

Frontend en mode dev (port 5173), depuis la racine du monorepo :

\`\`\`bash
pnpm install
pnpm dev:${SLUG}
\`\`\`

## TODO apres bootstrap

- [ ] Reecrire la section ci-dessus avec la description metier reelle.
- [ ] Ajouter la logique metier dans \`backend/app/api/<feature>.py\` + \`main.py\`.
- [ ] Definir les modeles SQLAlchemy dans \`backend/app/db/models.py\`.
- [ ] Generer la migration : \`alembic revision -m "0002 <feature>"\`.
- [ ] Adapter \`backend/app/templates/preview.html\` (onglets Home / Architecture).
- [ ] Implementer les routes React dans \`frontend/src/routes/\`.
- [ ] Mettre les libelles dans \`frontend/src/locales/{fr,en}.json\`.

## Ecarts au standard

Aucun.
EOF

# ----------------------------------------------------------------------
# 7. Wirage package.json racine (insertion avant la ligne de fermeture
# des scripts existants : on append derriere les blocs dev/test:e2e/
# openapi:gen)
# ----------------------------------------------------------------------
"$PYTHON_BIN" - "$SLUG" "$PORT" <<'PYEOF'
import json
import sys
from pathlib import Path

slug, port = sys.argv[1], sys.argv[2]
path = Path("package.json")
pkg = json.loads(path.read_text(encoding="utf-8"))

scripts = pkg.setdefault("scripts", {})

# dev:<slug>
scripts[f"dev:{slug}"] = (
    f'concurrently -n back,front -c blue,green '
    f'"cd apps/{slug}/backend && python -m uvicorn app.main:app --reload '
    f'--host 127.0.0.1 --port {port}" '
    f'"pnpm --filter @apps/{slug}-frontend dev"'
)
scripts[f"test:e2e:{slug}"] = (
    f"pnpm --filter @apps/{slug}-frontend --if-present test:e2e"
)
scripts[f"openapi:gen:{slug}"] = (
    f"pnpm --filter @apps/{slug}-frontend --if-present openapi:gen"
)

# Reordonne pour grouper dev:* / test:e2e:* / openapi:gen:*
def _key(k: str) -> tuple[int, str]:
    if k == "build":          return (0, k)
    if k == "lint":           return (1, k)
    if k == "test":           return (2, k)
    if k == "check-standard": return (3, k)
    if k.startswith("dev:"):           return (4, k)
    if k.startswith("test:e2e:"):      return (5, k)
    if k.startswith("openapi:gen:"):   return (6, k)
    return (9, k)

pkg["scripts"] = {k: scripts[k] for k in sorted(scripts.keys(), key=_key)}
path.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
PYEOF

trap - ERR

echo "[ok]  $APP_DIR/ instancie."
echo "[ok]  $PKG_DST genere."
echo "[ok]  package.json : scripts dev:${SLUG} / test:e2e:${SLUG} / openapi:gen:${SLUG} ajoutes."
echo

# ----------------------------------------------------------------------
# 8. Verification standard
# ----------------------------------------------------------------------
echo "[check] Execution de scripts/check_standard.sh..."
if bash scripts/check_standard.sh; then
    echo
    echo "[done] POC '$SLUG' pret. Prochaines etapes :"
    echo "       - Reecrire $APP_DIR/README.md (description metier + endpoints)"
    echo "       - Ajouter la logique metier dans $APP_DIR/backend/app/api/"
    echo "       - Adapter $APP_DIR/backend/app/templates/preview.html"
    echo "       - Tester : double-clic sur $APP_DIR/start.bat (ou bash $APP_DIR/start.sh)"
else
    echo
    echo "[warn] check_standard.sh a echoue. Inspecte les violations ci-dessus."
    echo "       Le POC est instancie mais doit etre corrige avant commit."
    exit 1
fi
