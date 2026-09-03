# Doc Reviewer — backend

FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog + PyMuPDF.

## Document contract

The upload extension selects the working format automatically: `.pdf` uses the
PDF pipeline, `.docx` uses the native DOCX pipeline, and legacy `.doc` is kept
as the original and converted to a DOCX working copy. Analysis only persists
suggestions; corrections require an explicit suggestion application.

`GET /api/v1/documents/{id}/exports` lists the outputs currently compatible
with the source, working format, correction state, and installed converters.
`GET /api/v1/documents/{id}/export?format=original|corrected|pdf|docx|doc`
downloads an explicit output. `?format=commented` produces the commented PDF
without applying corrections. For DOCX, this renders a temporary PDF and does
not replace the DOCX working version. DOCX-to-DOC is only available when
LibreOffice is installed and may lose layout fidelity.

The legacy `word_mode=pdf|docx` upload query is accepted for existing clients,
but new clients must omit it and rely on automatic selection.

Example:

```bash
curl -F "file=@manual.docx" http://127.0.0.1:8008/api/v1/documents
curl http://127.0.0.1:8008/api/v1/documents/<id>/exports
curl -o manual_commente.pdf "http://127.0.0.1:8008/api/v1/documents/<id>/export?format=commented"
```

## Démarrage local (dev)

```bash
cd apps/doc-reviewer/backend
python -m venv .venv
. .venv/Scripts/activate            # Windows : .venv\Scripts\activate.bat
pip install -e ".[dev]"
cp .env.example .env                # remplir MISTRAL_API_KEY si besoin
alembic upgrade head
pytest
uvicorn app.main:app --reload --port 8008
```

Test :

```bash
curl http://127.0.0.1:8008/api/v1/health
# → {"status":"ok","version":"0.1.0","db":"ok","llm":"not_configured"}
```

OpenAPI : `http://127.0.0.1:8008/api/v1/docs`.

## Verification manuelle

Le backend doit être lancé avant les tests. Le fichier de lancement sans
frontend est `_run_no_front.bat` à la racine de l'application, et non
`run_no_front.bat`.

Depuis `backend/`, le parcours manuel complet hors LLM est :

```bat
tests\backend_only_tests\run_manual_verification.bat C:\docs\manual.pdf
```

Le programme vérifie `/health`, exécute les scripts personnels `01` (upload),
`04` (format automatique et exports), puis `02` (analyse SSE déterministe).
Les réponses, événements SSE et artefacts restent dans
`tests/backend_only_tests/outputs/`. Pour tester la checklist avec le vrai LLM,
configurer d'abord Mistral dans l'application puis lancer :

```bat
tests\backend_only_tests\run_manual_verification.bat C:\docs\manual.docx --checklist C:\docs\checklist.xlsx --run-llm
```

Le runner n'envoie aucune clé API et n'utilise aucun mock.

## Layout

```
app/
├── main.py                   # create_app() — middlewares + error handlers + routers
├── config.py                 # Settings (pydantic-settings, CORS CSV→list)
├── api/
│   ├── health.py             # GET /api/v1/health
│   ├── documents.py          # CRUD documents PDF
│   ├── analyze.py            # POST /analyze (SSE streaming)
│   ├── suggestions.py        # CRUD suggestions
│   ├── rules.py              # règles éditables (S1000D / custom / units)
│   ├── preview.py            # rendu PDF côté serveur
│   └── settings.py
├── core/
│   ├── logging.py            # structlog JSON
│   ├── request_id.py         # uuid4 + structlog contextvars
│   ├── errors.py             # AppError + handlers → {code,message,detail,request_id}
│   ├── mistral_settings.py   # config LLM
│   ├── llm_suggester.py      # httpx async + SSE
│   ├── pdf_editor.py         # PyMuPDF in-place edit
│   ├── pdf_versioning.py
│   ├── rules_engine.py
│   └── units_detector.py
├── checks/                   # s1000d_checks, units_check, custom_rules
├── parsers/                  # pdf_parser
├── db/                       # session.py, models.py, seed.py
└── templates/                # preview.html
alembic/                      # migrations
tests/                        # pytest (conftest force sqlite in-memory)
Dockerfile                    # multi-stage, user 1001, healthcheck Python pur (port 8008)
```

## Format d'erreur

Toutes les erreurs renvoient :

```json
{
  "code": "DOCUMENT_NOT_FOUND",
  "message": "Document introuvable",
  "detail": null,
  "request_id": "8c4f…"
}
```

Détails dans [`docs/adr/0003-error-format.md`](../../../docs/adr/0003-error-format.md).
