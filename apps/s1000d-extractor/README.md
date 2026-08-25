# s1000d-extractor

Outil de **migration de documentation legacy vers une structure XML S1000D**.
À partir d'un **PDF natif** ou d'un fichier **Word**, il extrait un **squelette
structurel S1000D** (sections, procédures, étapes, warnings/cautions/notes,
figures, listes, tableaux) pour amorcer une conversion vers Data Module.

L'idée clé : en S1000D, **le type d'élément dépend du contexte**, pas de la
forme. Une liste à puces devient `randomList` en zone descriptive mais
`proceduralStep` en procédure. L'outil classe donc le **contexte** (descriptif
vs procédural), propose le mapping, et **remonte les cas ambigus** (plusieurs
candidats + niveau de confiance) pour revue humaine.

## Architecture générique (3 couches qui varient indépendamment)

| Couche | Varie… | Traitement |
|---|---|---|
| Forme d'entrée (layout PDF, styles Word) | par **document** | absorbée dans un **modèle logique canonique (IR)** commun ([app/core/ir.py](backend/app/core/ir.py)) |
| Moteur de mapping (contexte × forme → élément) | **jamais** | écrit une fois ([app/core/resolver.py](backend/app/core/resolver.py)) |
| Cible (version S1000D + BREX) | par **projet** | chargée en données (XSD + BREX), pas en code |

C'est ce qui rend l'outil générique : **un nouveau document ne demande aucune
config** (l'adapter le ramène à l'IR), et **un nouveau projet ne demande pas de
code** (on fournit son BREX + la version S1000D, réutilisés sur tous ses
documents). On ne réécrit jamais le mapping par document.

Pipeline ([app/core/pipeline.py](backend/app/core/pipeline.py)) :

```
parse (PDF/DOCX) -> IR -> classification contexte (IA) -> segmentation forme
   -> resolution candidats -> serialisation XML -> validation XSD + BREX
```

Entrées : le document + la **version S1000D** (4.2 ou 5.0) + le **BREX projet**
(optionnel). Sortie streamée en SSE (`session -> progress -> done`).

## Ressources client (optionnelles)

Trois fichiers facultatifs peuvent être attachés à un document au moment du
chargement (onglet *Migration*). Sans eux, l'assistant fonctionne comme avant.

| Ressource | Formats | Effet |
|---|---|---|
| **DMRL** | `.xlsx`, `.xlsm`, `.csv`, `.json` | **pilote le découpage** : un DM par ligne de la DMRL (le niveau de titre est ignoré) et permet de générer la **PMC** |
| **CIR** | `.xml` | les références `{{CIR:ID}}`, `[CIR:ID]`, `<cirRef refId="ID"/>` sont remplacées par le contenu du repository |
| **Règles client** | `.json` | contraintes rédactionnelles (profondeur de titres, longueur, rubriques obligatoires…) vérifiées à la génération |

Routes : `POST /api/v1/documents/{id}/resources/{dmrl|cir|brex_rules}`,
`GET /api/v1/documents/{id}/dmrl`, `GET /api/v1/documents/{id}/pmc`.

**DMRL** — colonnes reconnues (insensible à la casse/aux accents) : `Arbo`,
`DMC`, `Titre`/`Title`, `Type`/`Nature`, `Info code`, `Tech name`, `Info name`.
Le type de DM est déduit du code information quand la colonne `Type` est vide
(`941*` → IPD, `2/3/5/6/7/8**` → procédural, sinon descriptif). Une entrée dont
le titre n'est pas retrouvé dans le document produit un **DM vide** — jamais une
suppression silencieuse ([app/core/dmrl.py](backend/app/core/dmrl.py),
[app/core/pmc.py](backend/app/core/pmc.py)).

**Templates de DM** ([backend/app/dm_templates/](backend/app/dm_templates/)) :
un JSON par type de DM décrit les rubriques attendues et les métadonnées par
défaut. À la génération, le contenu du DM est réparti dans ces rubriques, les
listes à puces sont converties en balisage, et toute rubrique obligatoire vide
remonte en anomalie ([app/core/dm_templates.py](backend/app/core/dm_templates.py)).

**Règles client** — clés supportées : `max_title_levels`, `max_title_length`,
`allowed_dm_types`, `forbidden_kinds`, `required_sections`, `max_list_depth`.
Une clé inconnue est signalée (severity `info`), jamais ignorée en silence
([app/core/brex_rules.py](backend/app/core/brex_rules.py)).

## Auth

**Palier** : 1 — local seul, bind `127.0.0.1`, pas d'authentification.

POC local-first stricte conforme à [`STANDARD_POC.md §3.5`](../../STANDARD_POC.md).

## Stack

| Couche | Choix |
|---|---|
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog |
| Parsing | PyMuPDF (PDF), python-docx (Word), lxml (XML + validation XSD) |
| LLM | Mistral via `httpx` (chat JSON pour la classification de contexte) |
| Frontend | React 18 + TS + Vite + Tailwind + i18next + `@internal/ui` ; bundle React buildé |
| Persistance | SQLite (`backend/data/s1000d-extractor.db`), Alembic |

## Démarrage rapide

Double-clic sur `start.bat` (Windows) ou `bash start.sh` (Unix). Backend sur
http://127.0.0.1:8004/ — le **bundle React buildé** (onglet *Migration*) est
servi depuis `frontend/dist/`. OpenAPI : `/api/v1/docs`.

```bash
cd apps/s1000d-extractor/backend
python -m venv .venv && .venv\Scripts\activate    # Unix : source .venv/bin/activate
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload --port 8004
```

Frontend (optionnel, nécessite Node) : `pnpm dev:s1000d-extractor`.

## Vérification end-to-end

```bash
# Upload (PDF ou DOCX) + version + hint
curl -F "file=@manual.pdf" -F "s1000d_issue=5.0" -F "context_hint=mixed" \
     http://127.0.0.1:8004/api/v1/documents          # -> {"id": "<ID>", ...}

# Extraction (SSE : session -> progress -> done)
curl -N -X POST http://127.0.0.1:8004/api/v1/documents/<ID>/extract

# XML S1000D
curl -o out.xml http://127.0.0.1:8004/api/v1/documents/<ID>/xml

# Override d'un noeud (revue humaine)
curl -X PATCH -H "Content-Type: application/json" -d '{"element":"proceduralStep"}' \
     http://127.0.0.1:8004/api/v1/documents/<ID>/nodes/<NODE_ID>

# BREX projet (reutilisable)
curl -F "file=@project.brex" -F "name=Projet A" -F "s1000d_issue=5.0" \
     http://127.0.0.1:8004/api/v1/brex

# Ressources client d'un document (DMRL / CIR / regles client)
curl -F "file=@DMRL.xlsx" http://127.0.0.1:8004/api/v1/documents/<ID>/resources/dmrl
curl -F "file=@cir.xml"   http://127.0.0.1:8004/api/v1/documents/<ID>/resources/cir
curl -F "file=@rules.json" http://127.0.0.1:8004/api/v1/documents/<ID>/resources/brex_rules

# PMC generee depuis la DMRL
curl -o pmc.xml http://127.0.0.1:8004/api/v1/documents/<ID>/pmc
```

Tests : `cd backend && pytest` (fixtures PDF/DOCX/BREX/DMRL/CIR synthétiques,
jamais de donnée utilisateur réelle).

## Écarts au standard

- **Nouvelles dépendances** vs `_template` : `PyMuPDF` (extraction PDF),
  `python-docx` (Word), `lxml` (sérialisation + validation XSD), `openpyxl`
  (lecture des DMRL Excel). Justifiées par le métier. Aucun SDK propriétaire,
  ni LangChain (règles 1 & 2 respectées).
- **`localStorage` pour le thème et la langue** (`ThemeToggleButton.tsx`,
  `i18n.ts`). Écart littéral à `rules/javascript.mdc` de l'AACF (« *No
  localStorage/sessionStorage* »), mais **HR1 est respecté** : HR1 vise l'état
  *authoritative ou persistant* (auth, données), pas une préférence
  d'affichage. Ce pattern est par ailleurs **imposé** par le standard interne
  ([`CLAUDE.md`](../../CLAUDE.md) règle #13). Aucun état métier ni jeton n'est
  stocké côté navigateur.
- **Squelette != Data Module valide.** La sortie est un squelette structurel
  best-effort. **DMC, SNS, applicabilité, sécurité et ICN ne sont PAS
  récupérables d'un PDF** et sont laissés en placeholders `<!-- TODO -->`. Une
  complétion humaine + une *conversion specification* projet restent
  nécessaires (pratique standard de l'industrie).
- **Entrée : PDF (natif OU scanné) + DOCX.** Un PDF à couche texte est lu
  directement (PyMuPDF). Un **PDF scanné** (sans couche texte) bascule
  automatiquement sur l'**OCR Mistral** (`/v1/ocr`, modèle `mistral-ocr-latest`)
  qui renvoie du markdown converti en blocs — l'inférence de titres repose alors
  sur le markdown, pas sur la police. Sans clé Mistral configurée, le scan est
  rejeté avec un message explicite (`OCR_UNAVAILABLE`). Pas de modèle vision en
  v1.
- **BREX = porte de validation, pas générateur.** Le choix d'élément vient du
  content-model S1000D + contexte ; le BREX contraint/valide en aval. Seul un
  **sous-ensemble pragmatique** des `structureObjectRule` est évalué
  (`objectPath` + `allowedObjectFlag`) ; la sémantique BREX complète (CIR,
  notation rules, XPath avancés) est hors scope.
- **Validation XSD = schémas non redistribués.** Les jeux XSD officiels S1000D
  (volumineux) ne sont pas dans le repo. Déposer ceux de l'Issue voulue dans
  `backend/app/s1000d_schemas/issue-4.2/` et `issue-5.0/` pour activer la
  validation XSD réelle ; absents, la validation XSD est signalée « non
  installée » (dégradation gracieuse) et le vocabulaire interne reste utilisé.
- **Document mixte -> un seul DM.** Un document mêlant descriptif et procédural
  produit un seul squelette du type dominant. Le découpage en plusieurs Data
  Modules (pratique S1000D) est laissé à l'humain.
- **IA optionnelle, dégradée.** Sans clé Mistral, la classification de contexte
  retombe sur l'heuristique (qualité moindre, jamais de crash).
- **Frontend React non build-vérifié dans cet environnement** (Node absent au
  moment du dev). Le bundle React doit être construit avec `pnpm build` avant
  distribution et validation end-to-end.