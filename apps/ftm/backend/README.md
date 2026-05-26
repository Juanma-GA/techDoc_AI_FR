# FTM Agent v3 — backend

FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog.

## Démarrage local (dev)

```bash
cd apps/ftm/backend
python -m venv .venv
. .venv/Scripts/activate            # Windows : .venv\Scripts\activate.bat
pip install -e ".[dev]"
cp .env.example .env                # remplir MISTRAL_API_KEY si besoin
alembic upgrade head                # crée alembic_version (vide en J3)
pytest                              # 3 tests verts attendus
uvicorn app.main:app --reload --port 8000
```

Test :

```bash
curl http://127.0.0.1:8000/api/v1/health
# → {"status":"ok","version":"0.1.0","db":"ok","llm":"not_configured"}
```

OpenAPI : `http://127.0.0.1:8000/api/v1/docs`.

## Démarrage Windows non-tech

Double-clic sur `start.bat`.

## Layout

```
app/
├── main.py            # create_app() — middlewares + error handlers + routers
├── config.py          # Settings (pydantic-settings, CORS CSV→list)
├── api/
│   └── health.py      # GET /api/v1/health
├── core/
│   ├── logging.py     # structlog JSON
│   ├── request_id.py  # uuid4 + structlog contextvars
│   ├── errors.py      # AppError + 4 handlers → {code,message,detail,request_id}
│   └── mistral_client.py  # httpx async + truststore
├── db/
│   └── session.py     # engine, Base(DeclarativeBase), get_db()
├── parsers/           # remplis en S1
└── checks/            # remplis en S2
alembic/               # migrations (env.py + script.py.mako)
tests/                 # pytest (conftest force sqlite in-memory)
Dockerfile             # multi-stage, user 1001, healthcheck Python pur
```

## Format d'erreur

Toutes les erreurs renvoient :

```json
{
  "code": "PROJECT_NOT_FOUND",
  "message": "Projet introuvable",
  "detail": null,
  "request_id": "8c4f…"
}
```

Détails dans [`docs/adr/0003-error-format.md`](../../../docs/adr/0003-error-format.md).

## Règles métier (validation)

Les règles métier déterminent ce que les contrôles d'analyse vont remonter
comme anomalie. Elles vivent à deux endroits :

- **Défauts en dur** : [`app/core/rules.py`](app/core/rules.py) — dictionnaire
  `DEFAULT_RULES`, jamais effacé. Chargé si aucun override n'existe.
- **Override persistant** : `data/rules.json` — créé / mis à jour par l'UI
  Paramètres (`PUT /api/v1/settings/rules`) et supprimé par « Réinitialiser »
  (`DELETE /api/v1/settings/rules`).

Le code lit toujours via `app.core.rules.load_rules()` ; les contrôles
fusionnent silencieusement les listes vides → aucune anomalie pour cette
catégorie (désactivation par configuration).

### Catégories disponibles

| Clé JSON | Type d'anomalie | Sévérité défaut | Cible | Filtre LLM |
|---|---|---|---|---|
| `termes_interdits` | `consistency` | medium | Tout terme du document | non |
| `sections_obligatoires` | `consistency` | medium / low | Document ou onglet | non |
| `motifs_references` | `consistency` | low | Comptage > 10 | non |
| `paires_ambigues` | `consistency` | (LLM) | Confusion contextuelle de termes | oui (`_llm_consistency`) |
| `paires_logiques` | **`logical_pair`** | (LLM) | Action sans contre-action | **oui** (cf. ci-dessous) |
| `types_fichiers_attendus` | `naming` | high | Extension de fichier | non |
| `nomenclature_fichiers` | `naming` | medium | Pattern du nom de fichier | non |
| `regex_code_dmc` | (mode legacy) | — | Extraction codes DMC dans le texte | non |
| `instructions_libres` | (prompt) | — | Texte injecté en haut du prompt LLM | — |

`dmc_missing` (couverture du référentiel) est généré par le contrôle DMC
indépendamment de ces règles, à partir du fichier référentiel uploadé sur le
projet et de la colonne sélectionnée. Il n'est pas affiché dans les
catégories ci-dessus du dashboard (cf. carte « Couverture du référentiel »).

### `termes_interdits`

```json
[{ "terme": "enclencher", "a_utiliser": "déclencher", "raison": "Terminologie client imposée" }]
```

Une anomalie par terme et par fichier (anti-bruit : on signale la première
occurrence). Match insensible à la casse, mots entiers (`\b<terme>\b`).

### `sections_obligatoires`

```json
["Préparation", "Opérations", "Vérifications finales"]
```

Stratégie de détection :

- Documents avec marqueurs `[ONGLET: …]` / `[PAGE: …]` (xlsm, PDF) → check
  par feuille / page. Si la section est absente de TOUTES → 1 anomalie
  globale ; si présente partiellement → 1 anomalie low par feuille
  manquante.
- Documents simples (`.docx`, `.txt`) → check global sur le texte.

### `paires_ambigues`

```json
[["déclencher", "enclencher"], ["monter", "installer"]]
```

Couples de termes souvent confondus. Détectés par la passe sémantique
Mistral (`_llm_consistency`) — appel LLM unique pour toutes les paires
configurées, qui retourne une liste d'anomalies avec gravité.

### `paires_logiques`

```json
[{
  "action": "connecter",
  "contre_action": "déconnecter",
  "raison": "Toute connexion doit être suivie d'une déconnexion en fin de procédure.",
  "scope": "file"
}]
```

Détecte les cycles d'opération **incomplets** (action présente sans sa
contre-action). Différent de `paires_ambigues` qui détecte des confusions
de termes ; ici on contrôle la complétude.

- `scope = "file"` : la paire est validée si les deux termes apparaissent
  n'importe où dans le fichier.
- `scope = "sheet"` : validée feuille par feuille (réutilise `[ONGLET: …]`).
  Sur les `.docx` sans marqueurs, retombe sur le scope file.

**Pipeline en deux passes :**

1. Regex `\b<action>\b` / `\b<contre_action>\b` → liste de candidats
   `(found, missing, label, content)`.
2. Pour chaque candidat, appel `_llm_logical_pair_check` → JSON
   `{plausible, gravite, confiance, explication}` :
   - `plausible: true` (FTM de pose seule, handoff vers une autre FTM…)
     → **aucune anomalie émise**.
   - `plausible: false` → anomalie `logical_pair` avec sévérité mappée
     depuis `gravite` et confiance + explication injectées dans la
     `suggestion`.

**Indicateur de confiance** : ajouté à la `suggestion` de chaque ticket
(« Confiance IA : haute / moyenne / faible. »). Filtrable dans la Vue
Rédacteur.

**Mode strict** : si Mistral n'est pas configuré (pas de clé API), la
passe 2 est court-circuitée, l'anomalie est émise en `severity="medium"`
et la suggestion porte « Confiance IA : non évaluée (Mistral non
configuré) ».

### `nomenclature_fichiers`

```json
[{ "label": "DMC-TG", "regex": "^DMC-TG", "description": "Le nom de fichier doit commencer par DMC-TG" }]
```

Chaque fichier doit matcher au MOINS un des patterns. Liste vide =
contrôle désactivé.

### `types_fichiers_attendus`

```json
[".xlsm", ".docx"]
```

Extensions autorisées. Liste vide = contrôle désactivé.

### `instructions_libres`

Texte libre injecté en haut du prompt sémantique Mistral pour les
contrôles de cohérence. Sert aux consignes spécifiques client / projet
qui ne rentrent pas dans les catégories structurées.

### Édition

- **UI Paramètres** (page `Paramètres` du frontend) : tableaux et zones
  de texte pour chaque catégorie. Le bouton « Sauvegarder » écrit
  `data/rules.json`. Le bouton « Réinitialiser » supprime le fichier et
  ré-active les défauts du code.
- **Suggérer depuis les fichiers** : `POST /api/v1/settings/rules/suggest`
  envoie un échantillon des FTM uploadées à Mistral et propose des
  ajouts pour `termes_interdits`, `sections_obligatoires` et
  `paires_ambigues`. L'utilisateur sélectionne ce qu'il garde avant
  fusion. Mistral non configuré → 400 `MISTRAL_NOT_CONFIGURED`.

### Validation côté API

`PUT /api/v1/settings/rules` accepte `{rules: {...}}`. Validation rapide :
les clés `termes_interdits`, `sections_obligatoires`, `paires_ambigues`,
`paires_logiques`, `motifs_references` doivent être des listes (sinon
400 `RULES_INVALID`). Les autres clés sont conservées telles quelles —
les contrôles ignorent silencieusement les structures malformées.
