# CLAUDE.md — règles du monorepo

Ce fichier est lu automatiquement par Claude Code à l'ouverture du repo. Il fixe le cadre non-négociable. Pour le détail technique, voir [`STANDARD_POC.md`](./STANDARD_POC.md).

## Contexte

Monorepo pnpm hébergeant des POCs FastAPI + React **développés dans un tronc commun** et lancés **localement** sur le PC du dev. Posture **local-first stricte** : pas de Docker, pas de CI, pas de déploiement dans le périmètre du standard. Chaque POC est démarrable via `apps/<poc>/start.bat` (Windows) ou `start.sh` (Unix), et packagé via `apps/<poc>/package.bat`.

```
internal-poc-monorepo/
├── apps/<poc>/              # 1 POC = 1 app full-stack lancée localement
├── apps/_template/          # squelette pour démarrer un nouveau POC
├── packages/ui/             # @internal/ui (composants partagés)
├── design-tokens/           # tokens.json (dual-theme dark/light) + tailwind-preset
├── scripts/                 # check_standard.sh
└── docs/adr/
```

## 14 règles non-négociables

1. **Stack imposée**. Backend = FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog. Frontend = React 18 + TS strict + Vite + Tailwind + React Hook Form + Zod + i18next + Zustand + TanStack Query. Tout autre choix = écart à justifier dans le README de l'app.
2. **Bannis absolus**. Flask, Streamlit, Babel/React/Tailwind via CDN, LangChain, SDK Mistral, MUI/AntD, Docker, `alert()`, `confirm()`, icônes Unicode, `ignoreBuildErrors: true`, hex en dur dans le code, `console.log`/`print()`/`debug=True` committés.
3. **Composants UI uniquement via `@internal/ui`**. Pas de réinvention dans `apps/<poc>/components/`. Toute primitive nouvelle se crée dans `packages/ui/` puis se consomme.
4. **Tokens design uniques, dual-theme**. Couleurs, typo, dimensions viennent de `design-tokens/tokens.json` (palette dark à plat sous `color.*`, overrides light sous `themes.light.color.*`) via le preset Tailwind partagé qui consomme `theme.css`. Aucun hex écrit en dur. Tout POC supporte le toggle dark/light via `ThemeToggle`.
5. **API REST**. Préfixe `/api/v1/` obligatoire, IDs UUID v4, format d'erreur unifié `{code, message, detail, request_id}`, validation Pydantic systématique (jamais `request.json()` brut).
6. **LLM**. Mistral API + `httpx` async + SSE (`sse-starlette`). Pas de SDK Mistral. Pas de LangChain.
7. **Persistance**. SQLite par défaut dans `apps/<poc>/backend/data/<poc>.db` (gitignoré). Alembic dès J1, migrations compatibles SQLite ET Postgres.
8. **Auth = local seul (palier 1)**. Pas d'auth, bind `127.0.0.1` obligatoire, jamais `0.0.0.0`. Tout POC le déclare en haut de son README. Le déploiement (palier 2/3) sort du périmètre POC.
9. **Logs**. `structlog` JSON + `RequestIdMiddleware` + header `X-Request-Id` propagé bout en bout. ErrorBoundary obligatoire au niveau App côté front.
10. **i18n**. `i18next` câblé dès J1 avec FR + EN minimum. Clés sémantiques (`diagnostic.title`), jamais la chaîne FR comme clé.
11. **Tests**. 1 pytest par route backend, 1 Vitest par composant atomique de `@internal/ui`, 1 Playwright smoke par parcours critique. `scripts/check_standard.sh` doit rester vert avant tout commit.
12. **Launcher + packager obligatoires**. Tout POC fournit quatre `.bat` + un `start.sh` :
    - **`start.bat`** : wrapper court (3 lignes) qui fait `start "<poc>" cmd /k "%~dp0_run.bat"`. Toute la logique vit dans `_run.bat`. Le `cmd /k` garantit que la fenêtre **reste ouverte** sur erreur (sinon impossible de lire le message).
    - **`_run.bat`** : logique de lancement (détection Python, venv, deps, Alembic, uvicorn). Variable `set "PORT=80XX"` en tête, unique par POC. Check `netstat | findstr ":%PORT%" | findstr "LISTENING"` avant `uvicorn` ; sortie explicite si occupé.
    - **`package.bat`** + **`_package.bat`** (même pattern wrapper) qui appellent `scripts/package_<poc>.py` pour produire un ZIP autonome (Python embed + frontend dist + design-tokens).
    - **`start.sh`** : équivalent Unix, variable `PORT` configurable, `lsof -iTCP:$PORT -sTCP:LISTEN` avant `uvicorn`.
    - **ASCII pur obligatoire** dans tous les `.bat` (pas d'accents : `échec`→`echec`, `fenêtre`→`fenetre`). Sinon `cmd.exe` ferme la fenêtre silencieusement à la lecture du fichier.
    - **Pas de parenthèses dans `echo` à l'intérieur d'un block `if (...)` du bat** : cmd interprète le `)` comme fin de block et crash silencieusement avec « X était inattendu ». Reformuler `echo Installation (1 a 3 min)` en `echo Installation 1 a 3 min` ou échapper avec `^(` `^)`.
13. **Preview HTML autonome (sans Node)**. Tout POC fournit un fallback HTML servi à `/` quand `frontend/dist/` n'existe pas :
    - **`backend/app/templates/preview.html`** — UI vanilla JS, ASCII pur dans les strings inline (les accents passent par l'i18n FR injecté à la volée).
    - **`backend/app/api/preview.py`** — renderer qui injecte les CSS variables depuis `design-tokens/tokens.json` et le dict i18n FR depuis `frontend/src/locales/fr.json`.
    - **`main.py`** mount `_mount_preview()` quand `frontend/dist/` est absent ; `_mount_vite_dist()` sinon. API `/api/v1/*` enregistrées AVANT pour prendre la priorité.
    - **Onglets minimum** : Home / Architecture / Données / Paramètres. Le POC ajoute ses onglets métier.
    - **Standard visuel** : fonts Google `Inter` (sans-serif) / `JetBrains Mono` (label, code) / `Orbitron` (brand, titres). Classes CSS : `.btn[.primary|.secondary|.ghost|.danger|.small]`, `.card` + `.card-title`, `.kpi-grid` + `.kpi` + `.kpi-value[.info|.ok|.warn|.err]`, `.arch-flow` + `.arch-step`, `.empty-state`, `.banner[.warn]`, `.badge[.ok|.warn|.danger|.info]`.
    - **Theme toggle** : sun/moon SVG dans le sidebar-header. Class `.dark` sur `<html>`, persistée en `localStorage["theme"]`. Script anti-flash en `<head>` (lit le localStorage avant le render React/HTML).
    - **i18n** : attribut `data-i18n="key"` sur les éléments statiques + fonction `t(key)` pour les strings injectées par les render functions. Dictionnaires FR + EN inline dans le `<script>`. Boutons `.lang-btn` (FR/EN) déclenchent `setLang()` qui met à jour `LANG`, persiste en `localStorage["<poc>-lang"]` et re-render la page active.
    - **Confirmation actions destructrices** : pattern double-clic (1er clic arme le bouton avec label « Cliquer encore pour confirmer », 2e clic dans les 3 secondes exécute). Jamais `alert()` ni `confirm()` (règle #2).
14. **Endpoints standards**. Au-delà de `/api/v1/health`, tout POC expose :
    - `GET /api/v1/admin/stats` + `POST /api/v1/admin/reset/all` (et `/reset/<scope>` par scope métier) — consommés par l'onglet Données du preview.
    - `GET /api/v1/settings` + `POST /api/v1/settings` + `POST /api/v1/settings/test` — config Mistral runtime, persistée dans la table `AppConfig` (key/value). La clé Mistral n'est jamais committée.
    - SSE streaming (quand applicable, ex. chat / génération) : events `session` (init avec `{session_id, title}`) → `token*` (deltas successifs) → `done` (succès) ou `error` (avec `{message}`). Endpoint **POST** uniquement (l'`EventSource` natif refuse POST → côté client utiliser `fetch + ReadableStream`).
    - **`AppConfig`** (table `app_config`, key:str PK / value:text) est obligatoire dans tout POC. Sert à stocker la clé Mistral et toute config runtime. Préservée par convention lors d'un reset admin. Migration `0001_initial.py` créée par défaut dans le `_template`.

## Règles de méthode

- **Avant tout changement structurant** (ajout de dépendance, nouveau dossier, refacto multi-fichiers, modification de `packages/ui/` ou `design-tokens/`) : annonce le plan en 5 lignes max et attends validation.
- **Fichier > 200 lignes** : signale-le et propose un découpage avant de continuer à l'étendre.
- **Code legacy** (dossier `legacy/` ou marqué tel quel) : lecture seule. Ne le modifie pas, sauf demande explicite.
- **`scripts/check_standard.sh`** : doit retourner exit 0 avant chaque commit. Si rouge, corrige les violations avant de proposer le commit.
- **Chaque POC est indépendant**. N'introduis jamais de dépendance runtime entre `apps/<poc-a>/` et `apps/<poc-b>/`. Le partage passe uniquement par `packages/ui/` et `design-tokens/`.
- **Nouveau POC** : `cp -r apps/_template apps/<nouveau>` puis renommage. Jamais à partir d'un POC existant. Pense à `cp scripts/package_TEMPLATE.py scripts/package_<nouveau>.py` et à adapter `APP_NAME` / `APP_SLUG` / `EMBED_PREFIX` en tête de fichier (sinon `package.bat` plantera).
- **Si une règle est en conflit avec une demande utilisateur** : cite la règle et la section de `STANDARD_POC.md`, propose l'alternative conforme. Si l'utilisateur insiste, demande à documenter l'écart dans le README de l'app concernée.
- **Pas de lecture des données utilisateur.** L'utilisateur teste sur ses vraies données (FTM xlsm, PDF, templates métier, DB SQLite) — c'est nécessaire et attendu. **Moi je n'y touche pas.** Interdits : `Read` sur `apps/*/backend/data/storage/`, sur les `*.db` / `*.sqlite`, sur les fichiers uploadés du user ; `cat`/`head`/`grep` sur leur contenu ; `sqlite3` exploratoire sur les tables métier. Autorisés : `ls` pour comprendre la structure (noms de fichiers seulement), travail sur le code / les configs / les schémas / les migrations / les tests. Si un check ou un test a besoin d'un fixture qui ressemble à de la donnée utilisateur, créer un fichier synthétique dans `tests/fixtures/`, jamais sur la donnée réelle. Si le user partage un extrait dans le chat pour montrer un bug, ne pas en faire de copies / mémoires / résumés persistants — traiter le minimum, puis oublier.

## Pointeurs

| Besoin | Fichier |
|---|---|
| Détail technique d'une règle, justification, exemples | [`STANDARD_POC.md`](./STANDARD_POC.md) |
| Auditer un POC existant contre le standard | [`PROMPT_AUDIT_STANDARD.md`](./PROMPT_AUDIT_STANDARD.md) |
| Décisions architecturales historisées | `docs/adr/` |
| Vérifier la conformité automatiquement | `scripts/check_standard.sh` |

## Format de réponse attendu

Pour chaque tâche de code, structure ta réponse ainsi :

1. **Vérification standard** (1-3 lignes) : conforme parce que… / non conforme à cause de…
2. **Code** : le diff ou les fichiers à créer/modifier.
3. **Anomalies détectées** : si tu vois une violation à proximité de la zone touchée, signale-la sans la corriger en silence.
4. **Suggestion de commit** : message conventionnel court (`feat(api): …`, `fix(ui): …`).
