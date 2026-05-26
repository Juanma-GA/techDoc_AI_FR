# doc-writer — backend

FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog. RAG (chunking + embeddings Mistral via httpx + cosine similarity numpy) avec streaming SSE.

## Démarrage local

```bash
cd apps/doc-writer/backend
python -m venv .venv
. .venv/Scripts/activate            # Windows
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
pytest
uvicorn app.main:app --reload --host 127.0.0.1 --port 8002
```

Ou simplement, depuis la racine de l'app : `start.bat` / `start.sh`.

## Layout

```
app/
├── main.py            # create_app() — middlewares + error handlers + routers
├── config.py          # Settings (pydantic-settings, CORS CSV→list)
├── schemas.py         # Pydantic I/O par endpoint
├── api/
│   ├── health.py      # GET /api/v1/health
│   ├── documents.py   # CRUD documents + upload multipart
│   ├── sessions.py    # sessions + SSE /ask
│   └── settings.py    # config Mistral + test connexion
├── core/
│   ├── logging.py     # structlog JSON
│   ├── request_id.py  # uuid4 + structlog contextvars
│   ├── errors.py      # AppError + 4 handlers → {code,message,detail,request_id}
│   ├── security.py    # validation uploads + safe_storage_join
│   ├── versioning.py  # sha256
│   ├── mistral_client.py  # httpx async chat_stream + sync embed/list_models
│   ├── indexer.py     # chunk_text + index_document + search_similar (cosine)
│   └── writer_engine.py   # system prompts + build_messages + stream_answer
├── parsers/
│   ├── pdf_parser.py  # PyMuPDF
│   ├── docx_parser.py # python-docx
│   ├── xlsx_parser.py # openpyxl
│   └── txt_parser.py  # UTF-8 / latin-1 fallback (.txt / .md)
└── db/
    ├── session.py     # engine, Base, get_db()
    └── models.py      # Document, DocumentChunk, Session, Message, AppConfig
alembic/               # migrations (0001_initial.py)
tests/                 # pytest (conftest crée tables via Base.metadata)
```

## Endpoints

| Méthode | Chemin | Description |
|---|---|---|
| GET | `/api/v1/health` | liveness |
| GET | `/api/v1/documents` | liste documents |
| POST | `/api/v1/documents` | upload multipart (PDF/DOCX/XLSX/TXT/MD) |
| DELETE | `/api/v1/documents/{id}` | supprime document + chunks |
| GET | `/api/v1/sessions` | liste sessions |
| POST | `/api/v1/sessions` | crée une session avec scope optionnel |
| DELETE | `/api/v1/sessions/{id}` | supprime session + messages |
| GET | `/api/v1/sessions/{id}/messages` | historique |
| POST | `/api/v1/sessions/{id}/ask` | SSE : event=session → token* → done/error |
| GET / POST | `/api/v1/settings` | config Mistral runtime |
| POST | `/api/v1/settings/test` | teste la connexion (list_models) |
