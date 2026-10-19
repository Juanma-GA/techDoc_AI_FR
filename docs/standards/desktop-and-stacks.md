# Backend stacks and optional desktop applications

## Shared contract, backend-specific tooling

The monorepo shares React/Vite, strict TypeScript, `@internal/ui`, design tokens,
FR/EN, themes, local-only binding and data-safety rules. FastAPI remains the
default scaffold, not a requirement to rewrite an existing backend.

An app documents its runtime, framework, API differences and persistence in its
README. Go apps use Go builds/tests; FastAPI apps use Python/pytest/Alembic.
Do not add Python to an app solely to satisfy a launcher or packaging convention.
Other stacks need an explicitly implemented launcher, packager and checker adapter.

| App type | Backend validation | Distribution |
|---|---|---|
| FastAPI default | pytest | Existing Python-embed ZIP packager |
| PDF Toolkit (Go/Gin) | `go test ./...` | Node packager, bundled Windows x64 Go + sources/vendor + built UI |
| Optional Tauri | cargo check/test and native smoke | Native installer, web mode retained |

The shared build helper watches the app source/configuration, public assets,
shared UI, design tokens and root lockfile. It only installs frontend dependencies
when `frontend/node_modules` is absent. Web packaging may restore a previously
valid bundle on build failure, with an explicit warning. Native preparation fails
instead of quietly shipping a stale bundle.

## Create a web app or a web + desktop app

From the repository root:

```powershell
node scripts\new_poc.mjs my-app 8010 --dry-run
node scripts\new_poc.mjs my-app 8010
node scripts\new_poc.mjs my-desktop-app 8011 --desktop
```

The Bash wrapper `bash scripts/new_poc.sh <slug> [port] [--desktop]` remains
available. Generation itself uses Node, not Python. Existing positional arguments
remain compatible. Install workspace dependencies afterwards, complete the README,
then run the local standard and app-specific checks; generation is not validation.
The Bash wrapper also runs the local checker automatically after creation.

The canonical optional desktop assets live in `apps/_template/desktop/`. The
generator copies them into the new frontend only with `--desktop`, substitutes
the app identity and adds Tauri CLI/scripts. Web-only apps do not gain Rust,
Tauri dependencies, runtime resources or desktop prerequisites.

PDF Toolkit's web ZIP bundles the installed Windows x64 Go distribution with its
license/version, the app's allowlisted sources, vendored dependencies and built
frontend. First launch compiles locally offline; later launches reuse the binary
unless inputs change. No Go, Node or Python installation is needed on the recipient
PC. Go still creates an executable, and corporate endpoint approval may be required.
No launcher disables security protection or promises that compilation avoids a block.
The Tauri distribution remains a separate native executable/installer.

The default app backend remains FastAPI. This option does not create a second
backend or convert an app into Rust: Tauri starts the same local HTTP backend and
navigates to its React interface. PDF Toolkit keeps its existing Go-native adapter.

## Desktop adapter contract

`frontend/desktop.json` declares:

- `adapter`: `fastapi` or `command`;
- `dev` and `build`: executable and working directory;
- `args`: backend arguments, with `{port}` replaced by a free localhost port;
- `bootstrap`: optional argument arrays executed with that same executable;
- for `command`, `prepare.dev` / `prepare.build`: command arrays preparing the backend.

Developer paths resolve from the frontend. Packaged paths resolve from Tauri's
resource directory. A custom adapter must stage its own compiled runtime in
`frontend/src-tauri/runtime/` and expose `GET /api/v1/health`. Launch the actual
server executable, not a detached shell or a process manager, so closing Tauri
stops the managed process. Do not enable uvicorn reload in desktop mode.

The native shell chooses a loopback port, runs bootstrap, waits for HTTP 200 on
health and only then navigates. Startup failures appear in the startup window and
stderr. Closing the window cancels startup and terminates/reaps the managed child.
No remote-page IPC permissions are granted by the scaffold.

## Default FastAPI desktop adapter

Currently supported for **Windows x64**. Requires Rust stable, Visual Studio C++
build tools, WebView2 and Node/pnpm. Development additionally uses Python 3.11+.

```powershell
pnpm desktop:dev:my-desktop-app
pnpm desktop:build:my-desktop-app
```

Or run `package.bat desktop` inside the generated app; this puts Cargo output in
`apps/<slug>/dist/tauri/`. Direct Tauri CLI builds use its usual target directory.

Development creates/uses the app's virtual environment. Packaging downloads the
same Python 3.11.9 Windows embeddable runtime used by the existing ZIP packager,
installs the declared backend dependencies into it, and stages only source and
frontend runtime resources. These downloads need a trusted network; TLS
verification must not be disabled.

Alembic runs before the server. Database and storage paths are overridden to the
app-specific Tauri local-data directory, never the read-only installation folder.
Development desktop data is also separate from web backend data.
Do not inspect or copy these user-data directories during development.

## Release checks

Before distribution, validate the app's frontend build/typecheck/tests, backend
tests, local checker, installer and installed-app lifecycle with synthetic inputs.
Inspect ZIP/installer metadata and exclusions without opening user data.
Packaging requires dedicated user approval; generating a scaffold does not grant it.
Template native preparation, installation, first-run migrations, error display and
shutdown must be tested on Windows before declaring a generated app release-ready.
