# ECM-rename — backend

FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog. Le workflow métier est porté par `/api/v1/ecm-rename` ; les tests créent des PDF et trackers synthétiques.

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

## Dépendances métier

- PyMuPDF lit le texte déjà présent dans les PDF ; aucun OCR n'est lancé.
- openpyxl lit les trackers `.xlsx` et `.xlsm` ; l'écriture ne remplace que la feuille ciblée et les plages de tableaux concernées, sans réécrire les autres éléments du classeur.
- Les fichiers ne sont écrits qu'après confirmation dans l'interface.

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
