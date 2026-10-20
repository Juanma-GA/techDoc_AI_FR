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
The scaffold grants no broad remote-page IPC. Its only remote capability is
`core:window:allow-set-theme` for the app's `http://127.0.0.1:*` UI origin.

## Native window theme

Desktop windows must follow the React app's persisted dark/light theme while
retaining the operating system's native title bar. Start the window with the
dark theme to match the app's default, set `app.withGlobalTauri` to
`true` only in the desktop Tauri configuration, and apply the stored preference
from the desktop startup page before navigating to the main app. The React shell
then observes changes to the root `.dark` class and calls
`getCurrentWindow().setTheme("dark" | "light")` when the user toggles themes.

The Tauri capability must grant only `core:window:allow-set-theme` and scope its
remote URL to `http://127.0.0.1:*`; the backend selects an ephemeral loopback
port. Do not add broad IPC permissions or expose this capability to other
origins.

Keep this integration optional in shared app React code: web-only apps must
continue to work without Tauri globals or Tauri npm dependencies. Log failures
to synchronize the native theme rather than silently ignoring them. The desktop
scaffold and the generator regression test cover this contract.

## Desktop startup screen

The initial Tauri window should show a loading screen until startup is complete,
then navigate to the app's normal React entry point. Keep the screen in the
desktop scaffold as `frontend/src/desktop-startup.html` plus
`frontend/src/desktop-startup.tsx`, included as a second Vite entry only when
present. Its TSX page must use existing `@internal/ui` components (for example
`Card`, `Ai4TechDocLogo`, and `LoadingOverlay`), the shared theme CSS, and the
app's existing i18n resources. Use the HTML title or app configuration for
app-specific branding rather than hardcoding a POC name in the shared scaffold.

The loader is indeterminate; do not show a fabricated percentage. Its `role=status`
and `aria-busy` state should remain accessible. On startup failure, stop the
spinner and expose the error as an alert. The Rust shell keeps the window on this
page through migrations and all startup-critical service/model warm-ups, and
navigates only after the relevant health checks succeed. Apps without startup
model warm-up should keep model inference lazy rather than adding expensive work
to the generic template.

For apps that need model warm-up before first use, pass a desktop-only opt-in
environment flag to the API and model service. Their ASGI startup lifespan must
load the model before the health endpoint can return 200. Keep that flag off for
web/ZIP launchers unless their behavior is explicitly intended to change. The
Image Processor desktop adapter sets `DESKTOP_PRELOAD_MODELS=true` for OCR and
LaMa; its health waits have a bounded 10-minute timeout, after which the splash
shows an explicit startup error.

Build the second HTML entry with Vite and point the initial Tauri window at its
output path. Run desktop preparation synchronously before `tauri dev` or `tauri
build`; do not depend on a parallel Tauri hook to produce files Cargo needs.
For example, Image Processor opts into `DESKTOP_PRELOAD_MODELS=true` for both
local services, so its health checks stay pending until OCR and LaMa models are
loaded; the general template does not enable model warm-up by default.

## Default FastAPI desktop adapter

Currently supported for **Windows x64**. Requires Rust stable, Visual Studio C++
build tools, WebView2 and Node/pnpm. Development additionally uses Python 3.11+.

```powershell
pnpm desktop:dev:my-desktop-app
pnpm desktop:build:my-desktop-app
```

Or run `package.bat desktop` inside the generated app; this puts Cargo output in
`apps/<slug>/dist/tauri/`. The generated `tauri:dev` and `tauri:build` package
scripts prepare frontend and runtime resources synchronously before invoking
Tauri. Direct Tauri CLI commands must first run
`node scripts/prepare-desktop.mjs dev` or `build`; they use the usual target
directory.

Development creates/uses the app's virtual environment. Packaging downloads the
same Python 3.11.9 Windows embeddable runtime used by the existing ZIP packager,
installs the declared backend dependencies into it, and stages only source and
frontend runtime resources. These downloads need a trusted network; TLS
verification must not be disabled.

Alembic runs before the server. Database and storage paths are overridden to the
app-specific Tauri local-data directory, never the read-only installation folder.
Development desktop data is also separate from web backend data.
Do not inspect or copy these user-data directories during development.

## Desktop setup and troubleshooting

Install workspace dependencies once from the **monorepo root**, after checkout,
scaffolding, or any change to a frontend dependency manifest or `pnpm-lock.yaml`:

```powershell
pnpm install
pnpm desktop:dev:<slug>
```

`@tauri-apps/cli` is a local frontend development dependency. `tauri` not being
recognized usually means workspace dependencies were not installed or the lockfile
is stale; check it with
`pnpm --filter @apps/<slug>-frontend exec tauri --version`. Do not install a
global Tauri CLI or run `pnpm create tauri-app` inside an existing app. For a new
desktop POC, use `node scripts/new_poc.mjs <slug> <port> --desktop`.

Do not put `pnpm install` unconditionally on a launcher/build critical path:
install workspace dependencies explicitly as above. A wrapper may install only
when `frontend/node_modules` is absent; it must not silently skip the explicit
dependency sync after adding `@tauri-apps/cli` to an existing checkout.

If pnpm or pip reports `UNABLE_TO_GET_ISSUER_CERT_LOCALLY`, fix the configured
corporate CA certificate path (including `NODE_EXTRA_CA_CERTS` when set), then
retry the install. Never disable TLS verification with `strict-ssl=false` or
`NODE_TLS_REJECT_UNAUTHORIZED=0`.

Tauri may start Cargo while `beforeDevCommand` is still preparing the app. When
preparation creates files required by Rust compilation, serialize preparation
before invoking `tauri dev` / `tauri build` from the package script. Also keep
every configured `bundle.resources` path present in the source tree: for example,
track `frontend/src-tauri/runtime/.gitkeep` when `runtime/` is configured as a
resource, and preserve it while clearing generated runtime contents. Otherwise
Cargo fails with `resource path 'runtime' doesn't exist`.

Avoid compile-time `include_str!` references to runtime configuration that is
only generated by an asynchronous Tauri hook. Check in a stable configuration,
or ensure generation completes synchronously before Cargo starts. Runtime staging
must prepare the executable and its resources before the app can start.

For Python-backed apps, reuse the launcher's development virtual environments
and install-marker names when they are shared. A second, desktop-only marker can
cause `pip install --upgrade` to run on every first Tauri launch even though the
launcher already installed the dependencies. A Windows exit code `4294967295`
at that pip step is a cue to inspect the venv executable and marker alignment;
do not treat it as a missing Tauri CLI or bypass certificate validation.

## Release checks

Before distribution, validate the app's frontend build/typecheck/tests, backend
tests, local checker, installer and installed-app lifecycle with synthetic inputs.
Inspect ZIP/installer metadata and exclusions without opening user data.
Packaging requires dedicated user approval; generating a scaffold does not grant it.
Template native preparation, installation, first-run migrations, error display and
shutdown must be tested on Windows before declaring a generated app release-ready.
