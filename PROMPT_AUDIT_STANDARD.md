# PROMPT_AUDIT_STANDARD.md — audit d'un POC contre le standard

Prompt déclenché manuellement. Usage : « lis `PROMPT_AUDIT_STANDARD.md` et applique-le sur `apps/<poc>` ».

## Mission

Tu vas auditer l'app `apps/<poc>` indiquée par l'utilisateur contre les règles de [`STANDARD_POC.md`](./STANDARD_POC.md). Tu produis un rapport d'écarts au format imposé ci-dessous. Tu **proposes** les correctifs mais tu ne **les appliques pas** sans validation explicite de l'utilisateur.

## Avant de commencer

1. Vérifie que `STANDARD_POC.md` existe à la racine du repo. S'il est absent, arrête et demande où il se trouve.
2. Lis intégralement `STANDARD_POC.md`. C'est la seule référence de vérité.
3. Vérifie que l'app cible existe : `ls apps/<poc>/`. Si le chemin est ambigu, demande confirmation à l'utilisateur.
4. Explore systématiquement (sans rien inventer) :
   - `apps/<poc>/README.md` (niveau app — section Auth, section Écarts au standard)
   - `apps/<poc>/start.bat`, `apps/<poc>/start.sh`
   - `apps/<poc>/backend/app/main.py`, `config.py`, `schemas.py`
   - Au moins un fichier de `apps/<poc>/backend/app/api/`
   - `apps/<poc>/backend/pyproject.toml`
   - `apps/<poc>/backend/alembic.ini` et `alembic/env.py`
   - `apps/<poc>/backend/.env.example`
   - `apps/<poc>/backend/README.md` (s'il existe)
   - `apps/<poc>/backend/app/api/preview.py` et `apps/<poc>/backend/app/templates/preview.html` (s'ils existent — mode no-Node)
   - `apps/<poc>/frontend/src/main.tsx`, `App.tsx`, `i18n.ts`, `index.html`
   - `apps/<poc>/frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `tailwind.config.ts`

## Checklist exhaustive

Une case par règle de `STANDARD_POC.md`. Pour chaque ligne, statut + fichier:ligne + action.

### Structure de l'app

- [ ] `apps/<poc>/README.md` présent (niveau app)
- [ ] `apps/<poc>/start.bat` présent
- [ ] `apps/<poc>/start.sh` présent
- [ ] `apps/<poc>/backend/` et `apps/<poc>/frontend/` présents
- [ ] `apps/<poc>/backend/data/` présent (gitignoré)
- [ ] `apps/<poc>/backend/.env.example` présent et à jour
- [ ] Aucun `Dockerfile` ni `docker-compose.yml` (Docker hors standard)

### Stack backend

- [ ] FastAPI ≥ 0.115 dans `pyproject.toml`
- [ ] Pydantic v2 dans `pyproject.toml`
- [ ] SQLAlchemy 2.0 dans `pyproject.toml`
- [ ] pydantic-settings ≥ 2.0 dans `pyproject.toml`
- [ ] Alembic ≥ 1.13 + au moins une migration dans `alembic/versions/`
- [ ] httpx ≥ 0.28 + sse-starlette pour les appels LLM
- [ ] structlog pour les logs
- [ ] Aucune trace de Flask, Streamlit, SDK Mistral (`mistralai`), LangChain (`langchain*`) dans les dépendances

### Organisation backend

- [ ] `app/main.py` avec `create_app()` et middlewares (CORS, request_id, errors)
- [ ] `app/config.py` avec pydantic-settings et validation des env vars au boot
- [ ] `app/schemas.py` avec modèles Pydantic I/O
- [ ] `app/api/health.py` présent
- [ ] Une ressource = un fichier dans `app/api/`, pas de `routes.py` monolithique
- [ ] `app/parsers/` et `app/checks/` modulaires (1 fichier par format / contrôle)
- [ ] `app/db/` avec session, Base, modèles SQLAlchemy
- [ ] `app/static/` et `app/templates/` tolérés (uniquement pour servir le bundle Vite ou une page preview)

### Conventions API

- [ ] Toutes les routes préfixées `/api/v1/`
- [ ] `GET /api/v1/health` retourne `{status, version, db, llm}`
- [ ] Format d'erreur unifié `{code, message, detail, request_id}` partout
- [ ] IDs ressources en UUID v4 (pas d'auto-incrément exposé)
- [ ] Pagination `?limit=N&cursor=…` sur les endpoints list (si > 100 items attendus)
- [ ] Streaming SSE pour chat et générations > 5s
- [ ] Chaque body endpoint = modèle Pydantic, jamais `request.json()` brut

### Persistance

- [ ] SQLite par défaut dans `apps/<poc>/backend/data/<poc>.db`
- [ ] `data/` gitignoré
- [ ] Variable `DATABASE_URL` unique lue par `app/config.py`
- [ ] PRAGMA `journal_mode=WAL` activé
- [ ] Alembic migrations testées compatibles SQLite ET Postgres
- [ ] UUID stockés en `String(36)` (compatible bascule Postgres)
- [ ] Pas de types SQLite-spécifiques
- [ ] Fichiers uploadés stockés sous `data/storage/{project_uuid}/{file_version_uuid}_{name}` avec SHA-256

### Sécurité — Auth (palier 1 strict)

- [ ] Section `## Auth` présente dans `apps/<poc>/README.md` avec ligne `**Palier** : 1 — local seul, bind 127.0.0.1, pas d'authentification.`
- [ ] Aucun `--host 0.0.0.0` dans `start.bat`, `start.sh`, ou les invocations uvicorn
- [ ] CORS liste blanche explicite, pas `["*"]`
- [ ] Clé API LLM côté serveur uniquement, jamais saisie dans l'UI
- [ ] `.env` gitignoré, `.env.example` à jour avec valeurs factices

### Observabilité

- [ ] structlog JSON configuré, niveau via env var
- [ ] `RequestIdMiddleware` présent, header `X-Request-Id` propagé
- [ ] `request_id` propagé via `contextvars` dans les logs
- [ ] Aucun `print()` dans le code committé
- [ ] Aucun `console.log` dans le code committé
- [ ] Aucun `debug=True` dans le code committé

### Stack frontend

- [ ] React 18 dans `package.json`
- [ ] TypeScript strict (hérité de `tsconfig.base.json` racine)
- [ ] Vite comme bundler
- [ ] Tailwind via preset partagé `@internal/design-tokens/tailwind-preset`
- [ ] `@internal/ui` en dépendance workspace
- [ ] `@internal/design-tokens` en dépendance workspace
- [ ] lucide-react, recharts, react-router-dom v6, zustand, @tanstack/react-query
- [ ] react-hook-form + zod (toujours présents)
- [ ] i18next + react-i18next + i18next-browser-languagedetector
- [ ] Vitest + Playwright configurés
- [ ] Aucune trace de Babel runtime, scripts CDN (unpkg, cdn.tailwindcss.com)
- [ ] Aucune trace de MUI / Ant Design / Chakra / autre lib UI concurrente

### Organisation frontend

- [ ] `src/main.tsx` avec providers globaux (StrictMode, QueryClientProvider, BrowserRouter)
- [ ] `src/App.tsx` avec layout + ErrorBoundary global + topbar contenant `ThemeToggle`
- [ ] `src/i18n.ts` qui initialise i18next avec FR + EN
- [ ] `src/routes/` avec un fichier par page
- [ ] Pas de dossier `src/components/ui/` dans l'app
- [ ] `src/components/business/` pour les composants métier
- [ ] `src/components/charts/` consommant `tokens.json`
- [ ] `src/locales/{fr,en}.json` présents
- [ ] `src/stores/` Zustand pour l'état UI global

### Design system

- [ ] Aucun hex en dur dans le code (sauf `tokens.json`, `tailwind-preset.ts`, `theme.css`)
- [ ] Tailwind preset partagé importé dans `tailwind.config.ts`
- [ ] Composants `@internal/ui` utilisés partout, pas de réinvention
- [ ] `tokens.json` : couleurs flat sous `color.*` (dark) + overrides light sous `themes.light.color.*`
- [ ] `theme.css` présent à `design-tokens/theme.css`, pattern `:root` (light) + `.dark` (override), importé par `apps/<poc>/frontend/src/index.css`
- [ ] **Mode Vite** : `ThemeToggle` (depuis `@internal/ui`) présent dans `App.tsx` (topbar)
- [ ] **Mode Vite** : snippet anti-flash dans `frontend/index.html` qui applique `.dark` sur `<html>` avant rendu React
- [ ] **Mode Vite** : `meta color-scheme="dark light"` dans `frontend/index.html` (jamais `"dark"` seul)
- [ ] **Mode preview HTML** (si `app/templates/preview.html` existe) : `_build_css_vars()` émet `:root` (light) + `.dark` (dark override), avec liste de tokens identique à celle des autres POCs (uniformité visuelle inter-apps)
- [ ] **Mode preview HTML** : snippet anti-flash dans `<head>` de `preview.html` (avant `<link>`)
- [ ] **Mode preview HTML** : `meta color-scheme="dark light"`, pas de `class="dark"` hardcodé sur `<html>`
- [ ] **Mode preview HTML** : bouton SVG Sun/Moon + JS toggle inline présents (cherche `data-theme-toggle`)
- [ ] Persistance `localStorage['theme']` câblée dans les deux modes
- [ ] Aucune trace de `alert()` ou `confirm()`
- [ ] Aucune icône Unicode/emoji dans le JSX

### LLM

- [ ] Mistral API via httpx async
- [ ] sse-starlette pour le streaming SSE
- [ ] Aucune trace de SDK Mistral (`mistralai`)
- [ ] Aucune trace de LangChain (LangGraph standalone toléré)
- [ ] Table `llm_invocation_audit` présente dans le schéma DB (si appels LLM)
- [ ] Audit row écrit pour 100% des appels LLM
- [ ] Clé `AppConfig` `llm_enabled` gérée (helpers `get_llm_enabled`/`set_llm_enabled`, défaut `true`)
- [ ] Garde-fou `get_llm_enabled(db)` avant chaque `MistralClient.from_db(db)` des routes métier
- [ ] OFF = fallback gracieux (HTTP 200 + résultat déterministe/vide, jamais 5xx ; clé conservée)
- [ ] `GET/POST /api/v1/settings` expose/accepte `llm_enabled` ; `/health` reporte `llm:"disabled"` quand OFF
- [ ] UI : badge d'état LLM (sidebar+home) + `.switch` dans l'onglet Paramètres

### i18n

- [ ] i18next câblé dès le boot via `src/i18n.ts`
- [ ] FR + EN minimum dans `src/locales/`
- [ ] Clés sémantiques (ex. `diagnostic.title`), pas la chaîne FR comme clé
- [ ] Fallback `fr → en → clé brute` configuré

### Tests

- [ ] 1 pytest par route backend minimum
- [ ] 1 Vitest par composant atomique de `@internal/ui` (au niveau de `packages/ui/`, pas de l'app)
- [ ] 1 Playwright smoke par parcours critique dans `apps/<poc>/frontend/tests/e2e/`
- [ ] `scripts/check_standard.sh` retourne exit 0

## Format de sortie attendu

Produis un fichier `apps/<poc>/AUDIT_STANDARD.md` (à la racine de l'app auditée) avec **exactement** cette structure :

```markdown
# Audit standard — <nom du POC>

Date : YYYY-MM-DD
Standard de référence : STANDARD_POC.md (commit <hash court si dispo>)
Verdict global : CONFORME | PARTIEL | NON CONFORME
Palier d'auth déclaré : 1 — local seul (toujours, sinon hors scope POC)

## Résumé

| Domaine | Conforme | Partiel | Non conforme | Non applicable |
|---|---|---|---|---|
| Structure de l'app | X | Y | Z | — |
| Stack backend | … | … | … | — |
| Organisation backend | … | … | … | — |
| Conventions API | … | … | … | — |
| Persistance | … | … | … | — |
| Sécurité — Auth | … | … | … | — |
| Observabilité | … | … | … | — |
| Stack frontend | … | … | … | — |
| Organisation frontend | … | … | … | — |
| Design system | … | … | … | — |
| LLM | … | … | … | — |
| i18n | … | … | … | — |
| Tests | … | … | … | — |

## Détail des écarts

| Règle | Statut | Fichier:ligne | Action recommandée |
|---|---|---|---|
| FastAPI ≥ 0.115 | ✅ | backend/pyproject.toml:10 | — |
| Aucun hex en dur | ❌ | frontend/src/components/Header.tsx:24 | Remplacer `#0e1117` par `bg-bg` (token) |
| `print()` interdit | ⚠️ | backend/app/api/projects.py:67 | Remplacer par `logger.info(...)` structlog |
| Bind 127.0.0.1 | ✅ | start.sh:12 | — |
| Tokens dual-theme | ❌ | design-tokens/tokens.json | Ajouter les overrides light sous `themes.light.color.*` (cf. STANDARD §5.1) |
| `ThemeToggle` dans topbar | ❌ | frontend/src/App.tsx | Ajouter `<ThemeToggle />` dans la topbar |
| … | … | … | … |

Légende : ✅ conforme · ⚠️ partiel · ❌ non conforme · ➖ non applicable

## Plan de mise en conformité

Liste ordonnée par criticité décroissante :

1. **<chantier critique>** — effort estimé (XS/S/M/L), fichiers concernés
2. **<chantier majeur>** — …
3. …

Critères de criticité :
- **Critique** : sécurité (clé API exposée, bind 0.0.0.0, secret committé), blocage UX (`alert()` bloquant), ou plantage prévisible.
- **Majeure** : écart à l'identité commune (hex en dur, composant maison qui double `@internal/ui`, ThemeToggle absent, dual-theme cassé).
- **Mineure** : organisation (nom de dossier, log isolé, item de checklist non bloquant).

## Écarts documentés

Liste les écarts qui sont déjà documentés dans `apps/<poc>/README.md` section « Écarts au standard » avec leur justification. Ne les compte pas comme des violations.

| Règle | Justification documentée | Validation |
|---|---|---|
| … | … | … |

## Points hors-standard à clarifier

Choses présentes dans le projet qui ne sont ni explicitement conformes ni explicitement bannies par le standard. À discuter avec le mainteneur du standard.

- …
```

## Règles de jugement

- Cite **systématiquement** les fichiers et numéros de ligne réels (`backend/app/main.py:42`).
- Ne propose **aucune solution hors standard**. Si le projet utilise une lib bannie, écris « migration vers <lib conforme> » et cite la section de `STANDARD_POC.md`. Ne propose pas de garder la lib bannie « pour aller vite ».
- Ne juge pas les écarts qui sont **documentés** dans la section « Écarts au standard » du README de l'app (avec justification écrite). Liste-les séparément.
- Ne fabrique aucun fichier ou numéro de ligne. Si tu n'as pas pu vérifier un point (fichier absent, lecture incomplète), marque-le « à auditer » plutôt que de deviner.
- Ton final factuel, pas accusateur. Le but est un plan d'action, pas un blâme.

## Après le rapport

Une fois `AUDIT_STANDARD.md` produit, **arrête-toi**. N'applique aucun correctif. Demande à l'utilisateur :

> Le rapport d'audit est dans `apps/<poc>/AUDIT_STANDARD.md`. Veux-tu que j'applique les correctifs un par un, dans l'ordre du plan de mise en conformité ?
