# PDF Reviewer — backend

FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog + PyMuPDF.

## Démarrage local (dev)

```bash
cd apps/pdf-reviewer/backend
python -m venv .venv
. .venv/Scripts/activate            # Windows : .venv\Scripts\activate.bat
pip install -e ".[dev]"
cp .env.example .env                # remplir MISTRAL_API_KEY si besoin
alembic upgrade head
pytest
uvicorn app.main:app --reload --port 8001
```

Test :

```bash
curl http://127.0.0.1:8001/api/v1/health
# → {"status":"ok","version":"0.1.0","db":"ok","llm":"not_configured"}
```

OpenAPI : `http://127.0.0.1:8001/api/v1/docs`.

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
Dockerfile                    # multi-stage, user 1001, healthcheck Python pur (port 8001)
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
