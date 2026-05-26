@echo off
chcp 65001 >nul
setlocal

REM ===========================================================================
REM  FTM Agent v4 - Lancement local
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
REM ===========================================================================

REM ---- Port unique (a ajuster par POC) -------------------------------------
set "PORT=8000"

set "APP_DIR=%~dp0"
set "BACKEND_DIR=%APP_DIR%backend"
set "REPO_ROOT=%APP_DIR%..\.."

echo ============================================================
echo  FTM Agent v4 - Lancement local
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

REM ---- Lancement uvicorn + ouverture navigateur -----------------------------
echo.
echo [run] Backend sur http://127.0.0.1:%PORT%/
echo       Le navigateur va s'ouvrir.  Ctrl+C ici pour arreter.
echo.

start "" "http://127.0.0.1:%PORT%/"
"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

echo.
echo [info] uvicorn arrete.
pause
