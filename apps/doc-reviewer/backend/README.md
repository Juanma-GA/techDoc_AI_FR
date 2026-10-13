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
not replace the DOCX working version. DOCX-to-DOC may lose layout fidelity.

## Conversions (Microsoft Word or LibreOffice)

Every conversion (`.doc`/`.docx` → PDF, `.doc` → `.docx`, `.docx` → `.doc`,
PDF → `.docx`/`.doc`) runs through one of two engines, chosen by
`OFFICE_CONVERTER`:

| Value | Engine |
|---|---|
| `auto` (default) | Microsoft Word, then LibreOffice if Word is absent or fails |
| `word` | Microsoft Word only (COM automation, macros forced off) |
| `libreoffice` | LibreOffice only (no Word needed). Found on PATH, in Program Files, as a portable copy, or at `DR_SOFFICE_PATH` |

Both engines are supported and tested; the installation guide exists in a Word
edition and a LibreOffice edition. `.docx` files produced by LibreOffice carry
no sensitivity label.

Where Microsoft Purview makes a sensitivity label mandatory, Word refuses to
save an unlabelled `.docx`. Set `WORD_SENSITIVITY_LABEL_ID` (label GUID, see
`.env.example`): it is applied to converted `.docx` files that carry no label;
an existing label is always kept. A conversion stuck longer than
`WORD_CONVERT_TIMEOUT_SECONDS` has its own WINWORD instance stopped.

Real-Word tests (opt-in, Windows with Word):

```bat
set DR_TEST_REAL_WORD=1
set WORD_SENSITIVITY_LABEL_ID=<label GUID>
python -m pytest tests\test_word_real.py -v
```

Real-LibreOffice tests (opt-in, LibreOffice installed or `DR_SOFFICE_PATH` set):

```bat
set DR_TEST_REAL_LIBREOFFICE=1
python -m pytest tests\test_libreoffice_real.py -v
```

Example:

```bash
curl -H "X-Requested-With: doc-reviewer" -F "file=@manual.docx" http://127.0.0.1:8003/api/v1/documents
curl http://127.0.0.1:8003/api/v1/documents/<id>/exports
curl -o manual_commente.pdf "http://127.0.0.1:8003/api/v1/documents/<id>/export?format=commented"
```

## Sécurité locale (sans authentification)

L'API n'a pas de login : elle est protégée par `app/core/request_guard.py`.

- Toute requête de modification (POST/PUT/PATCH/DELETE) exige l'en-tête
  `X-Requested-With: doc-reviewer` (le front l'envoie ; à ajouter dans les
  scripts et `curl`). Un en-tête `Origin` étranger est refusé.
- L'en-tête `Host` doit être `localhost`, `127.0.0.1`, `[::1]` ou figurer dans
  `ALLOWED_HOSTS` (anti DNS-rebinding).
- Une requête relayée par un proxy (`X-Forwarded-For`, `Forwarded`…) ou reçue
  sur une adresse non-bouclage est refusée (403 `EXPOSURE_NOT_ALLOWED`) tant que
  `BEHIND_AUTH_PROXY=true` n'atteste pas un reverse proxy authentifiant ; dans ce
  cas `ENCRYPTION_KEY` et des `CORS_ORIGINS` de production sont obligatoires.
- La clé Mistral n'est envoyée qu'aux URL de `MISTRAL_ALLOWED_BASE_URLS`
  (défaut `https://api.mistral.ai`) ; changer l'URL impose de ressaisir la clé.

## Démarrage local (dev)

```bash
cd apps/doc-reviewer/backend
python -m venv .venv
. .venv/Scripts/activate            # Windows : .venv\Scripts\activate.bat
pip install -e ".[dev]"
cp .env.example .env                # remplir MISTRAL_API_KEY si besoin
alembic upgrade head
pytest
uvicorn app.main:app --reload --port 8003
```

### Logs de developpement

Le niveau se regle avec `LOG_LEVEL` dans `.env` puis en redemarrant le backend.
Utiliser `DEBUG` pour activer aussi le mode debug FastAPI et afficher les appels
Mistral, leurs prompts et leurs reponses, ainsi que les durees HTTP. Les images
inline sont resumees par leur type et leur taille, et la cle API n'est jamais
ecrite dans les logs. Utiliser `INFO` au quotidien, `WARNING` ou `ERROR` pour
reduire le bruit, et `NONE` (ou `OFF`) pour couper les logs.

Test :

```bash
curl http://127.0.0.1:8003/api/v1/health
# → {"status":"ok","version":"0.1.0","db":"ok","llm":"not_configured"}
```

OpenAPI : `http://127.0.0.1:8003/api/v1/docs`.

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

## Client and rule bundles

`app/checks/active_client.json` selects one primary client bundle with
`bundle` and may add rule-only bundles with `rule_bundles`. The primary bundle
continues to supply the client mapping and operations; each additional bundle
adds catalogs and rules without replacing that mapping. For example, the
repository selects `thales_rules` as its primary bundle and `ste100_rules` as
an additional rule bundle. Rule bundles declare their catalog and `rules.py`
module in their own `manifest.json`.

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
Dockerfile                    # multi-stage, user 1001, healthcheck Python pur (port 8003)
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
