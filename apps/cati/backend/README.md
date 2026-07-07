# Cati — backend

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
