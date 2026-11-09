# Application Inventory

This inventory is generated from [`scripts/apps.json`](../../scripts/apps.json).
The registry is the single source of truth for application identity, backend,
profiles, desktop capability, and target default ports.

## Target Ports and Profiles

Every app starts with its registered default and selects the next free port
when necessary. Windows, Unix, development commands, and API tooling must use
the same registered value.

<!-- APP_REGISTRY_START -->
| Application | Backend | Profiles | Target default port | Desktop |
|---|---|---|---:|---:|
| [_template](../../framework/apps/_template/README.md) | fastapi | `local-first` | 8000 | Yes |
| [corpus-agent](../../apps/corpus-agent/README.md) | fastapi | `local-first`, `llm`, `files` | 8001 | No |
| [doc-writer](../../apps/doc-writer/README.md) | fastapi | `local-first`, `llm`, `files` | 8002 | No |
| [doc-reviewer](../../apps/doc-reviewer/README.md) | fastapi | `local-first`, `llm`, `files` | 8003 | No |
| [catia-toolbox](../../apps/catia-toolbox/README.md) | fastapi | `local-first`, `files` | 8004 | Yes |
| [ocr-vision](../../apps/ocr-vision/README.md) | fastapi | `local-first`, `llm`, `files` | 8005 | No |
| [s1000d-extractor](../../apps/s1000d-extractor/README.md) | fastapi | `local-first`, `files` | 8006 | No |
| [ecm-automation](../../apps/ecm-automation/README.md) | fastapi | `local-first` | 8009 | No |
| [flowchart-generator](../../apps/flowchart-generator/README.md) | fastapi | `local-first`, `llm`, `files` | 8010 | No |
| [pdf-toolkit](../../apps/pdf-toolkit/README.md) | go | `local-first`, `files` | 8085 | Yes |
<!-- APP_REGISTRY_END -->

## Exception hors registre

[`image-processor`](../../apps/image-processor/README.md) reste une application
utilisable, mais n'est volontairement pas dans `scripts/apps.json`. Son
`pnpm dev:image-processor` personnalisé démarre l'API, LaMa dans son
environnement Python séparé et Vite. Le synchroniseur du registre ne sait
générer que le lanceur FastAPI + Vite standard : l'y ajouter remplacerait ce
script et omettrait LaMa. Utilise `pnpm dev:image-processor` pour le
développement ou `apps\image-processor\start.bat` pour le lancement local.

## Adding an App

Use `node scripts/new_poc.mjs <slug> [port] [--profile llm] [--profile files] [--desktop]`.
The default profile is `local-first`; LLM and file-handling capabilities must be
selected explicitly. `production` is outside the local POC scope.

The scaffold updates the registry and synchronized documentation/commands.
Application-specific behavior remains documented in each app README. Run the
app checks and `bash scripts/check_standard.sh` after scaffolding.
