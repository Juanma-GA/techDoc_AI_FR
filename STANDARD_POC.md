# STANDARD_POC.md — référence technique du monorepo

Référence technique des règles de développement. Lue par les humains et par Claude quand [`CLAUDE.md`](./CLAUDE.md) le pointe. Format : énoncé court, justification, exemple conforme, exemple non conforme.

**Posture générale** : POC **local-first stricte**. Le mode par défaut et seul supporté est l'exécution locale sur le PC du dev. Pas de Docker, pas de CI, pas de déploiement dans le périmètre du standard. Si un POC sort de ce périmètre, il bascule vers un autre standard (hors scope ici).

## 1. Structure du monorepo

```
internal-poc-monorepo/
├── apps/<poc>/                       # 1 POC = 1 app full-stack lancée localement
│   ├── README.md                     # niveau app — auth, écarts, démarrage
│   ├── start.bat                     # lanceur Windows — wrapper court
│   ├── _run.bat                      # logique de lancement Windows
│   ├── start.sh                      # lanceur Unix
│   ├── package.bat                   # packaging Windows — wrapper court
│   ├── _package.bat                  # logique de packaging Windows
│   ├── backend/                      # FastAPI
│   │   ├── README.md                 # niveau backend — détail tech
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   ├── alembic/
│   │   ├── data/                     # SQLite + uploads (gitignoré)
│   │   ├── .env.example
│   │   ├── app/
│   │   └── tests/
│   └── frontend/                     # Vite + React
│       ├── package.json
│       ├── tsconfig.json
│       ├── tailwind.config.ts
│       ├── vite.config.ts
│       ├── index.html
│       ├── src/
│       └── tests/
├── apps/_template/                   # squelette canonique copié pour chaque nouveau POC
├── packages/
│   └── ui/                           # @internal/ui (shadcn + Radix + Lucide)
├── design-tokens/
│   ├── tokens.json                   # source unique des couleurs/typo/dimensions, dual-theme
│   └── tailwind-preset.ts            # preset Tailwind partagé qui consomme tokens.json
├── tools/
├── scripts/
│   └── check_standard.sh             # vérification automatique avant commit
├── docs/adr/
├── tsconfig.base.json                # config TS racine étendue par chaque frontend
├── pnpm-workspace.yaml
└── package.json                      # scripts par POC : dev:<poc>, test:<poc>
```

**Règle**. Tout code partagé vit dans `packages/ui/` (côté front) ou `design-tokens/`. Aucune dépendance runtime entre apps. Si deux POCs ont besoin du même composant UI, il monte dans `packages/ui/`.

## 2. Mutualisé vs propre au POC

| Élément | Mutualisé | Propre à l'app (`apps/<poc>/`) |
|---|---|---|
| Composants UI atomiques (Button, Card, Dialog…) | ✅ `packages/ui/` | ❌ jamais |
| Composants métier (AnomalyTable, SuggestionPanel) | ❌ | ✅ `frontend/src/components/business/` |
| Tokens design (couleurs, typo, dimensions) | ✅ `design-tokens/tokens.json` | ❌ jamais |
| Preset Tailwind | ✅ `design-tokens/tailwind-preset.ts` | ✅ extends preset dans `tailwind.config.ts` |
| Config TypeScript de base | ✅ `tsconfig.base.json` racine | ✅ extends dans `frontend/tsconfig.json` |
| Logique métier backend (parsers, checks, endpoints) | ❌ | ✅ `backend/app/` |
| Migrations Alembic | ❌ | ✅ `backend/alembic/` |
| README, start.bat, start.sh, .env.example | ❌ | ✅ niveau app + niveau backend |

## 3. Backend

### 3.1 Stack

| Couche | Choix | Version |
|---|---|---|
| Runtime | Python | 3.11+ |
| Framework HTTP | FastAPI | ≥ 0.115 |
| ASGI | uvicorn | ≥ 0.34 |
| Validation I/O | Pydantic | v2 |
| ORM | SQLAlchemy | 2.0 |
| Migrations | Alembic | ≥ 1.13 |
| Client LLM | httpx async + sse-starlette | ≥ 0.28 |
| Logs | structlog | ≥ 24.1 |
| Settings | pydantic-settings | ≥ 2.0 |
| Tests | pytest + pytest-asyncio + httpx AsyncClient | ≥ 8.0 |

**Bannis** : Flask (sync, pas d'OpenAPI natif, pas de validation typée intégrée), Streamlit (re-run du script à chaque interaction, pas de séparation back/front), SDK Mistral officiel, LangChain (LangGraph standalone toléré).

### 3.2 Organisation des modules

```
apps/<poc>/backend/
├── app/
│   ├── main.py              # create_app() + middlewares (CORS, request_id, errors)
│   ├── config.py            # pydantic-settings, validation des env vars au boot
│   ├── schemas.py           # Pydantic I/O par endpoint
│   ├── api/                 # 1 fichier par ressource (+ health.py obligatoire)
│   │   └── preview.py       # facultatif — render_preview() + _build_css_vars() pour mode no-Node
│   ├── core/                # logging, request_id, errors, mistral_client, etc.
│   ├── parsers/             # 1 module par format (docx, pdf, xlsx) — pur, testable
│   ├── checks/              # 1 module par contrôle métier — pur, testable
│   ├── db/                  # session, Base, modèles SQLAlchemy
│   ├── static/              # facultatif — assets servis par FastAPI (favicon, i18n JSON, etc.)
│   └── templates/           # facultatif — preview.html (UI autonome HTML/CSS/JS pour mode no-Node)
├── tests/                   # 1 fichier par route minimum
├── alembic/
├── data/                    # SQLite + uploads (gitignoré)
├── .env.example
├── README.md
└── pyproject.toml
```

**Règle**. Pas de fichier `routes.py` monolithique. Une ressource = un fichier dans `api/`. Logique transverse = `core/`. Code métier pur = `parsers/` ou `checks/`. Les dossiers `static/` et `templates/` sont tolérés pour servir le bundle Vite buildé ou une page preview HTML/JS autonome — pas pour héberger des templates Jinja métier.

### 3.3 Conventions API

| Règle | Standard |
|---|---|
| Préfixe URL | `/api/v1/` obligatoire dès J1 |
| Health check | `GET /api/v1/health` → `{status, version, db, llm}` |
| Format d'erreur | `{code, message, detail, request_id}` partout |
| Codes HTTP | 400 / 401 / 403 / 404 / 422 / 500 explicites |
| IDs ressources | UUID v4 (jamais d'auto-incrément exposé) |
| Pagination | `?limit=N&cursor=…` dès >100 items |
| Streaming | SSE pour chat et toute génération > 5s |
| Validation | Chaque body = modèle Pydantic, toute response typée |

**Conforme**

```python
@router.post("/projects", response_model=ProjectResponse, status_code=201)
async def create_project(body: ProjectCreate, db: Session = Depends(get_db)):
    project = Project(id=uuid4(), name=body.name)
    db.add(project); db.commit()
    return project
```

**Non conforme**

```python
@router.post("/create_project")  # pas de /api/v1/, verbe dans l'URL
async def create_project(request: Request):
    data = await request.json()  # pas de validation Pydantic
    project = Project(id=db.query(Project).count() + 1, name=data["name"])  # ID int
    return {"ok": True}  # pas de response typée
```

### 3.4 Persistance

**SQLite par défaut**. Fichier `apps/<poc>/backend/data/<poc>.db`, gitignoré.

| Règle | Standard |
|---|---|
| Fichier DB | `apps/<poc>/backend/data/<poc>.db` |
| Driver | SQLAlchemy 2 + sqlite3 stdlib |
| Concurrence | `PRAGMA journal_mode=WAL` activé |
| Migrations | Alembic obligatoire dès J1 |
| Compatibilité Postgres | Migrations testées en SQLite ET Postgres dès J1 |
| UUID | `String(36)` côté SQLite (compatible Postgres `UUID` natif) |
| Variable de bascule | `DATABASE_URL` unique, lue par `app/config.py` |
| Storage fichiers | `apps/<poc>/backend/data/storage/{project_uuid}/{file_version_uuid}_{name}` |
| Versionnage fichiers | SHA-256 calculé à l'upload, stocké en base |

**Bascule Postgres** : seuils explicites — > 100k lignes, > 5 utilisateurs concurrents, ou besoin de Row Level Security. Sous ces seuils, SQLite suffit. Ne pas basculer sur Postgres « parce que c'est plus pro ».

**Conforme** : `String(36)` pour UUID, `DATABASE_URL=sqlite:///./data/foo.db` par défaut, `DATABASE_URL=postgresql://…` au moment de la bascule sans modifier le code.

**Non conforme** : `JSON` SQLite-spécifique, `Base.metadata.create_all()` au démarrage, `sqlite:///` hardcodé.

### 3.5 Sécurité — Auth = palier 1 unique

**Tout POC est local seul.** Pas d'auth, bind `127.0.0.1` obligatoire, jamais `0.0.0.0`. Le palier est documenté en haut du `apps/<poc>/README.md` :

```markdown
## Auth
**Palier** : 1 — local seul, bind 127.0.0.1, pas d'authentification.
```

**Justification** : aucun POC n'est exposé sur un réseau dans le périmètre du standard. Si un POC sort de ce périmètre (déploiement sur URL, démo distante), il sort aussi du standard POC — voir l'ADR de déploiement (à créer le jour où le besoin émerge).

**Autres règles de sécurité** :
- CORS liste blanche explicite, pas `["*"]`.
- Clé API LLM côté serveur uniquement, jamais saisie dans l'UI.
- Aucun secret committé. `.env` gitignoré, `.env.example` fournit la liste des variables avec valeurs factices.
- Validation MIME et taille des uploads côté serveur (`max_upload_size_mb` dans `config.py`).

**Conforme**

```python
# uvicorn lancé avec --host 127.0.0.1 --port 8000
# pas de middleware auth
```

**Non conforme** : `--host 0.0.0.0` dans `start.bat`/`start.sh` ou dans le code.

### 3.6 Observabilité

| Règle | Standard |
|---|---|
| Logs backend | `structlog` JSON, niveau via env var |
| `request_id` | uuid4 en header `X-Request-Id`, propagé via `contextvars` dans toute la chaîne |
| Health check | `GET /api/v1/health` retournant `{status, version, db, llm}` |
| Logs frontend | `console.error` en dev OK, jamais de `console.log` committé |
| ErrorBoundary | Obligatoire au niveau App + par route React |

**Bannis** : `print()` en code committé, `console.log` en code committé, `debug=True` en code committé.

### 3.7 Endpoints standards + `AppConfig`

Au-delà de `/health`, tout POC expose :

| Endpoint | Description |
|---|---|
| `GET /api/v1/admin/stats` | Compteurs (documents, chunks, sessions, messages, total_size_bytes). Consommé par l'onglet Données du preview. |
| `POST /api/v1/admin/reset/all` | Vide les tables métier ; **préserve `app_config`** (clé Mistral). |
| `POST /api/v1/admin/reset/<scope>` | Reset par scope (ex. `documents`, `sessions`). |
| `GET /api/v1/settings` | Lit la config Mistral runtime (`api_key_set: bool`, `base_url`, `chat_model`, `embed_model`). |
| `POST /api/v1/settings` | Met à jour les clés fournies (vide = inchangé). |
| `POST /api/v1/settings/test` | Liste les modèles Mistral pour vérifier la connexion. |

**Table `AppConfig`** (`app_config`) **obligatoire** dans tout POC :

```python
class AppConfig(Base):
    __tablename__ = "app_config"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="", server_default="")
```

Sert à stocker la clé Mistral et toute config runtime (modèles utilisés, base URL...). **Préservée par convention lors d'un reset admin** — le user ne doit pas perdre sa clé en cliquant « Tout supprimer ». Migration `0001_initial.py` créant cette table est fournie par le `_template`.

## 4. Frontend

### 4.1 Stack

| Aspect | Choix |
|---|---|
| Framework | React 18 |
| Langage | TypeScript strict (`"strict": true`, `noUncheckedIndexedAccess`) — hérité de `tsconfig.base.json` racine |
| Toolchain | Vite |
| Styling | Tailwind via preset partagé `@internal/design-tokens/tailwind-preset` |
| Composants | `@internal/ui` (shadcn + Radix), jamais de réinvention dans l'app |
| Charts | Recharts (Plotly toléré pour radar/3D uniquement) |
| Icônes | Lucide React |
| Routing | React Router v6, URLs propres via `pushState` |
| État global | Zustand (UI), TanStack Query (server state) |
| Forms | React Hook Form + Zod (toujours présents, même si pas encore utilisés) |
| i18n | i18next + JSON par locale, clés sémantiques |
| Markdown | react-markdown + remark-gfm |
| Tests | Vitest + Playwright |

**Bannis** : Babel runtime, React/Tailwind via CDN (bloque l'industrialisation), MUI / Ant Design / Chakra (deuxième système de composants concurrent à `@internal/ui`).

### 4.2 Structure

```
apps/<poc>/frontend/src/
├── main.tsx                 # ReactDOM root + providers globaux
├── App.tsx                  # Layout (sidebar + topbar + main) + ErrorBoundary + routes
├── i18n.ts                  # init i18next
├── index.css                # @tailwind directives + variables CSS si besoin
├── routes/                  # 1 fichier par page
├── components/
│   ├── business/            # composants métier propres au POC
│   └── charts/              # wrappers Recharts qui consomment tokens.json
├── hooks/                   # useApi + hooks de mutations React Query
├── lib/                     # api.ts (typé), utils.ts
├── locales/                 # fr.json, en.json
├── stores/                  # Zustand (UI global : sidebar collapsed, theme)
└── types/                   # api.ts généré par openapi-typescript, domain.ts
```

**Règle**. Pas de dossier `components/ui/` dans l'app — les primitives viennent de `@internal/ui`. Tout composant qui mérite réutilisation cross-POC monte dans `packages/ui/`.

## 5. Design system

### 5.1 Tokens

Trois fichiers à la racine de `design-tokens/`, source unique de vérité :

| Fichier | Rôle |
|---|---|
| `tokens.json` | Valeurs brutes : couleurs dark (à plat sous `color.*`) + overrides light sous `themes.light.color.*` + tokens non-thèmes (font, radius, shadow, layout). |
| `theme.css` | CSS custom properties dérivées de `tokens.json`. Pattern Tailwind classique : `:root { … }` = palette light par défaut, `.dark { … }` = overrides dark. Importé par chaque app via `index.css` (`@import "@internal/design-tokens/theme.css"`). |
| `tailwind-preset.ts` | Preset Tailwind partagé. Mappe les classes (`bg-bg`, `text-fg`…) vers `var(--color-*)` pour rendre le dual-theme automatique sans recompile. |

**Structure de `tokens.json`** :

```json
{
  "color": {
    "bg":   { "base": "#0e1117", "2": "#131720", "3": "#1a2035" },
    "card": { "base": "#161c2b", "hover": "#1d2540" },
    "brand":    { "blue": "#2563eb", "blue-light": "#3b82f6" },
    "semantic": { "success": "#10b981", "warning": "#f59e0b", "danger": "#ef4444", "info": "#3b82f6" },
    "text":     { "base": "#e2e8f0", "dim": "#94a3b8", "muted": "#4b5563" },
    "border":   { "base": "rgba(255,255,255,0.07)", "md": "rgba(255,255,255,0.12)", "bright": "rgba(37,99,235,0.4)" }
  },
  "themes": {
    "light": {
      "color": {
        "bg":   { "base": "#ffffff", "2": "#f8fafc", "3": "#e2e8f0" },
        "card": { "base": "#ffffff", "hover": "#f1f5f9" },
        "text": { "base": "#0f172a", "dim": "#64748b", "muted": "#94a3b8" },
        "border": { "base": "rgba(0,0,0,0.07)", "md": "rgba(0,0,0,0.12)", "bright": "rgba(37,99,235,0.4)" }
      }
    }
  },
  "font":   { "sans": ["Inter", "sans-serif"], "mono": ["JetBrains Mono", "monospace"] },
  "radius": { "sm": "8px", "lg": "12px" },
  "layout": { "sidebar-w": "252px", "topbar-h": "52px" }
}
```

**Pourquoi cette structure** : `color.*` reste à plat pour la rétrocompat des consommateurs JS/TS (charts Recharts qui font `color.brand.blue`). Les overrides light vivent sous `themes.light` et n'ont à contenir que les valeurs qui changent. Le preset Tailwind ne consomme **plus** ces hex directement — il consomme les CSS variables émises par `theme.css`, ce qui rend le toggle dark/light automatique sans recompiler Tailwind.

**Naming Tailwind** : le preset expose `text.*` sous `fg.*` pour éviter la classe `text-text-base`. Utiliser `text-fg`, `text-fg-dim`, `bg-bg`, `bg-bg-2`, `bg-card`, `bg-card-hover`, `text-brand-blue-light`.

**Conforme** : `<div className="bg-bg text-fg">…</div>` (classes Tailwind résolues via CSS vars, dual-theme automatique).
**Non conforme** : `<div style={{ background: "#0e1117" }}>…</div>` (hex en dur, ne suit pas le toggle theme).

**Code TS theme-aware** (charts qui doivent changer de couleurs entre dark/light) :

```ts
import { colorByTheme } from "@internal/design-tokens";
const fill = colorByTheme(theme, "text.base");  // "#e2e8f0" en dark, "#0f172a" en light
```

### 5.2 Typographie

Inter (sans), JetBrains Mono (chiffres/badges techniques). Body 13.5px line-height 1.5. Identique en dark et light. Imposé par le preset Tailwind partagé.

### 5.3 Composants `@internal/ui` (canoniques)

Liste à jour des composants disponibles dans [`packages/ui/src/index.ts`](./packages/ui/src/index.ts) :

| Catégorie | Composants |
|---|---|
| Atoms | `Badge`, `Button`, `Card` |
| Overlays (remplacent alert/confirm) | `Dialog`, `Toast` |
| Métier transverses | `ChartCard`, `EmptyState`, `KpiCard`, `LoadingOverlay` |
| Hooks & utils | `useMediaQuery`, `cn` |

**Règle d'extension** : tout composant atomique nouveau (Input, Select, Tabs, Tooltip, Skeleton, etc.) se crée dans `packages/ui/` **avant** d'être consommé dans une app. Pas de réinvention locale dans `apps/<poc>/frontend/src/components/`.

**Bannis** :
- `alert()` natif (bloquant, pas stylable, pas a11y) → utiliser `Dialog`.
- `confirm()` natif → utiliser `Dialog` avec actions.
- Icônes Unicode/emoji dans le JSX (rendu OS-dépendant, a11y cassée) → utiliser `lucide-react`.
- Classes utilitaires `.btn-*` qui doublent un composant existant.

### 5.4 Theme dark / light

Chaque POC supporte le toggle dark/light dans **les deux modes de rendu** :

- **Mode Vite/React** (quand Node est installé et le bundle frontend buildé) : `index.html` + `App.tsx` avec `<ThemeToggle />` importé de `@internal/ui`.
- **Mode preview HTML** (fallback servi par FastAPI quand pas de bundle Vite, via `app/api/preview.py` + `app/templates/preview.html`) : bouton SVG inline + JS toggle inline + CSS variables émises par `_build_css_vars()` à partir de `tokens.json`.

**Mécanique commune aux deux modes** :

- **Mode initial** : si `localStorage['theme']` est défini → respect ; sinon `prefers-color-scheme` ; à défaut → dark (continuité POC).
- **Application** : classe `.dark` sur `<html>`. Le preset Tailwind est en `darkMode: "class"` ; le preview consomme directement les vars CSS générées sous `:root` (light) et `.dark` (dark override).
- **Persistance** : `localStorage['theme']` = `"dark"` ou `"light"`, écrit par `ThemeToggle` ou par le toggle inline du preview.

**Snippet anti-flash** (à inclure tel quel dans `index.html` Vite **et** dans `preview.html`, en haut du `<head>` avant tout `<link>`) :

```html
<script>
  (function () {
    var stored = localStorage.getItem("theme");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (stored === "dark" || (!stored && prefersDark) || stored === null) {
      document.documentElement.classList.add("dark");
    }
  })();
</script>
```

**`meta color-scheme`** : valeur `"dark light"` dans les deux `<head>` (signal au navigateur que les deux thèmes sont supportés). Jamais `"dark"` seul (forcerait le scrollbar dark même en mode light).

**Toggle inline** dans `preview.html` (côté backend, sans React disponible) : bouton SVG Sun/Moon dans `.sidebar-header`, JS minimal qui ajoute/retire `.dark` et écrit `localStorage['theme']`. Le code identique vit dans `apps/<poc>/backend/app/templates/preview.html` de chaque app.

## 6. LLM

| Règle | Standard |
|---|---|
| Provider | Mistral API (`mistral-medium-latest` par défaut) |
| Client | `httpx` async direct, pas de SDK Mistral |
| Streaming | SSE obligatoire sur chat et toute génération > 5s, via `sse-starlette` |
| Framework wrapper | Aucun — LangChain banni |
| Exception LangChain | LangGraph standalone toléré pour graphes d'agents complexes |
| Audit | Table `llm_invocation_audit` peuplée à chaque appel (model, status, tokens, request_id) |
| Clé API | Côté serveur uniquement, persistée dans la table `AppConfig` (jamais committée, jamais saisie dans le frontend) |

**Conforme** : appel `httpx.AsyncClient` + stream SSE + ligne `LLMInvocationAudit` écrite. **Non conforme** : `from langchain.chat_models import ChatMistralAI`, ou appel synchrone qui bloque l'event loop.

### 6.1 Contrat SSE

Endpoint **POST** (jamais GET — l'`EventSource` natif refuse POST, donc le client doit utiliser `fetch + ReadableStream`).

Séquence d'events :

```
event: session
data: {"session_id": "uuid", "title": "titre court"}

event: token
data: <delta_de_texte>

event: token
data: <delta_de_texte>

...

event: done
data: {}
```

Ou en cas d'échec :

```
event: error
data: {"message": "raison de l'erreur"}
```

**Persistance** : le user message est inséré dans `messages` AVANT le premier delta ; l'assistant message complet est inséré APRÈS le `done`. Cette ordre évite de laisser un message user orphelin si le stream échoue mid-way.

**Client preview HTML** : snippet de référence pour parser le flux :

```js
const resp = await fetch(API + "/sessions/" + id + "/ask", {
  method: "POST",
  headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
  body: JSON.stringify({ question }),
});
const reader = resp.body.getReader();
const decoder = new TextDecoder("utf-8");
let buffer = "";
while (true) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });
  let sep;
  while ((sep = buffer.indexOf("\n\n")) !== -1) {
    const chunk = buffer.slice(0, sep);
    buffer = buffer.slice(sep + 2);
    // parse "event: X\ndata: Y" ici, dispatcher selon X
  }
}
```

## 7. i18n

`i18next` câblé dès J1. Fichiers `src/locales/{fr,en}.json` minimum. Clés **sémantiques** (`diagnostic.swot.title`), jamais la chaîne FR comme clé. Fallback explicite `fr → en → clé brute`. Pluralisation ICU si besoin.

**Conforme** : `t('diagnostic.swot.title')`. **Non conforme** : `t('Diagnostic SWOT')`.

## 8. Tests

| Périmètre | Outil | Minimum |
|---|---|---|
| Backend | pytest + httpx AsyncClient | 1 test par route |
| Composants atomiques | Vitest + Testing Library | 1 test par composant de `packages/ui/` |
| Parcours critiques | Playwright | 1 smoke test par parcours métier majeur |
| Linter | ruff (Python) + ESLint (TS) | Bloquant à la sauvegarde |

`scripts/check_standard.sh` doit retourner exit 0 avant tout commit. Il vérifie au minimum :
- Préfixe `/api/v1/` monté dans chaque `apps/*/backend/app/main.py`.
- Absence de `console.log` dans `apps/*/frontend/src/`.
- Absence de `print(` dans `apps/*/backend/app/`.
- Absence de hex en dur hors `tokens.json` et `tailwind-preset.ts`.
- Absence de `alert(`/`confirm(` dans `apps/*/frontend/src/`.
- Absence de `debug=True` dans `apps/*/backend/app/`.
- Chaque `apps/*/_run.bat` déclare `set "PORT=80XX"` et vérifie le port libre (`findstr "LISTENING"`) avant uvicorn.

## 9. Lanceurs locaux et packaging

Chaque POC fournit **cinq** fichiers à la racine de `apps/<poc>/` (quatre `.bat` + un `start.sh`), copiés depuis `apps/_template/` :

| Fichier | Rôle |
|---|---|
| `start.bat` | Wrapper Windows ultra-court — `start "..." cmd /k "%~dp0_run.bat"` pour spawn une fenêtre qui reste ouverte quoi qu'il arrive. |
| `_run.bat` | Logique de lancement Windows (détection Python, venv, deps, Alembic, uvicorn). **ASCII pur** : aucun accent (sinon cmd.exe ferme la fenêtre avant que l'utilisateur ne voie le message). |
| `start.sh` | Équivalent Unix (variable `PORT` configurable, `lsof` pour vérifier que le port est libre). |
| `package.bat` + `_package.bat` | Wrapper Windows qui spawn une fenêtre `cmd /k` et délègue à `scripts/package_<poc>.py` pour produire un ZIP autonome. |

**Comportement attendu de `start.bat`** :

1. Variable `PORT` unique en haut du `_run.bat` (à ajuster par POC).
2. Détecter Python 3.11+ (system, embed, ou installer silencieux selon le contexte).
3. Créer le venv si absent (`backend/.venv/`).
4. Installer les deps Python si pas déjà fait (marker `.installed`).
5. Lancer `alembic upgrade head` (idempotent).
6. **Résoudre un port libre** : tester `PORT` ; s'il est occupé, basculer automatiquement sur le premier port libre suivant (jusqu'à `PORT+20`). Sortir en erreur seulement si toute la plage est occupée.
7. Lancer `uvicorn app.main:app --host 127.0.0.1 --port %PORT%` sur le port résolu.
8. Ouvrir le navigateur sur `http://127.0.0.1:<port>/` — sert l'UI React si `frontend/dist/` a été buildé, sinon la preview HTML autonome (mount auto dans `main.py`). Swagger reste accessible sur `/api/v1/docs`.

**Comportement attendu de `package.bat`** :

1. Appelle `python scripts/package_<poc>.py --out apps/<poc>/dist`.
2. Produit `apps/<poc>/dist/<poc>-vX.Y.Z-YYYYMMDD.zip` contenant : `start.bat` racine, `apps/<poc>/`, `design-tokens/`, `python-embed/` (Python 3.11 embarqué), `frontend/dist/` si Node disponible.
3. Le script `scripts/package_<poc>.py` est créé par `cp scripts/package_TEMPLATE.py scripts/package_<poc>.py` et l'adaptation de `APP_NAME` / `APP_SLUG` / `EMBED_PREFIX` en tête de fichier.

**Règles non négociables** :
- `--host 127.0.0.1` toujours. Jamais `0.0.0.0` (palier 1 strict).
- `.bat` en ASCII pur. Les accents dans un `.bat` non-CP1252 peuvent provoquer une fermeture immédiate de cmd.exe — préférer "echec" à "échec".
- La fenêtre cmd doit **toujours rester ouverte** en cas d'erreur (wrapper `cmd /k`).
- Chaque `_run.bat` **doit** déclarer `set "PORT=80XX"` en tête et résoudre un port libre **avant** uvicorn — bascule automatique sur `PORT+1`, `PORT+2`… si le port par défaut est occupé. Jamais de port codé en dur dans la commande uvicorn. **Vérifié automatiquement par `scripts/check_standard.sh` (check 7)** — un `_run.bat` sans variable `PORT`, sans check `findstr "LISTENING"`, ou sans la boucle de bascule `:find_port` fait échouer le script.
- Pas de `--reload` sur uvicorn : c'est un flag de dev, proscrit dans un `_run.bat` destiné au lancement local stable et au packaging.

### 9.1 Pièges courants des `.bat`

**Symptôme : la fenêtre se ferme immédiatement à l'ouverture.**

Diagnostic : 9 fois sur 10, encoding UTF-8 avec accents. `cmd.exe` lit dans la code page active (souvent CP1252) ; si octets multi-byte invalides, il abort silencieusement. Vérif : `file apps/<poc>/*.bat` doit afficher `DOS batch file, ASCII text` partout. Sinon réécrire en remplaçant les accents.

**Symptôme : `« ... était inattendu »` dans la fenêtre puis fermeture.**

Diagnostic : une `(` ou `)` non échappée dans un `echo` à l'intérieur d'un block `if (...)`. Cmd interprète le `)` comme fin du block. Exemple cassé :

```bat
if not exist "%INSTALLED_MARK%" (
    echo Installation des deps (1 a 3 min)...    REM <-- KO
    ...
)
```

Solutions :
- Reformuler sans parens : `echo Installation des deps - 1 a 3 min...`
- Ou échapper : `echo Installation des deps ^(1 a 3 min^)...`

**Symptôme : uvicorn crash silencieusement, ou ne démarre pas.**

Diagnostic : port déjà occupé (souvent un précédent uvicorn zombie, ou l'app lancée deux fois). Le `_run.bat` cherche un port libre avant le bind et bascule automatiquement si le port par défaut est pris :

```bat
set /a PORT_TRY=%PORT%
set /a PORT_MAX=%PORT% + 20

:find_port
netstat -ano | findstr ":%PORT_TRY%" | findstr "LISTENING" >nul 2>nul
if errorlevel 1 goto :port_ok
set /a PORT_TRY=PORT_TRY + 1
if %PORT_TRY% GTR %PORT_MAX% goto :no_port
goto :find_port

:no_port
echo [erreur] Aucun port libre entre %PORT% et %PORT_MAX%.
pause
exit /b 1

:port_ok
if not "%PORT_TRY%"=="%PORT%" echo [info] Port %PORT% occupe -- bascule auto sur le port %PORT_TRY%.
set "PORT=%PORT_TRY%"
```

Le navigateur et uvicorn consomment ensuite `%PORT%` résolu. Hisser le port par défaut dans une variable unique en tête de `_run.bat` (`set "PORT=80XX"`).

## 10. Preview HTML autonome (sans Node)

### Motivation

Palier 1 = local-first strict, sans pré-requis Node côté utilisateur. Sans `frontend/dist/` (= sans build React préalable), le backend doit quand même servir une UI utilisable à `/`. Le preview HTML est cette UI — vanilla JS, design-tokens injectés, consomme directement l'API REST.

### Fichiers obligatoires

| Fichier | Rôle |
|---|---|
| `backend/app/templates/preview.html` | UI vanilla JS complète. ASCII pur dans les strings inline (les accents passent par l'i18n FR injecté dynamiquement). |
| `backend/app/api/preview.py` | Renderer qui lit `design-tokens/tokens.json` + `frontend/src/locales/fr.json`, remplace les placeholders `/*__CSS_VARS__*/` et `/*__I18N_FR__*/` dans le template, retourne `HTMLResponse`. |
| `backend/app/main.py` | `_mount_frontend()` : si `frontend/dist/` existe → SPA Vite ; sinon → `render_preview()` à `/`. Les routes `/api/v1/*` sont enregistrées AVANT pour priorité sur le catch-all. |

### Onglets standards (minimum)

| Onglet | Contenu |
|---|---|
| **Home** | Page d'accueil sobre. Statut backend (`/health`) en badge. Pointe vers les fichiers à éditer pour personnaliser le POC. |
| **Architecture** | Card 1 : 2 colonnes (`.grid-2`) Backend / Frontend décrivant la stack en 30 secondes. Card 2 : workflow utilisateur numéroté (6 étapes typiques). |
| **Données** | KPI grid alimentée par `GET /api/v1/admin/stats` + bouton "Tout supprimer" avec pattern double-clic → `POST /api/v1/admin/reset/all`. |
| **Paramètres** | Formulaire Mistral (api_key / base_url / chat_model / embed_model) + bouton "Tester la connexion" → `POST /api/v1/settings/test`. |

Le POC ajoute ses onglets métier.

### Conventions visuelles

- **Fonts Google** (chargées via `<link>` dans `<head>`) :
  - `Inter` (400/500/600/700) — body sans-serif
  - `JetBrains Mono` (400/500/700) — `.label`, `code`, `.kpi-value`
  - `Orbitron` (500/700) — `.brand`, `.page-header h1`, `.card-title`
- **Layout** : `html { font-size: 13.5px; }`, sidebar `var(--sidebar-w)` (252px), topbar 52px, main padding `24px 32px`.
- **Classes CSS standardisées** :

| Classe | Variants | Usage |
|---|---|---|
| `.btn` | `.primary` `.secondary` `.ghost` `.danger` `.small` | Tous les boutons |
| `.card` | + `.card-title` (Orbitron) | Container de section |
| `.kpi-grid` | + `.kpi` + `.kpi-value` (`.info` `.ok` `.warn` `.err`) | Compteurs onglet Données |
| `.arch-flow` | + `.arch-step` + `.step-n` (mono) | Workflow numéroté Architecture |
| `.arch-split` | + `.label.brand-color` / `.label.accent-color` | 2-col Backend/Frontend |
| `.banner` | + `.warn` | Bandeau d'info ou warning |
| `.badge` | `.ok` `.warn` `.danger` `.info` | Pastilles d'état |
| `.input` | (state via classe ajoutée) | Champs `<input>`, `<select>`, `<textarea>` |
| `.dropzone` | + `.dragover` | Zone drag&drop |
| `.empty-state` | — | Texte centré "Aucun X" |
| `.label` | — | Étiquette uppercase mono |

- **Couleurs** : toutes via CSS vars injectées depuis `tokens.json` par `preview.py`. **Aucun hex en dur** dans le HTML (règle #4).

### Theme toggle (dark ↔ light)

Pattern obligatoire dans `<head>` (anti-flash, applique le theme AVANT que le HTML render) :

```html
<script>
  (function () {
    var stored = localStorage.getItem("theme");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    if (stored === "dark" || (!stored && prefersDark) || stored === null) {
      document.documentElement.classList.add("dark");
    }
  })();
</script>
```

Bouton sun/moon SVG dans la `sidebar-header`. CSS toggle entre les deux via `.dark .theme-toggle-sun` / `.theme-toggle-moon`. Le clic toggle la classe `.dark` sur `<html>` et persiste en `localStorage["theme"]`.

### i18n pattern (auto-switch FR ↔ EN)

Deux niveaux :

1. **Strings statiques** (HTML) : attribut `data-i18n="key"` sur les éléments dont le `textContent` doit être traduit.
2. **Strings dynamiques** (rendus par JS) : fonction `t(key)` appelée dans les `innerHTML` template literals.

Snippet de référence :

```js
const I18N = {
  fr: { "nav.generate": "Generation", "page.generate.title": "Generation de contenu" /* ... */ },
  en: { "nav.generate": "Generate",   "page.generate.title": "Content generation"    /* ... */ },
};
let LANG = localStorage.getItem("<poc>-lang") || "fr";

function t(key) {
  return (I18N[LANG] && I18N[LANG][key]) || (I18N.fr && I18N.fr[key]) || key;
}

function applyI18n() {
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    el.textContent = t(el.dataset.i18n);
  });
  document.documentElement.lang = LANG;
}

function setLang(lang) {
  LANG = lang;
  try { localStorage.setItem("<poc>-lang", lang); } catch (e) { /* ignore */ }
  document.querySelectorAll(".lang-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.lang === lang);
  });
  applyI18n();
  navigate(state.currentRoute);  // re-render la page active avec les nouvelles trads
}

document.querySelectorAll(".lang-btn").forEach((b) => {
  b.addEventListener("click", () => setLang(b.dataset.lang));
});
```

Au boot : appeler `setLang(LANG)` (qui déclenche `applyI18n` + `navigate` initial).

### Pattern double-clic (au lieu de `confirm()`)

À utiliser pour toute action destructrice. La règle #2 (pas de `alert`/`confirm`) s'applique aussi au preview HTML.

```js
document.querySelectorAll("[data-reset]").forEach((btn) => {
  let armed = false;
  let timer = null;
  const original = btn.textContent;
  btn.addEventListener("click", async () => {
    if (!armed) {
      armed = true;
      btn.textContent = t("data.confirmAgain");
      timer = setTimeout(() => { armed = false; btn.textContent = original; }, 3000);
      return;
    }
    clearTimeout(timer);
    armed = false;
    btn.textContent = original;
    // ... appel API ici ...
  });
});
```

1er clic remplace le label par « Cliquer encore pour confirmer » ; 2e clic dans les 3 secondes exécute ; au-delà, le bouton revient à son état initial.

## 11. Ajout d'un nouveau POC

```bash
cp -r apps/_template apps/<nouveau-poc>
```

Puis :

1. Renommer dans `apps/<nouveau-poc>/backend/pyproject.toml`, `apps/<nouveau-poc>/frontend/package.json`, `apps/<nouveau-poc>/README.md`.
2. Choisir un port unique pour le backend (8000, 8001, 8002…) et le poser dans la variable `PORT=` de `_run.bat` + `PORT=` en haut de `start.sh`.
3. `cp scripts/package_TEMPLATE.py scripts/package_<nouveau-poc>.py`, puis adapter `APP_NAME` / `APP_SLUG` / `EMBED_PREFIX` en tête de fichier. Mettre à jour aussi `apps/<nouveau-poc>/_package.bat` pour qu'il appelle ton nouveau script.
4. Initialiser Alembic : première migration vide via `alembic revision -m "0001 initial"`.
5. Ajouter une entrée dans `package.json` racine : `"dev:<nouveau-poc>": "pnpm --filter @apps/<nouveau-poc>-frontend dev"`.
6. Vérifier `bash scripts/check_standard.sh` exit 0.
7. Premier commit : `feat(<nouveau-poc>): bootstrap from template`.

## 12. Écarts au standard

Tout écart se documente dans `apps/<poc>/README.md` (niveau app), section dédiée :

```markdown
## Écarts au standard

### <date> — <titre court>
**Règle violée** : §<numéro section> — <énoncé court>
**Justification** : <pourquoi le contournement est nécessaire ici>
**Plan de retour à la conformité** : <si applicable, sinon "permanent">
**Validation** : <nom du mainteneur du standard qui a validé>
```

Si un écart est documenté ainsi, `check_standard.sh` peut le whitelister via un commentaire `# noqa: standard <règle>` au plus près du code concerné.

Sans documentation explicite, tout écart est traité comme une violation par le script et par les revues de code.
