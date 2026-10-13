# CLAUDE.md — règles du monorepo

Ce fichier est lu automatiquement par Claude Code à l'ouverture du repo. Il fixe le cadre local de sécurité et de méthode. Pour le détail technique normatif, voir [`STANDARD_POC.md`](./STANDARD_POC.md). L'index documentaire est [`docs/index.md`](./docs/index.md) et le workflow Git/PR est défini dans [`CONTRIBUTING.md`](./CONTRIBUTING.md).

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
6. **LLM (profil `llm` uniquement)**. Ces obligations concernent seulement les apps qui déclarent `llm` dans la section `## Profiles` de leur README. Mistral API + `httpx` async + SSE (`sse-starlette`). Pas de SDK Mistral. Pas de LangChain. **Désactivable globalement** via la clé `AppConfig` `llm_enabled` (défaut `true`) : quand OFF, chaque route qui appelle Mistral **saute la tâche confiée à l'IA** (fallback gracieux — HTTP 200 + résultat déterministe/vide, jamais 5xx) et la clé Mistral est **conservée**. Helpers standards `get_llm_enabled(db)` / `set_llm_enabled(db, bool)` dans `core/mistral_client.py`, à appeler **avant** tout `MistralClient.from_db(db)`. Une app déterministe sans IA ne déclare pas `llm` et n'a pas à fournir ces mécanismes.
7. **Persistance**. Le profil `local-first` utilise SQLite dans `apps/<poc>/backend/data/<poc>.db` (gitignoré). Alembic dès J1. PostgreSQL est réservé aux profils multi-utilisateurs ou production et doit être activé via `DATABASE_URL`.
8. **Auth = local seul (palier 1)**. Pas d'auth, bind `127.0.0.1` obligatoire, jamais `0.0.0.0`. Tout POC le déclare en haut de son README. Le déploiement (palier 2/3) sort du périmètre POC.
9. **Logs**. `structlog` JSON + `RequestIdMiddleware` + header `X-Request-Id` propagé bout en bout. ErrorBoundary obligatoire au niveau App côté front.
10. **i18n**. `i18next` câblé dès J1 avec FR + EN minimum. Clés sémantiques (`diagnostic.title`), jamais la chaîne FR comme clé.
11. **Tests**. 1 pytest par route backend, 1 Vitest par composant atomique de `@internal/ui`, 1 Playwright smoke par parcours critique. `scripts/check_standard.sh` doit rester vert avant tout commit.
12. **Launcher + packager obligatoires**. Tout POC fournit quatre `.bat` + un `start.sh` + un `_needs_rebuild.ps1` :
    - **`start.bat`** : wrapper court (3 lignes) qui fait `start "<poc>" cmd /k "%~dp0_run.bat"`. Toute la logique vit dans `_run.bat`. Le `cmd /k` garantit que la fenêtre **reste ouverte** sur erreur (sinon impossible de lire le message).
    - **`_run.bat`** : logique de lancement (détection Python, venv, deps, Alembic, **rebuild front auto**, uvicorn). Variable `set "PORT=80XX"` en tête, unique par POC. Check `netstat | findstr ":%PORT%" | findstr "LISTENING"` avant `uvicorn` ; si le port est occupé, bascule sur le premier port libre suivant dans la plage autorisée et affiche le port retenu.
    - **Rebuild front auto (règle #13)** : `_run.bat` / `start.sh` reconstruisent `frontend/dist/` quand il est **absent OU périmé** (une source front plus récente), **avant** uvicorn. Interdit de court-circuiter le build dès que `dist/` existe (`if exist dist goto ...` sec) — c'est le piège qui ressert un vieux bundle après une modif front. Le rebuild est **conditionnel** (pas de `pnpm build` systématique) : Windows délègue la comparaison de dates au helper **`_needs_rebuild.ps1`** (batch pur incapable de le faire proprement), Unix utilise `find -newer`. Si `pnpm` est absent, on sert le `dist/` existant sans rebuild.
    - **`pnpm install` JAMAIS sur le chemin critique du build (launcher ET packager)** : ne l'appeler **que si `frontend/node_modules` est absent** (`if not exist node_modules call pnpm install` en bat ; `[ -d node_modules ] || pnpm install` en sh ; skip conditionnel dans `_build_frontend` du package script). Raison : derrière un proxy qui **intercepte le TLS** (`UNABLE_TO_GET_ISSUER_CERT_LOCALLY`), un `pnpm install` « à jour » **retente chaque paquet « in 1 minute »** et bloque le lancement/packaging plusieurs minutes → symptôme « ne s'ouvre pas / ne se package pas ». `pnpm build` (`vite build`) tourne parfaitement **hors-ligne** quand `node_modules` est présent. Corollaire packager : si le build échoue mais qu'un `frontend/dist/index.html` valide existe déjà, le **conserver** (déjà bundlé) plutôt que de le traiter comme un échec silencieux.
    - **`package.bat`** + **`_package.bat`** (même pattern wrapper) qui appellent `scripts/package_<poc>.py` pour produire un ZIP autonome (Python embed + frontend dist + design-tokens). **Le ZIP sort TOUJOURS dans `apps/<poc>/dist/`** (jamais à la racine du repo) : le `--out` par défaut du script pointe sur `apps/<poc>/dist` et `_package.bat` le passe explicitement. Ne pas lancer le script sans ce `--out`.
    - **`start.sh`** : équivalent Unix, même port par défaut et même bascule vers le premier port libre suivant, variable `PORT` configurable, `lsof -iTCP:$PORT -sTCP:LISTEN` avant `uvicorn`, **même rebuild front auto** (`find -newer`).
    - **ASCII pur obligatoire** dans tous les `.bat` (pas d'accents : `échec`→`echec`, `fenêtre`→`fenetre`). Sinon `cmd.exe` ferme la fenêtre silencieusement à la lecture du fichier.
    - **Pas de parenthèses dans `echo` à l'intérieur d'un block `if (...)` du bat** : cmd interprète le `)` comme fin de block et crash silencieusement avec « X était inattendu ». Reformuler `echo Installation (1 a 3 min)` en `echo Installation 1 a 3 min` ou échapper avec `^(` `^)`.
13. **UI React (Vite), servie à `/`**. L'UI de chaque POC est l'app **React buildée** (`frontend/dist/`), servie par `main.py` (`_mount_vite_dist`) ; les routes `/api/v1/*` sont enregistrées AVANT le catch-all SPA. **Plus de preview HTML autonome** : React est désormais **obligatoire**, le build **Node/Vite est un pré-requis** du POC (le `build` vaut `vite build`, cf. règle #1). Si `frontend/dist/` est absent, `/` renvoie un message « frontend non buildé » (HTTP 503), jamais une UI de substitution. `index.html` sert l'`index.html` du dist en **no-cache** (les assets hashés `/assets/*` restent cacheables) pour que tout rebuild prenne effet sans Ctrl+F5.
    - **Composants via `@internal/ui`** (règle #3) et tokens design (règle #4). Script anti-flash thème en tête de `<head>` de `index.html`.
    - **Onglets minimum** : Home / Données / Paramètres. Le POC ajoute ses onglets métier.
    - **Standard visuel** : fonts `Inter` (sans-serif) / `JetBrains Mono` (label, code) / `Orbitron` (brand, titres) ; dual-theme dark/light via la classe `.dark` sur `<html>` et les tokens. Les préférences de thème et de langue peuvent être conservées côté navigateur ; aucune donnée d'authentification, métier ou session ne doit l'être.
    - **Indicateur + switch LLM (profil `llm` uniquement)** : badge d'état LLM dans le sidebar, alimenté par `GET /api/v1/health`. Le vert n'est PAS gratuit : `ON`/vert **uniquement** si clé configurée ET test de connexion réussi ET interrupteur ON (`llm:"ok"`) ; `A TESTER`/orange si clé présente mais aucun test réussi (`llm:"untested"`) ; `NO KEY`/orange si aucune clé effective (`llm:"not_configured"`) ; `OFF`/gris si interrupteur OFF (`llm:"disabled"`). Après un test réussi (ou un save de clé) en Paramètres, **invalider la query `health`** (TanStack Query) pour rafraîchir le badge immédiatement. Un `.switch` « LLM activé » en Paramètres `POST /settings {llm_enabled}` — pas une action destructrice → pas de double-clic, bascule immédiate.
    - **Theme toggle** : bouton sun/moon dans le sidebar. Classe `.dark` sur `<html>`. La persistance navigateur est limitée aux préférences non sensibles de thème et de langue ; jamais à l'authentification, à l'état métier ou aux sessions. Script anti-flash en `<head>` si la préférence de thème est persistée.
    - **i18n** : `i18next` FR + EN minimum, clés sémantiques (`diagnostic.title`), jamais la chaîne FR comme clé ; switch de langue FR/EN dans le sidebar.
    - **Confirmation actions destructrices** : pattern double-clic (1er clic arme le bouton « Cliquer encore pour confirmer », 2e clic dans les 3 secondes exécute). Jamais `alert()` ni `confirm()` (règle #2).
14. **Endpoints standards**. Au-delà de `/api/v1/health`, tout POC expose :
    - `GET /api/v1/admin/stats` + `POST /api/v1/admin/reset/all` (et `/reset/<scope>` par scope métier) — consommés par l'onglet Données de l'app React.
    - Pour les apps déclarant le profil `llm` : `GET /api/v1/settings` + `POST /api/v1/settings` + `POST /api/v1/settings/test` — config Mistral runtime, persistée dans la table `AppConfig` (key/value). La clé Mistral n'est jamais committée. Le champ booléen `llm_enabled` est exposé en GET et accepté en POST (interrupteur LLM). `/settings/test` renvoie `{ok:false, error:"LLM desactive"}` quand OFF.
    - Pour les apps déclarant le profil `llm`, `GET /api/v1/health` retourne `llm: "ok" | "untested" | "not_configured" | "disabled"`. `ok` = clé effective présente (DB ou `.env`, via `get_effective_settings`) ET dernier test réussi (`get_llm_tested`) ET `llm_enabled` ; `untested` = clé présente mais pas de test réussi ; `not_configured` = aucune clé effective ; `disabled` = `llm_enabled=false`. NE PAS calculer l'état avec `settings.llm_configured` (ne lit que le `.env`, ignore la clé saisie en Paramètres). Helpers standards `get_llm_tested(db)` / `set_llm_tested(db, bool)` dans `core/mistral_client.py`, posés par `/settings/test`.
    - SSE streaming (quand applicable, ex. chat / génération) : events `session` (init avec `{session_id, title}`) → `token*` (deltas successifs) → `done` (succès) ou `error` (avec `{message}`). Endpoint **POST** uniquement (l'`EventSource` natif refuse POST → côté client utiliser `fetch + ReadableStream`).
    - **`AppConfig`** (table `app_config`, key:str PK / value:text) est obligatoire pour tout POC déclarant le profil `llm`. Elle sert à stocker la clé Mistral et toute config runtime, et est préservée par convention lors d'un reset admin. La migration `0001_initial.py` est créée par défaut dans le `_template`.

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
