# S1000d Extractor — backend

FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog. Squelette minimal qui démarre, expose `/api/v1/health` et passe le test pytest.

## Démarrage local

```bash
cd apps/<poc>/backend
python -m venv .venv
. .venv/Scripts/activate            # Windows
pip install -e ".[dev]"
cp .env.example .env
python -m app.db.migrations
pytest
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

`python -m app.db.migrations` upgrades both the normal and demo databases.

## Blocking Work And Streaming

Document, resource and BREX uploads, as well as batch DM validation, use
synchronous routes so FastAPI runs file reads and processing in its worker
thread pool rather than on the asyncio event loop. SSE routes remain
asynchronous and offload their processing with `asyncio.to_thread`.

## File And Illustration Reliability

- Graphic entity identifiers and filenames are validated before entering the
  internal DTD. Invalid names produce `GRAPHIC_NAME_INVALID` diagnostics.
  ZIP image conversions pass their filename map directly to the serializer;
  paragraph text is never rewritten.
- Uploads, generated XML, cut PDFs and extracted images are published through
  unique temporary files in the destination directory and `os.replace`.
  Unique names avoid collisions between concurrent writes and file formats.
  Final publications are serialized within the local process to avoid Windows
  sharing collisions; preparing and writing temporary files remains parallel.
- Document deletion and admin resets commit database changes before removing
  files. Cleanup failures produce structured warnings without undoing a
  successful database deletion.
- Illustration extraction uses a temporary directory and a separate IR copy.
  Only an error-free extraction replaces the previous images and IR links.
  Directory publication failures restore the previous directory.
- Expected extraction failures are logged with structured context and traceback.
  `illustration_errors` counts extraction errors, not unique source images.
  The count is persisted as a document diagnostic and displayed in French and
  English by the wizard, including after resuming it.

## À adapter dans un nouveau POC

- `pyproject.toml` : `name = "<poc>-backend"`
- `app/config.py` : `app_name`, `database_url` (path `data/<poc>.db`)
- `alembic.ini` : `sqlalchemy.url`
- `.env.example` : valeurs par défaut

## Layout

```
app/
├── main.py            # create_app() — middlewares + error handlers + routers
├── config.py          # Settings (pydantic-settings, CORS CSV→list)
├── schemas.py         # Pydantic I/O par endpoint
├── api/
│   └── health.py      # GET /api/v1/health
├── core/
│   ├── logging.py     # structlog JSON
│   ├── request_id.py  # uuid4 + structlog contextvars
│   └── errors.py      # AppError + 4 handlers → {code,message,detail,request_id}
└── db/
    └── session.py     # engine, Base(DeclarativeBase), get_db()
alembic/               # migrations (env.py + script.py.mako + versions/)
tests/                 # pytest (conftest force sqlite in-memory)
```
