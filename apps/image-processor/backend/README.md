# Image Processor — backend

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
- `POST /api/v1/image-processor/export` converts the current image to an A4/300 dpi
  JPEG and returns the selected Excel ICN as the download filename, without suffixes.
  It uses the same filename sanitization as OCR and history. History caches the
  output name in snapshot metadata; older snapshots derive it from their analysis
  or selected workbook without loading image payloads for listing. No new DB migration.

## Replacement typography

- `text_geometry.py` converts OCR quadrilaterals to reading order, accounts for
  Paddle's tall-crop rotation and 0/180-degree class IDs, and aligns orientation
  metadata with recognition-filtered polygons. Narrow single glyphs are not
  considered vertical just because their boxes are tall.
- `replacement_typography.py` rectifies each selected reference, measures visible
  ink components rather than OCR padding, and excludes isolated noise/border lines.
  Heights within 10% or two pixels form a group; the mean of the largest group
  defines the common font height. Equal-frequency groups choose the smaller size.
- `replacement_rendering.py` uses regular Arial (Pillow fallback), preserves detected
  rotations and centers visible ink. Angles within five degrees of an axis snap
  to it. Only replacements wider than their reading-direction region shrink.
- Text is rendered after A4 layout. Optional `replacement_font_size` is validated
  in OCR forms and persisted analysis, so reruns/history reuse the same A4 size.
  Missing ink with no existing size returns an explicit 422 rather than inventing one.
- `PP-LCNet_x1_0_textline_ori` runs locally and may download about 6.5 MB on first use.
  `ocr_orientation_ms` isolates its inference time; automated tests simulate the model and
  never download weights or read user files.
- Before importing Paddle, the app defaults `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK`
  to `True` and `PADDLE_PDX_MODEL_SOURCE` to `bos`. This skips the one-second
  host availability probes, not TLS verification, and uses the official direct
  download first. Explicit process environment values remain unchanged.
  Internet access is still required for uncached models; orientation is never
  silently disabled when a model cannot be downloaded.
- Orientation uses `textline_orientation_batch_size=1`: the installed PaddleX
  classifier exposes batch-wide class IDs in individual results, while its OCR
  pipeline reads the first ID. Single-line batches preserve each line's direction.
- Manual validation downloaded the official model and verified local inference on
  synthetic upright/180-degree text crops with single-line batches. No user files
  were used; this is a functionality smoke test, not a performance benchmark.

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
