# Corpus Agent v4 — backend

FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog.

Contrôle de conformité documentaire d'un corpus multi-fichiers : ingestion de
documents, analyse contre un catalogue de règles métier configurables + des
règles personnalisées importables, détection d'anomalies, KPIs, et chat RAG
assisté par Mistral (désactivable).

## Démarrage local (dev)

```bash
cd apps/corpus-agent/backend
python -m venv .venv
. .venv/Scripts/activate            # Windows : .venv\Scripts\activate.bat
pip install -e ".[dev]"
cp .env.example .env                # remplir MISTRAL_API_KEY si besoin
alembic upgrade head
pytest                              # la suite doit passer au vert
uvicorn app.main:app --reload --port 8000
```

Test :

```bash
curl http://127.0.0.1:8000/api/v1/health
# → {"status":"ok","version":"4.0.0","db":"ok","llm":"not_configured"}
```

OpenAPI : `http://127.0.0.1:8000/api/v1/docs`.

## Démarrage Windows non-tech

Double-clic sur `start.bat`.

## Layout

```
app/
├── main.py            # create_app() — middlewares + error handlers + routers + serving React
├── config.py          # Settings (pydantic-settings, CORS CSV→list)
├── api/               # health, projects, files, analysis, anomalies, kpis, chat, settings, i18n, admin
├── core/
│   ├── logging.py     # structlog JSON
│   ├── request_id.py  # uuid4 + structlog contextvars
│   ├── errors.py      # AppError + handlers → {code,message,detail,request_id}
│   ├── mistral_client.py   # httpx async + truststore + interrupteur LLM
│   ├── indexer.py     # embeddings Mistral + recherche cosinus (RAG)
│   ├── chat_engine.py # chat RAG multi-scope + résumé d'anomalies
│   ├── rules.py       # DEFAULT_RULES + load_rules()/save_rules() (override data/rules.json)
│   ├── rules_catalog.py    # catalogue déclaratif des familles de règles (registry)
│   └── checklist_excel.py  # parsing d'une checklist Excel → règles personnalisées
├── parsers/           # .docx, .doc, .pdf, .xlsx/.xlsm, .xml/S1000D (+ repli texte)
├── checks/            # script, granule, text_rules, operations, referentiel_items, illustration, custom_rules
├── db/                # models.py, session.py
└── static/i18n/       # traductions FR/EN (source de vérité, servies par GET /api/v1/i18n/{lang})
alembic/               # migrations (SQLite ⇄ Postgres)
tests/                 # pytest (conftest force un SQLite temporaire + storage temp)
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

## Pipeline d'analyse

`POST /api/v1/projects/{id}/analysis/run` applique **7 contrôles séquentiels** à
la dernière version de chaque fichier du projet, dans l'ordre :

1. `script` — conformité du code script attendu (colonne de référence `script`).
2. `granule` — cohérence des granules dépose/pose vs référentiel.
3. `text_rules` — règles de texte (format des phrases, ordre des tâches,
   tâches induites, orthographe assistée IA…).
4. `operations` — rechanges, outillages, infrastructure, mise en sécurité,
   opérations préliminaires / complémentaires, serrages, verrouillages.
5. `referentiel_items` — couverture des éléments attendus du référentiel.
6. `illustration` — format du repérage, dimensions, taille, cohérence visuelle
   (contrôles vision multimodale optionnels).
7. `custom_rules` — **règles personnalisées** (voir plus bas), évaluées par IA.

Les anomalies sont créées avec le statut `open`, un type, une sévérité et un
niveau de confiance IA. Après les contrôles, les documents sont indexés
(embeddings) pour le chat RAG.

## Règles métier

Deux niveaux, tous deux lus via `app.core.rules.load_rules()` :

- **Catalogue par défaut** — familles de règles déclarées dans
  [`app/core/rules_catalog.py`](app/core/rules_catalog.py) (registry) et leurs
  défauts dans [`app/core/rules.py`](app/core/rules.py) (`DEFAULT_RULES`). Ce
  catalogue est la **source de vérité** : ne pas le redocumenter ici (risque de
  dérive). Il est exposé en lecture seule par `GET /api/v1/settings/rules/catalog`
  et listé dans l'onglet Paramètres pour transparence.
- **Override persistant** — `data/rules.json` (gitignoré), écrit par
  `PUT /api/v1/settings/rules` / `…/rules/sparse` et supprimé par
  `DELETE /api/v1/settings/rules` (retour aux défauts du code). Merge profond :
  une famille partiellement sauvegardée est complétée par les défauts.

### Règles personnalisées (IA) + import de checklist

Sous la clé `regles_personnalisees` de `rules.json` : une liste de
`{id, label, consigne, severity, validated}`. La `consigne` est une règle en
langage naturel ; à chaque analyse, le check `custom_rules` la soumet au Mistral
embarqué contre le contenu de chaque document et remonte les écarts (type
d'anomalie `personnalisee`). Skippé si Mistral est désactivé/non configuré.

Trois façons de les alimenter :

- **Saisie / édition** dans l'onglet Paramètres (éditable : libellé, consigne,
  sévérité, suppression).
- **Extraction depuis une spec** : `POST /api/v1/settings/rules/from-spec`
  (upload d'un document, l'IA propose des règles à relire).
- **Import de checklist Excel** : `POST /api/v1/settings/rules/checklist/inspect`
  (aperçu des onglets + mapping colonnes) puis
  `POST /api/v1/settings/rules/checklist/import` (`.xlsx`/`.xlsm`, colonnes
  sujet/vérification/criticité, modes `replace`/`add`/`update`/`overwrite`).
  Structure idéale + 5 règles d'exemple : `GET /api/v1/settings/rules/checklist/template`
  (bouton « Télécharger un modèle » dans l'UI), régénérable via
  `scripts/make_checklist_template.py`.

**File de validation** : une règle importée arrive `validated=false` et
**n'entre pas** dans l'analyse tant qu'un humain ne l'a pas validée
(`POST /api/v1/settings/rules/validate-all`, ou validation individuelle depuis
l'UI). Les règles sans le champ `validated` (saisies à la main) sont considérées
validées — compat ascendante.

### `instructions_libres`

Texte libre injecté en tête du prompt des contrôles IA — consignes générales
transverses qui ne rentrent pas dans une règle structurée.
