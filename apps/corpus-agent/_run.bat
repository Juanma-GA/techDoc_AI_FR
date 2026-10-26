@echo off
chcp 65001 >nul
setlocal

REM ===========================================================================
REM  Corpus Agent v4 - Lancement local
REM
REM  Detection automatique de Python (3 tiers, dans l'ordre):
REM   1. Python embeddable bundled (..\..\python-embed\python.exe) - aucun
REM      pre-requis cote utilisateur (mode "package partageable").
REM   2. Python system du PATH (Python 3.11+ requis).
REM   3. Auto-install silencieux via tools\python-installer.exe (user-only,
REM      sans admin), puis re-detection.
REM
REM  Au premier lancement : 1 a 3 min pour installer les deps Python.
REM  Aux lancements suivants : ~5 secondes.
REM
REM  UI = React buildi, servi par le backend sur le port 8000. Le front est
REM  reconstruit AUTOMATIQUEMENT au lancement si frontend\dist est absent OU si
REM  une source front (frontend\src, index.html, configs) est plus recente que
REM  le dernier build (helper _needs_rebuild.ps1). Donc une modif du code front
REM  est prise en compte au prochain start.bat, sans supprimer dist a la main.
REM  Restart instantane si rien n'a change. Si pnpm est absent, on sert le dist
REM  existant tel quel. Un seul onglet ouvert : http://127.0.0.1:8000/.
REM ===========================================================================

REM ---- Port unique (a ajuster par POC) -------------------------------------
set "PORT=8001"

set "APP_DIR=%~dp0"
set "BACKEND_DIR=%APP_DIR%backend"
set "REPO_ROOT=%APP_DIR%..\.."

echo ============================================================
echo  Corpus Agent v4 - Lancement local
echo ============================================================
echo.

REM ---- Detection Python: bundled embed > system > MSI installer -------------
set "EMBED_PY=%APP_DIR%..\..\python-embed\python.exe"
set "USE_EMBED=0"
if exist "%EMBED_PY%" (
    set "USE_EMBED=1"
    set "PYTHON=%EMBED_PY%"
    set "INSTALLED_MARK=%APP_DIR%..\..\python-embed\.ftmv2_installed"
    echo [info] Python embarque detecte: aucun pre-requis necessaire.
    goto :have_python
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=python"
    set "INSTALLED_MARK=%BACKEND_DIR%\.venv\.installed"
    goto :have_python
)

REM ---- Tier 3: tentative d'auto-install via MSI ----------------------------
set "PY_INSTALLER="
if exist "%REPO_ROOT%\tools\python-installer.exe" set "PY_INSTALLER=%REPO_ROOT%\tools\python-installer.exe"

if not defined PY_INSTALLER (
    echo [erreur] Python introuvable et aucune solution de fallback.
    echo          Solutions :
    echo            1. Installe Python 3.11+ : https://www.python.org/downloads/
    echo               ^(coche "Add Python to PATH" pendant l'install^)
    echo            2. OU repackage le zip avec --embed-python.
    echo            3. OU place python-installer.exe dans tools\ a la racine.
    echo.
    pause
    exit /b 1
)

echo [setup] Python introuvable. Installation silencieuse en cours ^(1-2 min^)...
echo         Pour l'utilisateur courant uniquement, sans droits admin.
"%PY_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1
if errorlevel 1 (
    echo [erreur] L'installation Python a echoue.
    pause
    exit /b 1
)

REM Refresh PATH depuis le registre user
for /f "skip=2 tokens=2,*" %%A in ('reg query "HKCU\Environment" /v Path 2^>nul') do set "USER_PATH=%%B"
if defined USER_PATH set "PATH=%USER_PATH%;%PATH%"

where python >nul 2>nul
if errorlevel 1 (
    echo [erreur] Python installe mais introuvable apres refresh du PATH.
    echo          Ferme cette fenetre, ouvre-en une nouvelle, et relance start.bat.
    pause
    exit /b 1
)
set "PYTHON=python"
set "INSTALLED_MARK=%BACKEND_DIR%\.venv\.installed"
echo [setup] OK : Python installe.
echo.

:have_python
cd /d "%BACKEND_DIR%"

REM ---- Dossiers data --------------------------------------------------------
if not exist data         mkdir data
if not exist data\storage mkdir data\storage

REM ---- Venv (uniquement en mode system Python) ------------------------------
if "%USE_EMBED%"=="0" (
    if not exist .venv (
        echo [setup] Creation du venv Python...
        "%PYTHON%" -m venv .venv
        if errorlevel 1 (
            echo [erreur] Echec creation du venv.
            pause
            exit /b 1
        )
    )
    call .venv\Scripts\activate.bat
    set "PYTHON=python"
)

REM ---- Install deps une seule fois (marker .installed) ---------------------
if not exist "%INSTALLED_MARK%" (
    echo [setup] Installation des dependances Python ^(1 a 3 min^)...
    "%PYTHON%" -m pip install --upgrade pip >nul
    "%PYTHON%" -m pip install -e .
    if errorlevel 1 (
        echo [erreur] Echec installation des deps.
        pause
        exit /b 1
    )
    type nul > "%INSTALLED_MARK%"
    echo [setup] OK.
)

REM ---- Alembic upgrade head a CHAQUE lancement (idempotent) ----------------
echo [setup] Verification du schema DB ^(alembic^)...
"%PYTHON%" -m alembic upgrade head
if errorlevel 1 (
    echo [erreur] Echec migrations Alembic.
    pause
    exit /b 1
)

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
pause
exit /b 1

:port_ok
if not "%PORT_TRY%"=="%PORT%" echo [info] Port %PORT% occupe -- bascule auto sur le port %PORT_TRY%.
set "PORT=%PORT_TRY%"

REM ---- Front React : on sert le build (dist) sur le meme port que le backend.
REM  Rebuild AUTO si le dist est absent OU si une source front est plus recente
REM  que le dernier build (helper _needs_rebuild.ps1). Restart instantane si
REM  rien n'a change. Node portable (sans install admin) : si present, on le
REM  prefixe au PATH pour que pnpm/node soient trouves meme dans un cmd neuf.
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

REM dist absent => rebuild. Sinon on delegue la fraicheur au helper PowerShell
REM (exit 1 = sources plus recentes que dist). Si le helper manque (zip sans
REM le .ps1), on retombe sur l'ancien comportement : build seulement si absent.
set "NEED_BUILD=0"
if not exist "%FRONTEND_DIR%\dist\index.html" set "NEED_BUILD=1"
if "%NEED_BUILD%"=="0" if exist "%APP_DIR%_needs_rebuild.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%_needs_rebuild.ps1" "%FRONTEND_DIR%"
    if errorlevel 1 set "NEED_BUILD=1"
)
if "%NEED_BUILD%"=="0" goto :front_ready

echo [setup] Build du front React - dist absent ou sources modifiees, 5 a 30 s...
pushd "%FRONTEND_DIR%"
REM pnpm install UNIQUEMENT si node_modules absent (evite le hang TLS corporate)
if not exist node_modules call pnpm install
call pnpm build
popd
:front_ready

REM ---- Lancement uvicorn + ouverture navigateur -----------------------------
echo.
echo [run] App ^(React buildi^) sur http://127.0.0.1:%PORT%/
echo       L'onglet va s'ouvrir.  Ctrl+C ici pour arreter.
echo.

start "" "http://127.0.0.1:%PORT%/"
"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

echo.
echo [info] uvicorn arrete.
pause
