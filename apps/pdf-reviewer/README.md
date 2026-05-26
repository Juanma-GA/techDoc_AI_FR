# pdf-reviewer

Application interne pour relire un PDF technique, y détecter des
anomalies selon des règles configurables, proposer des corrections
(Accept / Edit / Reject) et **les appliquer directement dans le PDF
binaire**.

Les règles combinent :

- **Catalogues built-in multi-normes** : S1000D (5.0 / 6.0), MAT10000
  (v1), S2000M (issue 7), ATA100 (rev 38), ATA iSpec 2200 (2018-1).
  Chaque norme expose ses règles textuelles (terminologie, formats DMC
  / ATA) **et** structurelles (champ requis, section requise,
  cohérence inter-champs, format d'étape, valeur énumérée).
- **Normes & versions custom** : créer ses propres normes et règles
  via `/standards` puis les attacher à un document à l'upload.
- **Règles custom transverses** (regex / terme exact, CRUD
  utilisateur) qui s'exécutent quelle que soit la norme cible.
- **Conversions d'unités** (cm/mm/m ↔ in/ft, kg ↔ lb) auto-detect.

POC **local-first** (SQLite + stockage disque, pas de Docker à ce stade).

## Auth

**Palier** : 1 — local seul, bind 127.0.0.1, pas d'authentification.

POC local-first stricte conforme à [`STANDARD_POC.md §3.5`](../../STANDARD_POC.md). Aucun déploiement dans le périmètre du standard.

---

## Démarrage rapide

### Backend (port 8001)

```bash
cd apps/pdf-reviewer/backend
python -m venv .venv && source .venv/bin/activate   # ou .venv\Scripts\activate sous Windows
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

### Frontend (port 5173)

```bash
pnpm install                                   # depuis la racine du monorepo
pnpm --filter @apps/pdf-reviewer-frontend dev
```

Le proxy Vite redirige `/api` → `http://localhost:8001`.

### Tests

```bash
# Backend
cd apps/pdf-reviewer/backend && pytest

# Frontend
pnpm --filter @apps/pdf-reviewer-frontend test
pnpm --filter @apps/pdf-reviewer-frontend test:e2e   # Playwright
```

---

## Vérification end-to-end

```bash
# Upload
curl -F "file=@./backend/tests/fixtures/sample.pdf" \
     "http://localhost:8001/api/v1/documents?target=imperial"
# → {"id":"<DOC_ID>", "current_version":0, ...}

# Analyse (SSE)
curl -N -X POST "http://localhost:8001/api/v1/documents/<DOC_ID>/analyze"

# Liste suggestions
curl "http://localhost:8001/api/v1/documents/<DOC_ID>/suggestions"

# Apply
curl -X PATCH -d '{"status":"accepted"}' -H "Content-Type: application/json" \
     "http://localhost:8001/api/v1/suggestions/<SUG_ID>"
curl -X POST "http://localhost:8001/api/v1/suggestions/<SUG_ID>/apply"

# Export PDF modifié
curl -o final.pdf "http://localhost:8001/api/v1/documents/<DOC_ID>/export"
```

---

## Écarts au standard

L'édition PDF binaire est intrinsèquement fragile. Le POC accepte ces
limitations explicitement :

- **Kerning / ligatures / justification** : non préservés (best-effort
  redact + insert via PyMuPDF). Le rendu peut visuellement se dégrader
  sur les paragraphes denses.
- **Polices manquantes** : fallback `Helvetica` (`helv`) si la police
  d'origine n'est pas embarquable, ce qui change légèrement
  l'apparence.
- **PDFs signés numériquement** : refusés à l'upload (`PDF_HAS_SIGNATURE`)
  car toute modification invalide la signature.
- **PDFs scannés (raster sans couche texte)** : aucune suggestion ne
  peut être posée — pas d'OCR dans ce POC.
- **PDF/A** : la conformité n'est pas garantie après édition. À valider
  manuellement si besoin.
- **Concurrent edits** : verrou applicatif simple via
  `Suggestion.status = applied` (POC mono-utilisateur).
- **Taille `app/templates/preview.html`** ~480 lignes (CLAUDE.md
  recommande < 200 lignes par fichier). Justifié comme pour
  `apps/ftm/.../preview.html` (1543 lignes) : page autonome
  HTML/CSS/JS qui ne peut pas être splittée sans bundler en mode
  preview. Tokens CSS injectés au request-time depuis
  `design-tokens/tokens.json`, donc zéro hex en dur.

Toute extension hors de ce périmètre doit être documentée ici.

---

## Architecture

```
apps/pdf-reviewer/
├── backend/                    # FastAPI + PyMuPDF + SQLite
│   ├── app/
│   │   ├── api/                # /health, /documents, /analyze, /suggestions, /rules
│   │   ├── core/               # errors, logging, request_id, security, pdf_editor, pdf_versioning, units_detector, rules_engine
│   │   ├── checks/             # s1000d_checks, custom_rules, units_check
│   │   ├── parsers/            # pdf_parser (PyMuPDF, span+bbox)
│   │   ├── db/                 # session + models (Document, Suggestion, Rule, EditHistory, AnalysisRun)
│   │   ├── schemas.py          # Pydantic v2 I/O
│   │   ├── main.py             # FastAPI factory
│   │   └── config.py
│   ├── alembic/                # migrations Alembic
│   └── tests/                  # pytest + httpx TestClient
└── frontend/                   # React 18 + Vite + react-pdf v9
    └── src/
        ├── routes/             # DocumentsList, DocumentReviewer, Rules, Settings
        ├── components/         # reviewer/PdfViewer, HighlightLayer, SuggestionPanel, …
        ├── hooks/              # useDocuments, useSuggestions, useApplySuggestion, useAnalyze
        ├── stores/             # viewerStore (transient), filtersStore (persisté)
        ├── lib/                # api.ts, bbox.ts, diff.ts, units.ts, pdfWorker
        ├── types/domain.ts
        ├── locales/{fr,en}.json
        ├── App.tsx, main.tsx, i18n.ts, index.css
```

Le pipeline `analyze` :

```
parse_pdf  →  s1000d_checks
                custom_rules        →  materialize  →  Suggestion (DB)  →  SSE event
                units_check
```

L'application d'une suggestion :

```
apply  →  bump_version (vN → v{N+1}.pdf)  →  pdf_editor.apply_patch  →  EditHistory
```

V0 reste immuable. Le rollback (route `/documents/{id}/rollback` ou
`/suggestions/{id}/revert`) repointe `current_version` sans toucher aux
snapshots.
