# Catia Toolbox — backend

Backend local et déterministe : FastAPI + Pydantic v2 + SQLAlchemy 2 + Alembic + structlog. Il gère les nomenclatures, comparaisons, conversions Composer, optimisations XML, colorisations et renommages SMGXML.

## Démarrage local

```bash
cd apps/catia-toolbox/backend
python -m venv .venv
. .venv/Scripts/activate            # Windows
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
pytest
uvicorn app.main:app --reload --host 127.0.0.1 --port 8004
```

## Configuration

- Les variables de démarrage sont décrites dans `.env.example`.
- Les racines entrée/sortie, la licence Composer, le convertisseur et le profil XML sont enregistrés via `GET /api/v1/settings` et `POST /api/v1/settings`.
- `GET /api/v1/health` vérifie la connexion SQL et renvoie uniquement `status`, `version` et `db`.
- `httpx` est une dépendance de développement, utilisée par les tests HTTP.
- Les migrations historiques et les données existantes ne sont pas supprimées lors du nettoyage des modules retirés.

## Layout

```
app/
├── main.py            # create_app() — middlewares + error handlers + routers
├── config.py          # Settings (pydantic-settings, CORS CSV→list)
├── schemas.py         # Pydantic I/O par endpoint
├── api/
│   └── *.py           # routes des modules actifs, paramètres, administration
├── core/
│   ├── logging.py     # structlog JSON
│   ├── request_id.py  # uuid4 + structlog contextvars
│   └── errors.py      # AppError + 4 handlers → {code,message,detail,request_id}
└── db/
    └── session.py     # engine, Base(DeclarativeBase), get_db()
alembic/               # migrations (env.py + script.py.mako + versions/)
tests/                 # pytest : SQLite et stockage dans des dossiers temporaires
```

## Tests

```bash
python -m pytest -q
```

Les fixtures ne lisent pas les données utilisateur. La conversion réelle exige une installation locale de CATIA Composer et une licence valide ; les tests automatisés simulent cette intégration.
