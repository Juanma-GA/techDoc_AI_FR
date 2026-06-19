#!/usr/bin/env bash
# scripts/check_standard.sh
# Structural conformance checks against STANDARD_POC.md.
# Exit 0 = clean. Exit 1 = at least one violation.
#
# Run from any directory:
#     bash scripts/check_standard.sh
#
# Excluded from every check: legacy/, node_modules, .venv, __pycache__,
# build/dist artefacts, Playwright reports, and the .git folder. The hex
# check additionally tolerates tokens.json (the canonical palette),
# tailwind-preset.ts (consumes tokens), theme.css + preview-skin.css (CSS
# variables for dark/light), and any *.test.* / tests/ file.

set -o pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

violations=0

EXCLUDE_DIRS=(node_modules .venv __pycache__ dist build .git playwright-report test-results coverage legacy)
exclude_args=()
for d in "${EXCLUDE_DIRS[@]}"; do
  exclude_args+=(--exclude-dir="$d")
done

step()  { printf "[%d/15] %-38s" "$1" "$2"; }
pass()  { printf " \033[32mok\033[0m\n"; }
fail()  { printf " \033[31mFAIL\033[0m\n"; violations=$((violations + 1)); printf '%b\n' "$1" | sed 's/^/    /'; }

# ------------------------------------------------------------------
# 1. Every FastAPI app mounts a router under /api/v1.
# ------------------------------------------------------------------
step 1 "FastAPI mounts /api/v1 prefix"
if compgen -G 'apps/*/backend/app/main.py' >/dev/null && \
   grep -lq 'prefix="/api/v1"' apps/*/backend/app/main.py 2>/dev/null; then
  pass
else
  fail "No 'prefix=\"/api/v1\"' found in apps/*/backend/app/main.py"
fi

# ------------------------------------------------------------------
# 2. No console.log in frontend src/.
# ------------------------------------------------------------------
step 2 "console.log absent in frontend"
hits=$(grep -rn "${exclude_args[@]}" --include='*.ts' --include='*.tsx' \
  'console\.log' apps/*/frontend/src 2>/dev/null || true)
if [[ -z "$hits" ]]; then pass; else
  fail "console.log forbidden in apps/*/frontend/src (use structured logging or remove):\n$hits"
fi

# ------------------------------------------------------------------
# 3. No print() in backend.
# ------------------------------------------------------------------
step 3 "print() absent in backend"
hits=$(grep -rnE "${exclude_args[@]}" --include='*.py' \
  '(^|[^A-Za-z_.])print\(' apps/*/backend/app 2>/dev/null || true)
if [[ -z "$hits" ]]; then pass; else
  fail "print() forbidden in apps/*/backend/app (use structlog):\n$hits"
fi

# ------------------------------------------------------------------
# 4. No hardcoded hex colors outside tokens.
# ------------------------------------------------------------------
step 4 "No hardcoded hex colors"
hits=$(grep -rEn "${exclude_args[@]}" \
  --include='*.ts' --include='*.tsx' --include='*.css' --include='*.py' --include='*.html' \
  '#[0-9a-fA-F]{3}([0-9a-fA-F]{3})?\b' \
  apps/ packages/ design-tokens/ 2>/dev/null \
  | grep -v '/tokens.json:' \
  | grep -v '/tailwind-preset.ts:' \
  | grep -v '/theme.css:' \
  | grep -v '/preview-skin.css:' \
  | grep -vE '\.test\.(ts|tsx|py):' \
  | grep -vE '/tests/' \
  || true)
if [[ -z "$hits" ]]; then pass; else
  fail "Hex colors must come from tokens.json (use a Tailwind class or import \`color\` from @internal/design-tokens):\n$hits"
fi

# ------------------------------------------------------------------
# 5. No alert() / confirm() in frontend.
# ------------------------------------------------------------------
step 5 "alert()/confirm() absent in frontend"
hits=$(grep -rnE "${exclude_args[@]}" --include='*.ts' --include='*.tsx' \
  '(^|[^A-Za-z_.])(alert|confirm)\(' apps/*/frontend/src 2>/dev/null || true)
if [[ -z "$hits" ]]; then pass; else
  fail "Use Dialog/Toast from @internal/ui instead of native alert/confirm:\n$hits"
fi

# ------------------------------------------------------------------
# 6. No debug=True in backend.
# ------------------------------------------------------------------
step 6 "debug=True absent in backend"
hits=$(grep -rEn "${exclude_args[@]}" --include='*.py' \
  'debug[[:space:]]*=[[:space:]]*True' apps/*/backend/app 2>/dev/null || true)
if [[ -z "$hits" ]]; then pass; else
  fail "debug=True forbidden in apps/*/backend/app (security — STANDARD §2.5):\n$hits"
fi

# ------------------------------------------------------------------
# 7. Every _run.bat declares a PORT variable, checks it, and falls
#    back to a free port automatically (STANDARD_POC.md §9, rule #12).
# ------------------------------------------------------------------
step 7 "_run.bat: PORT + bascule auto"
missing=""
for runbat in apps/*/_run.bat; do
  [[ -f "$runbat" ]] || continue
  if ! grep -q 'set "PORT=' "$runbat"; then
    missing+="$runbat — manque la variable 'set \"PORT=80XX\"'\n"
  elif ! grep -q 'findstr "LISTENING"' "$runbat"; then
    missing+="$runbat — manque le check de port (netstat ... findstr \"LISTENING\")\n"
  elif ! grep -q ':find_port' "$runbat"; then
    missing+="$runbat — manque la bascule auto sur port libre (boucle :find_port)\n"
  fi
done
if [[ -z "$missing" ]]; then pass; else
  fail "Chaque apps/*/_run.bat doit declarer 'set \"PORT=80XX\"', verifier le port et basculer auto si occupe (STANDARD §9):\n$missing"
fi

# ------------------------------------------------------------------
# 8. Aucun pyproject.toml d'app ne porte encore le nom TEMPLATE-backend
#    (instanciation oubliee depuis apps/_template/).
# ------------------------------------------------------------------
step 8 "pyproject.toml renomme"
hits=""
for f in apps/*/backend/pyproject.toml; do
  [[ -f "$f" ]] || continue
  [[ "$f" == "apps/_template/backend/pyproject.toml" ]] && continue
  if grep -q '^name = "TEMPLATE-backend"' "$f"; then
    hits+="$f\n"
  fi
done
if [[ -z "$hits" ]]; then pass; else
  fail "Le 'name' de pyproject.toml doit etre <slug>-backend (instanciation incomplete) :\n$hits"
fi

# ------------------------------------------------------------------
# 9. Aucun README d'app n'est encore celui du _template
#    (contient la phrase 'Squelette canonique').
# ------------------------------------------------------------------
step 9 "README d'app reecrit"
hits=""
for f in apps/*/README.md; do
  [[ -f "$f" ]] || continue
  [[ "$f" == "apps/_template/README.md" ]] && continue
  if grep -q 'Squelette canonique' "$f"; then
    hits+="$f\n"
  fi
done
if [[ -z "$hits" ]]; then pass; else
  fail "Le README de l'app contient encore le texte du template ('Squelette canonique') :\n$hits"
fi

# ------------------------------------------------------------------
# 10. config.py / alembic.ini ne referencent plus 'TEMPLATE.db'.
# ------------------------------------------------------------------
step 10 "DB renommee (pas TEMPLATE.db)"
hits=""
for f in apps/*/backend/app/config.py apps/*/backend/alembic.ini; do
  [[ -f "$f" ]] || continue
  case "$f" in
    apps/_template/*) continue ;;
  esac
  if grep -q 'TEMPLATE\.db' "$f"; then
    hits+="$f\n"
  fi
done
if [[ -z "$hits" ]]; then pass; else
  fail "config.py / alembic.ini doivent pointer sur <slug>.db, pas TEMPLATE.db :\n$hits"
fi

# ------------------------------------------------------------------
# 11. Section '## Auth' presente dans chaque apps/<poc>/README.md
#    (palier 1 declare explicitement, cf. STANDARD §3.5).
# ------------------------------------------------------------------
step 11 "Section Auth presente"
missing=""
for f in apps/*/README.md; do
  [[ -f "$f" ]] || continue
  if ! grep -q '^## Auth' "$f"; then
    missing+="$f\n"
  fi
done
if [[ -z "$missing" ]]; then pass; else
  fail "Section '## Auth' obligatoire dans chaque apps/<poc>/README.md (STANDARD §3.5) :\n$missing"
fi

# ------------------------------------------------------------------
# 12. Le package.json racine declare 'dev:<poc>' pour chaque dossier
#    sous apps/ (sauf _template).
# ------------------------------------------------------------------
step 12 "package.json racine wire"
missing=""
if [[ -f package.json ]]; then
  for d in apps/*/; do
    poc="$(basename "$d")"
    [[ "$poc" == "_template" ]] && continue
    if ! grep -q "\"dev:${poc}\"" package.json; then
      missing+="apps/$poc/ -- manque 'dev:${poc}' dans package.json racine\n"
    fi
  done
fi
if [[ -z "$missing" ]]; then pass; else
  fail "Chaque POC doit avoir un script 'dev:<poc>' au niveau racine :\n$missing"
fi

# ------------------------------------------------------------------
# 13. Aucun --host 0.0.0.0 dans les lanceurs (palier 1 strict).
# ------------------------------------------------------------------
step 13 "Bind 127.0.0.1 dans lanceurs"
hits=$(grep -rnE "${exclude_args[@]}" --include='*.bat' --include='*.sh' \
  'host[[:space:]=]+0\.0\.0\.0|--host[[:space:]]+0\.0\.0\.0' apps/ 2>/dev/null || true)
if [[ -z "$hits" ]]; then pass; else
  fail "Bind 0.0.0.0 interdit (palier 1 - STANDARD §3.5) :\n$hits"
fi

# ------------------------------------------------------------------
# 14. Interrupteur LLM : chaque app expose la cle llm_enabled
#     (helper get_llm_enabled + champ settings), cf. STANDARD §3.7 / §6.
# ------------------------------------------------------------------
step 14 "Interrupteur LLM (llm_enabled)"
missing=""
for d in apps/*/backend/app; do
  [[ -d "$d" ]] || continue
  if ! grep -rq 'llm_enabled' "$d" 2>/dev/null; then
    poc="$(basename "$(dirname "$(dirname "$d")")")"
    missing+="apps/$poc — manque l'interrupteur LLM 'llm_enabled' (get_llm_enabled + champ /settings)\n"
  fi
done
if [[ -z "$missing" ]]; then pass; else
  fail "Chaque app doit exposer l'interrupteur LLM 'llm_enabled' (STANDARD §3.7 / §6) :\n$missing"
fi

# ------------------------------------------------------------------
# 15. Summary
# ------------------------------------------------------------------
step 15 "Summary"
if [[ $violations -gt 0 ]]; then
  printf " \033[31m%d violation(s)\033[0m\n" "$violations"
  exit 1
fi
pass
exit 0
