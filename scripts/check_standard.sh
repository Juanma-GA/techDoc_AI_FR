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

EXCLUDE_DIRS=(node_modules .venv __pycache__ dist build generated target gen .git playwright-report test-results coverage legacy)
exclude_args=()
for d in "${EXCLUDE_DIRS[@]}"; do
  exclude_args+=(--exclude-dir="$d")
done

step()  { printf "[%d/18] %-38s" "$1" "$2"; }
pass()  { printf " \033[32mok\033[0m\n"; }
fail()  { printf " \033[31mFAIL\033[0m\n"; violations=$((violations + 1)); printf '%b\n' "$1" | sed 's/^/    /'; }

# ------------------------------------------------------------------
# 1. Check the API prefix using the declared backend's source layout.
# ------------------------------------------------------------------
step 1 "Backend API prefix /api/v1"
missing=""
for backend in apps/*/backend; do
  [[ -d "$backend" ]] || continue
  if [[ -f "$backend/go.mod" ]]; then
    grep -rq --include='*.go' 'Group("/api/v1")' "$backend/cmd" ||
      missing+="$backend -- Go API group /api/v1 missing\n"
  elif [[ -f "$backend/pyproject.toml" ]]; then
    grep -q 'prefix="/api/v1"' "$backend/app/main.py" ||
      missing+="$backend -- FastAPI prefix /api/v1 missing\n"
  else
    missing+="$backend -- backend stack needs an explicit checker adapter\n"
  fi
done
if [[ -z "$missing" ]]; then pass; else fail "$missing"; fi

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
  elif ! grep -Eq 'findstr(\.exe)?["]?[[:space:]]+"LISTENING"' "$runbat"; then
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
# 12. Le package.json racine declare 'dev:<poc>' pour chaque app
#    avec un dossier backend ou frontend (sauf _template).
# ------------------------------------------------------------------
step 12 "package.json racine wire"
missing=""
if [[ -f package.json ]]; then
  for d in apps/*/; do
    poc="$(basename "$d")"
    [[ "$poc" == "_template" ]] && continue
    [[ -d "${d}backend" || -d "${d}frontend" ]] || continue
    if ! grep -q "\"dev:${poc}\"" package.json; then
      missing+="apps/$poc/ -- manque 'dev:${poc}' dans package.json racine\n"
    fi
  done
fi
if [[ -z "$missing" ]]; then pass; else
  fail "Chaque app avec backend ou frontend doit avoir un script 'dev:<poc>' au niveau racine :\n$missing"
fi

# ------------------------------------------------------------------
# 13. Aucun --host 0.0.0.0 dans les lanceurs (palier 1 strict).
# ------------------------------------------------------------------
step 13 "Bind 127.0.0.1 dans lanceurs"
hits=$(grep -rnE "${exclude_args[@]}" --include='*.bat' --include='*.sh' \
  --exclude-dir='deploy' \
  'host[[:space:]=]+0\.0\.0\.0|--host[[:space:]]+0\.0\.0\.0' apps/ 2>/dev/null || true)
if [[ -z "$hits" ]]; then pass; else
  fail "Bind 0.0.0.0 interdit (palier 1 - STANDARD §3.5) :\n$hits"
fi

# ------------------------------------------------------------------
# 14. Interrupteur LLM : seules les apps declarant le profil `llm`
#     dans README exposent llm_enabled, cf. STANDARD §3.7 / §6.
# ------------------------------------------------------------------
step 14 "Interrupteur LLM pour profil llm"
missing=""
for d in apps/*/backend/app; do
  [[ -d "$d" ]] || continue
  poc="$(basename "$(dirname "$(dirname "$d")")")"
  readme="apps/$poc/README.md"
  [[ -f "$readme" ]] || continue
  if ! awk '
    /^## Profiles[[:space:]]*$/ { in_profiles=1; next }
    /^## / { in_profiles=0 }
    in_profiles && /^[[:space:]]*-[[:space:]]*`llm`[[:space:]]*$/ { found=1 }
    END { exit !found }
  ' "$readme"; then
    continue
  fi
  if ! grep -rq 'llm_enabled' "$d" 2>/dev/null; then
    missing+="apps/$poc — profil llm declare mais interrupteur 'llm_enabled' absent (get_llm_enabled + champ /settings)\n"
  fi
done
if [[ -z "$missing" ]]; then pass; else
  fail "Chaque app declarant le profil 'llm' doit exposer l'interrupteur 'llm_enabled' (STANDARD §3.7 / §6) :\n$missing"
fi

# ------------------------------------------------------------------
# 15. pnpm install garde par node_modules dans les lanceurs (rule #12).
#     En reseau a TLS intercepte, un 'pnpm install' non garde retente
#     chaque paquet "in 1 minute" et fige le lancement plusieurs minutes.
# ------------------------------------------------------------------
step 15 "pnpm install garde par node_modules"
missing=""
for runbat in apps/*/_run.bat; do
  [[ -f "$runbat" ]] || continue
  # Ne verifie que les .bat qui appellent effectivement pnpm install.
  if grep -q 'pnpm install' "$runbat" && ! grep -q 'if not exist node_modules call pnpm install' "$runbat"; then
    missing+="$runbat — 'call pnpm install' doit etre garde par 'if not exist node_modules'\n"
  fi
done
for sh in apps/*/start.sh; do
  [[ -f "$sh" ]] || continue
  if grep -q 'pnpm install' "$sh" && ! grep -q 'node_modules \] || pnpm install' "$sh"; then
    missing+="$sh — 'pnpm install' doit etre garde par '[ -d node_modules ] ||'\n"
  fi
done
if [[ -z "$missing" ]]; then pass; else
  fail "Lanceurs : 'pnpm install' interdit sur le chemin critique, garder par node_modules absent (STANDARD §lanceurs, rule #12) :\n$missing"
fi

# ------------------------------------------------------------------
# 16. Registry, profiles, ports and shared UI stay synchronized.
# ------------------------------------------------------------------
step 16 "App registry, profils, ports et UI partagee"
NODE_BIN="$(command -v node || command -v node.exe || true)"
if [[ -z "$NODE_BIN" ]]; then
  fail "Node.js 20+ doit etre sur le PATH du shell courant pour valider le registre et les surfaces synchronisees."
elif ! "$NODE_BIN" -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 20 ? 0 : 1)' >/dev/null 2>&1; then
  fail "Node.js 20+ est requis pour valider le registre et les surfaces synchronisees."
elif "$NODE_BIN" scripts/sync_app_registry.mjs --check > /dev/null; then pass; else
  fail "Le registre, les README, les ports, les commandes racine et le shell @internal/ui doivent rester synchronises."
fi

# ------------------------------------------------------------------
# 17. Every frontend defaults to dark, honoring an explicit saved light theme.
# ------------------------------------------------------------------
step 17 "Theme sombre par defaut"
missing=""
if [[ -n "$NODE_BIN" ]]; then
  while IFS= read -r app_slug; do
    theme_html="apps/$app_slug/frontend/index.html"
    [[ -f "$theme_html" ]] || continue
    if ! grep -Fq 'var stored = localStorage.getItem("theme");' "$theme_html" ||
      ! grep -Fq 'if (stored !== "light") {' "$theme_html" ||
      ! grep -Fq 'document.documentElement.classList.add("dark");' "$theme_html" ||
      grep -q 'prefers-color-scheme' "$theme_html"; then
      missing+="$theme_html — doit demarrer en sombre sauf preference light explicite\n"
    fi
  done < <("$NODE_BIN" -e 'const registry = JSON.parse(require("node:fs").readFileSync("scripts/apps.json", "utf8")); for (const app of registry.apps) console.log(app.slug);')
fi
if [[ -z "$missing" ]]; then pass; else
  fail "Chaque frontend doit appliquer le mode sombre par defaut dans son anti-flash :\n$missing"
fi

# ------------------------------------------------------------------
# 18. Summary
# ------------------------------------------------------------------
step 18 "Summary"
if [[ $violations -gt 0 ]]; then
  printf " \033[31m%d violation(s)\033[0m\n" "$violations"
  exit 1
fi
pass
exit 0
