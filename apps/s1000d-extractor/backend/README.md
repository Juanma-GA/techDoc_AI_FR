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

## Performance And Read-Only Downloads

- PDF parsing retains table geometry and passes it to illustration extraction.
  Both stages use the same selected source, with an explicit page-set check;
  table detection is not repeated.
- Reference indexes cache constrained DM content and its constraint report.
  IR fingerprints invalidate changed content. Cross-DM inline references are
  finalized after all target IDs are known; serialization reuses the content
  and constrains only the remaining document structure.
- Official XMLSchema objects are compiled once per process. Each schema has
  its own lock covering validation and error-log extraction. The schema-stem
  mapping is shared. Generation uses `SELECTABLE_ISSUES` (4.1/4.2), not the
  validation-only Issue 5.0 included in `SUPPORTED_ISSUES`.
- Heavy document JSON columns load only on explicit access. No migration is
  needed. The demo-mode switch is cached after a successful commit; this cache
  assumes the launcher's single-process configuration.
- XML GET routes do not write files or commit database changes. Versioned
  fingerprints cover IR, XML integrity, resources, Issue and procedural review.
  Old or stale wizard XML can be rendered in memory without changing storage.
  Responses include an ETag.
- `POST /api/v1/documents/{id}/wizard/validate` accepts
  `{"dm_ids": ["..."]}` or `{"dm_ids": null}` and validates selected/all DMs
  server-side. The Validation page no longer downloads and re-uploads them.
- Images use private HTTP caching. PDF previews are cached by source timestamp,
  size and page, and removed with document deletion or admin reset.
- ZIP files are written to temporary disk files and streamed with cleanup after
  the response. Original images are copied from paths; dimensions come from
  headers, and conversions are processed one image at a time.
- Extraction, wizard startup and PMC streaming share one threaded SSE helper.
  Disconnects signal cooperative cancellation at progress checkpoints; running
  native calls cannot be forcibly interrupted. Cancellation is not persisted as
  an extraction failure. The frontend shares one SSE parser, handles multi-line
  data and incomplete final blocks, and aborts wizard streams on unmount or a
  document change.

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
