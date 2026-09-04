# doc-reviewer

> Preserved technical reference. Use [`apps/doc-reviewer/README.md`](../../../apps/doc-reviewer/README.md) for current onboarding and maturity status.

Relecteur de documents **détection-first** : ingère des **PDF, .docx et .doc**
(et des `.zip` en contenant), y détecte des anomalies selon des règles
configurables, et produit un **PDF commenté** que le rédacteur utilise pour
corriger son document Word. La correction dans le PDF (Accept / Edit / Reject)
reste possible mais **secondaire**.

## Ingestion : tout est ramené à un PDF fidèle

Pour éviter les fausses anomalies dues à une conversion `.doc → .docx` lossy,
**tout format est révisé via un PDF fidèle** :

- `.pdf` → utilisé tel quel (zéro conversion) ;
- `.doc` / `.docx` → **PDF exact** via Word COM `ExportAsFixedFormat` (rendu Word,
  **non** bloqué par la stratégie Office contrairement au SaveAs `.docx`), repli
  LibreOffice `--convert-to pdf`. Override du chemin : `DR_SOFFICE_PATH`.

La détection tourne ensuite sur le PDF (spans PyMuPDF), identique pour tous les
formats. Un `.docx` template-safe éditable par le rédacteur est un **besoin
distinct**, hors périmètre de l'outil (cf. section Écarts).

## Détection : règles

Les règles combinent :

- **Catalogues built-in multi-normes** : ASD-STE100 (style rédactionnel),
  MAT10000 (v1), ATA 100 (rev 38). Chaque norme expose des règles
  textuelles (terminologie, casse, chapitrage) **et** structurelles
  (champ requis, section requise, format d'étape, valeur énumérée)
  vérifiables sur le **rendu PDF**. Les normes purement XML/gestion de
  données (S1000D, ATA iSpec 2200, S2000M) sont hors périmètre : leurs
  règles portaient sur des codes/champs (DMC, NSN, CAGE, SMR, QPA…) qui
  n'existent que dans la source XML/SGML. Les règles de style S1000D/STE
  restent disponibles via le moteur transverse intégré.
- **Normes & versions custom** : créer ses propres normes et règles
  via `/standards` puis les attacher à un document à l'upload.
- **Règles custom transverses** (regex / terme exact, CRUD
  utilisateur) qui s'exécutent quelle que soit la norme cible.
- **Checklist Excel importée** (`Topic | Check`) → règles `llm_nl` en langage
  naturel **jugées par le LLM** sur le texte du PDF. Importées **désactivées**
  (curation), activables une à une ou en masse (`/rules/validate-all`).
- **Conversions d'unités** (cm/mm/m ↔ in/ft, kg ↔ lb) auto-detect.

## Feedback de rejet + mémoire (façon corpus-agent)

Au rejet d'une anomalie, le relecteur saisit un **motif libre** (`Suggestion.feedback`).
La **signature** `(rule_code, original_text)` des anomalies rejetées est mémorisée :
à la ré-analyse, une re-détection identique est **supprimée** (`summary.suppressed_rejected`)
et son motif conservé. Un faux positif récurrent ne réapparaît plus.

## Livrable : PDF commenté

`GET /documents/{id}/commented.pdf` renvoie le PDF fidèle + les anomalies retenues
(non rejetées) estampillées en **annotations PyMuPDF** + une page-sommaire. C'est le
document sur lequel le rédacteur s'appuie pour corriger son Word puis assembler le PDF final.

POC **local-first** (SQLite + stockage disque, pas de Docker à ce stade).

## Auth

**Palier** : 1 — local seul, bind 127.0.0.1, pas d'authentification.

POC local-first stricte conforme à [`STANDARD_POC.md §3.5`](../../../STANDARD_POC.md). Aucun déploiement dans le périmètre du standard.

## LLM & Graceful Degradation

**Checklist NLP Rules** (`llm_nl`) are evaluated by Mistral. When LLM is **OFF** or Mistral key is missing, these rules produce **no findings** (HTTP 200, graceful degradation per HR7).

**Fallback** (HR4/HR7 Compliance): For increased transparency when LLM is disabled, `doc-reviewer` includes ~10 regex-based fallback patterns that detect common writing issues:
- Passive voice (`was written`)
- Intensifiers (`very`, `extremely`)
- Multiple punctuation (`!!`, `...`)
- ALL CAPS words
- Weak words (`basically`, `stuff`)
- Contractions (`don't`, `can't`)
- Vague quantifiers (`many`, `several`)

The built-in **deterministic catalog** (ASD-STE100, MAT10000, ATA 100) and **unit conversions** remain fully functional regardless of LLM state. Only checklist NLP findings are affected.

---

## Démarrage rapide

### Backend (port 8008)

```bash
cd apps/doc-reviewer/backend
python -m venv .venv && source .venv/bin/activate   # ou .venv\Scripts\activate sous Windows
pip install -e .[dev]
alembic upgrade head
uvicorn app.main:app --reload --port 8008
```

### Frontend (port 5173)

```bash
pnpm install                                   # depuis la racine du monorepo
pnpm --filter @apps/doc-reviewer-frontend dev
```

Le proxy Vite redirige `/api` → `http://localhost:8008`.

### Tests

```bash
# Backend
cd apps/doc-reviewer/backend && pytest

# Frontend
pnpm --filter @apps/doc-reviewer-frontend test
pnpm --filter @apps/doc-reviewer-frontend test:e2e   # Playwright
```

---

## Vérification end-to-end

```bash
# Upload
curl -F "file=@./backend/tests/fixtures/sample.pdf" \
     "http://localhost:8008/api/v1/documents?target=imperial"
# → {"id":"<DOC_ID>", "current_version":0, ...}

# Analyse (SSE)
curl -N -X POST "http://localhost:8008/api/v1/documents/<DOC_ID>/analyze"

# Liste suggestions
curl "http://localhost:8008/api/v1/documents/<DOC_ID>/suggestions"

# Apply
curl -X PATCH -d '{"status":"accepted"}' -H "Content-Type: application/json" \
     "http://localhost:8008/api/v1/suggestions/<SUG_ID>"
curl -X POST "http://localhost:8008/api/v1/suggestions/<SUG_ID>/apply"

# Export PDF modifié
curl -o final.pdf "http://localhost:8008/api/v1/documents/<DOC_ID>/export"
```

---

## Écarts au standard

Spécifiques à doc-reviewer :

- **Conversion `.doc/.docx` → PDF** : nécessite Word (automation COM) OU
  LibreOffice sur le poste. Sans ni l'un ni l'autre, l'upload d'un `.doc/.docx`
  renvoie `DOC_CONVERT_UNAVAILABLE` (les `.pdf` restent traités). La fidélité
  est celle d'**une** conversion (stockée comme artefact canonique, jamais
  re-convertie).
- **Conversion `.doc → .docx` template-safe** : **hors périmètre** de l'outil.
  Sur ce poste Word est bloqué par GPO pour le SaveAs `.docx` et LibreOffice
  altère le template — aucun `.docx` fidèle n'est produisible ici. Le rédacteur
  édite son Word directement / via un poste où Word peut « Enregistrer sous .docx ».
- **Règles checklist `llm_nl`** : jugées par le LLM sur le **texte de page
  entière** (pas de zone-scoping footer/header). Les anomalies d'**absence**
  (sans `original_text`) n'ont pas de bbox → visibles seulement dans la
  page-sommaire du PDF commenté, pas surlignées. Lignes « manuelles » (visuel)
  **ignorées** à l'import.
- **Écart règle #6** : plus de repli déterministe pour les règles `llm_nl` —
  LLM OFF ou clé Mistral absente ⇒ ces règles ne produisent aucune anomalie
  (les catalogues built-in + regex custom + unités restent déterministes).
- **Correction PDF-only (secondaire)** : les findings sont ancrés sur des spans
  PDF, sans inverse fiable vers les runs Word. « Corriger » édite le PDF, pas le
  `.docx` source — cohérent avec la posture détection-first.

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

- **Skin CSS au lieu de `@internal/ui` (règles #3/#4)** : pour un rendu
  visuellement cohérent avec les POCs récents (corpus-agent / doc-writer),
  le React réutilise un CSS sur-mesure `frontend/src/styles/preview-skin.css`
  (classes `.card/.btn/.kpi/.badge/.sev/.reviewer-*`...) plutôt que les
  composants `@internal/ui`. Les variables CSS reprennent les valeurs de
  `design-tokens/tokens.json` (`:root` clair, `.dark` sombre) — donc zéro hex
  « magique ». Les primitives riches (`Dialog`) viennent quand même de
  `@internal/ui`. Plan de retour : migrer les classes skin vers `@internal/ui`
  si l'app est pérennisée.

Toute extension hors de ce périmètre doit être documentée ici.

---

## Architecture

```
apps/doc-reviewer/
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
