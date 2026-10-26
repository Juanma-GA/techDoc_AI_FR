@echo off
chcp 65001 >nul
setlocal

REM ===========================================================================
REM  doc-writer - Logique de lancement.
REM  Appele par start.bat dans une fenetre cmd /k qui restera ouverte
REM  quoi qu'il arrive. Pure ASCII, pas d'accent.
REM
REM  Detection Python (3 tiers):
REM   1. Python embeddable bundled (..\..\python-embed\python.exe)
REM   2. Python system du PATH (3.11+ requis)
REM   3. Auto-install via tools\python-installer.exe
REM ===========================================================================

REM ---- Port unique (a ajuster par POC) -------------------------------------
set "PORT=8002"

set "APP_DIR=%~dp0"
set "BACKEND_DIR=%APP_DIR%backend"
set "REPO_ROOT=%APP_DIR%..\.."

echo ============================================================
echo  doc-writer - Lancement local (port %PORT%)
echo ============================================================
echo.

set "EMBED_PY=%APP_DIR%..\..\python-embed\python.exe"
set "USE_EMBED=0"
if exist "%EMBED_PY%" (
    set "USE_EMBED=1"
    set "PYTHON=%EMBED_PY%"
    set "INSTALLED_MARK=%APP_DIR%..\..\python-embed\.doc-writer_installed"
    echo [info] Python embarque detecte.
    goto :have_python
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=python"
    set "INSTALLED_MARK=%BACKEND_DIR%\.venv\.installed"
    goto :have_python
)

set "PY_INSTALLER="
if exist "%REPO_ROOT%\tools\python-installer.exe" set "PY_INSTALLER=%REPO_ROOT%\tools\python-installer.exe"

if not defined PY_INSTALLER (
    echo [erreur] Python introuvable.
    echo          Installe Python 3.11+ depuis https://www.python.org/downloads/
    echo          Coche bien "Add Python to PATH" pendant l'install.
    exit /b 1
)

echo [setup] Installation silencieuse de Python en cours - 1 a 2 min...
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1
if errorlevel 1 (
    echo [erreur] L'installation Python a echoue.
    exit /b 1
)

for /f "skip=2 tokens=2,*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
if defined USER_PATH set "PATH=%USER_PATH%;%PATH%"

where python >nul 2>nul
if errorlevel 1 (
    echo [erreur] Python installe mais introuvable apres refresh du PATH.
    echo          Ferme cette fenetre, ouvre-en une nouvelle, et relance.
    exit /b 1
)
set "PYTHON=python"
set "INSTALLED_MARK=%BACKEND_DIR%\.venv\.installed"

:have_python
cd /d "%BACKEND_DIR%"

if not exist data         mkdir data
if not exist data\storage mkdir data\storage

if "%USE_EMBED%"=="0" (
    if not exist .venv (
        echo [setup] Creation du venv...
        "%PYTHON%" -m venv .venv
        if errorlevel 1 (
            echo [erreur] Echec creation du venv.
            exit /b 1
        )
    )
    call .venv\Scripts\activate.bat
    set "PYTHON=python"
)

if not exist "%INSTALLED_MARK%" (
    echo [setup] Installation des deps Python en cours - 1 a 3 min...
    "%PYTHON%" -m pip install --upgrade pip >nul
    REM F-07 (hardening) : installe depuis le lock hash-verifie (versions
    REM exactes) plutot que de re-resoudre les bornes larges de pyproject.toml
    REM a chaque poste, pour un build reproductible. --no-deps ensuite : le
    REM paquet local seul, les deps sont deja posees par le lock ci-dessus.
    "%PYTHON%" -m pip install -r requirements.lock.txt
    if errorlevel 1 (
        echo [erreur] Echec installation des deps verrouillees ^(requirements.lock.txt^).
        exit /b 1
    )
    "%PYTHON%" -m pip install -e . --no-deps
    if errorlevel 1 (
        echo [erreur] Echec installation du paquet local.
        exit /b 1
    )
    type nul > "%INSTALLED_MARK%"
)

echo [setup] Migrations Alembic...
"%PYTHON%" -m alembic upgrade head
if errorlevel 1 (
    echo [erreur] Echec migrations.
    exit /b 1
)

REM ---- Pre-fetch Inter TTF (best-effort, ignore les erreurs reseau) --------
echo [setup] Verification de la police Inter pour les exports PDF...
"%PYTHON%" -c "from app.core.fonts import ensure_inter; ensure_inter()" 2>nul
if errorlevel 1 echo [info] Police Inter non telechargee, exports PDF en Helvetica.

REM ---- Recherche d'un port libre (defaut %PORT%, sinon les suivants) -------
set /a PORT_TRY=%PORT%
set /a PORT_MAX=%PORT% + 20

:find_port
netstat -ano | findstr ":%PORT_TRY%" | findstr "LISTENING" >nul 2>nul
if errorlevel 1 goto :port_ok
set /a PORT_TRY=PORT_TRY + 1
if %PORT_TRY% GTR %PORT_MAX% goto :no_port
goto :find_port

:no_port
echo [erreur] Aucun port libre entre %PORT% et %PORT_MAX%.
echo          Ferme les applications qui ecoutent sur ces ports.
exit /b 1

:port_ok
if not "%PORT_TRY%"=="%PORT%" echo [info] Port %PORT% occupe -- bascule auto sur le port %PORT_TRY%.
set "PORT=%PORT_TRY%"

REM ---- Front React : on sert le build (dist) sur le meme port que le backend.
REM  Rebuild AUTO si le dist est absent OU si une source front est plus recente
REM  que le dernier build (helper _needs_rebuild.ps1). Restart instantane si
REM  rien n'a change. Node portable (sans install admin) prefixe au PATH si present.
set "FRONTEND_DIR=%APP_DIR%frontend"
set "NODE_DIR="
for /d %%D in ("%LOCALAPPDATA%\node-portable\node-v*-win-x64") do set "NODE_DIR=%%D"
if defined NODE_DIR set "PATH=%NODE_DIR%;%PATH%"
where node >nul 2>nul
if errorlevel 1 if exist "C:\PROJETS\AI4TECHDOC\node.exe" (
    set "PATH=C:\PROJETS\AI4TECHDOC;%PATH%"
)

where pnpm >nul 2>nul
if errorlevel 1 goto :front_ready

set "NEED_BUILD=0"
if not exist "%FRONTEND_DIR%\dist\index.html" set "NEED_BUILD=1"
if "%NEED_BUILD%"=="0" if exist "%APP_DIR%_needs_rebuild.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%_needs_rebuild.ps1" "%FRONTEND_DIR%"
    if errorlevel 1 set "NEED_BUILD=1"
)
if "%NEED_BUILD%"=="0" goto :front_ready

echo [setup] Build du front React - dist absent ou sources modifiees, 5 a 30 s...
pushd "%FRONTEND_DIR%"
REM pnpm install UNIQUEMENT si node_modules absent : en reseau avec interception
REM TLS, un install "a jour" retente chaque paquet pendant des minutes et bloque
REM le lancement. Le build seul tourne hors-ligne quand node_modules est present.
if not exist node_modules call pnpm install
call pnpm build
popd
:front_ready

echo.
echo [run] React   : http://127.0.0.1:%PORT%/
echo       Preview : http://127.0.0.1:%PORT%/preview  (acces manuel si besoin)
echo       OpenAPI : http://127.0.0.1:%PORT%/api/v1/docs
echo       Ctrl+C ici pour arreter.
echo.

start "" "http://127.0.0.1:%PORT%/"
"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

echo.
echo [info] uvicorn arrete.
