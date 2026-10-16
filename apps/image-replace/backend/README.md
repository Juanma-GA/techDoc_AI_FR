# Image Replace — backend

FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog. Squelette minimal qui démarre, expose `/api/v1/health` et passe le test pytest.

## Démarrage local

```bash
cd apps/<poc>/backend
python -m venv .venv
. .venv/Scripts/activate            # Windows
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
pytest
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## À adapter dans un nouveau POC

- `pyproject.toml` : `name = "<poc>-backend"`
- `app/config.py` : `app_name`, `database_url` (path `data/<poc>.db`)
- `alembic.ini` : `sqlalchemy.url`
- `.env.example` : valeurs par défaut

## Workspace persistence

- `app/workspace_schemas.py` validates startup preferences and complete history snapshots.
- `api/workspace.py` persists the startup workbook and mapping without an image or selected part.
- `api/history.py` saves/restores complete image workspaces and serves lightweight paginated summaries.
- `services/workspace_storage.py` writes versioned files under `data/storage`, stores
  UUID references and SHA-256 metadata in SQLite, and checks file integrity on restoration.
- Migration `0002_workspaces` adds `excel_preset`, `image_history`, and `file_asset`.
- Backend tests use isolated SQLite databases and temporary synthetic-file storage.
  Never point test commands or migration checks at user data.
- `POST /api/v1/image-replace/export` converts the current image to an A4/300 dpi
  JPEG and returns the selected Excel ICN as the download filename, without suffixes.
  It uses the same filename sanitization as OCR and history. History caches the
  output name in snapshot metadata; older snapshots derive it from their analysis
  or selected workbook without loading image payloads for listing. No new DB migration.

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
