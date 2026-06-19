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

## Auth

**Palier** : 1 — local seul, bind `127.0.0.1`, pas d'authentification.

POC local-first stricte conforme à [`STANDARD_POC.md §3.5`](../../STANDARD_POC.md).

## Stack

| Couche | Choix |
|---|---|
| Backend | FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog |
| Parsing | PyMuPDF (PDF), python-docx (Word), lxml (XML + validation XSD) |
| LLM | Mistral via `httpx` (chat JSON pour la classification de contexte) |
| Frontend | React 18 + TS + Vite + Tailwind + i18next + `@internal/ui` ; preview HTML autonome (Node-free) |
| Persistance | SQLite (`backend/data/s1000d-extractor.db`), Alembic |

## Démarrage rapide

Double-clic sur `start.bat` (Windows) ou `bash start.sh` (Unix). Backend sur
http://127.0.0.1:8004/ — la **preview HTML autonome** (onglet *Migration*) est
servie quand `frontend/dist/` n'existe pas. OpenAPI : `/api/v1/docs`.

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
```

Tests : `cd backend && pytest` (20 tests, fixtures PDF/DOCX/BREX synthétiques).

## Écarts au standard

- **Nouvelles dépendances** vs `_template` : `PyMuPDF` (extraction PDF),
  `python-docx` (Word), `lxml` (sérialisation + validation XSD). Justifiées par
  le métier. Aucun SDK propriétaire, ni LangChain (règles 1 & 2 respectées).
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
  moment du dev). La **preview HTML autonome** (onglet *Migration*) est l'UI
  active et testée end-to-end ; le frontend React est fourni et aligné sur le
  template mais doit être `pnpm install` + `build` pour validation.
- **Taille `app/templates/preview.html`** > 200 lignes : page autonome
  HTML/CSS/JS non splittable sans bundler en mode preview (même justification
  que les autres POCs).