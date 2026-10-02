@echo off
setlocal

REM ---- Durcissement : outils systeme par chemin absolu ------------------------
REM  cmd.exe cherche d'abord un executable dans le dossier COURANT (ici backend\,
REM  inscriptible par l'utilisateur si l'IT n'a pas restreint les ACL) : un
REM  netstat.exe / findstr.exe / powershell.exe depose la etait execute a la place
REM  de l'outil Windows (y compris si un administrateur lance l'app). On coupe
REM  cette recherche et on appelle les outils systeme par leur chemin complet.
REM  Python est lance avec -s : le site-packages UTILISATEUR (%APPDATA%\Python,
REM  inscriptible) passait sinon AVANT les dependances figees du python-embed.
set "NoDefaultCurrentDirectoryInExePath=1"
set "SYS32=%SystemRoot%\System32"
"%SYS32%\chcp.com" 65001 >nul

REM ===========================================================================
REM  Doc Reviewer - Lancement local
REM
REM  Detection automatique de Python:
REM   1. Python embeddable bundled (../../python-embed/python.exe) - aucun
REM      pre-requis cote utilisateur (mode "package partageable").
REM   2. Sinon, fallback sur Python system du PATH (Python 3.11+ requis).
REM
REM  Au premier lancement : 1 a 3 min pour installer les deps Python.
REM  Aux lancements suivants : ~5 secondes.
REM ===========================================================================

REM ---- Port unique (a ajuster par POC) -------------------------------------
set "PORT=8003"

set "BACKEND_DIR=%~dp0backend"
cd /d "%BACKEND_DIR%"

echo ============================================================
echo  Doc Reviewer - Lancement local
echo ============================================================
echo.

REM ---- Detection Python: bundled embed ou system -----------------------------
set "EMBED_PY=%~dp0..\..\python-embed\python.exe"
set "USE_EMBED=0"
if exist "%EMBED_PY%" (
    set "USE_EMBED=1"
    set "PYTHON=%EMBED_PY%"
    set "INSTALLED_MARK=%~dp0..\..\python-embed\.docreviewer_installed"
    echo [info] Python embarque detecte: aucun pre-requis necessaire.
) else (
    "%SYS32%\where.exe" python >nul 2>nul
    if errorlevel 1 (
        echo [erreur] Python introuvable.
        echo          Installe Python 3.11+ depuis https://www.python.org/downloads/
        echo          ^(coche "Add Python to PATH" pendant l'installation^),
        echo          puis double-clique a nouveau sur start.bat.
        echo.
        pause
        exit /b 1
    )
    set "PYTHON=python"
    set "INSTALLED_MARK=%BACKEND_DIR%\.venv\.installed"
)

REM ---- Dossiers data --------------------------------------------------------
if not exist data         mkdir data
if not exist data\storage mkdir data\storage

REM ---- Venv (uniquement en mode system Python) ------------------------------
if "%USE_EMBED%"=="0" (
    if not exist .venv (
        echo [setup] Creation du venv Python...
        python -m venv .venv
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
REM  Package partageable : les dependances sont DEJA installees dans python-embed
REM  par scripts\package_doc_reviewer.py (marker present) -> aucun acces PyPI.
REM  Sinon : versions ET empreintes figees (requirements.lock.txt, --require-hashes),
REM  jamais de resolution flottante ni de mise a jour de pip depuis Internet.
if not exist "%INSTALLED_MARK%" (
    echo [setup] Installation des dependances Python verrouillees ^(1 a 3 min^)...
    "%PYTHON%" -s -m pip install --require-hashes --no-deps -r requirements.lock.txt
    if errorlevel 1 (
        echo [erreur] Echec installation des deps.
        pause
        exit /b 1
    )
    "%PYTHON%" -s -m pip install --no-deps -e .
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
"%PYTHON%" -s -m alembic upgrade head
if errorlevel 1 (
    echo [erreur] Echec migrations Alembic.
    pause
    exit /b 1
)

REM ---- Recherche d'un port libre (defaut %PORT%, sinon les suivants) -------
set /a PORT_TRY=%PORT%
set /a PORT_MAX=%PORT% + 20

:find_port
"%SYS32%\NETSTAT.EXE" -ano | "%SYS32%\findstr.exe" ":%PORT_TRY%" | "%SYS32%\findstr.exe" "LISTENING" >nul 2>nul
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
REM  rien n'a change. Node portable (sans install admin) prefixe au PATH si present.
set "FRONTEND_DIR=%~dp0frontend"
set "NODE_DIR="
for /d %%D in ("%LOCALAPPDATA%\node-portable\node-v*-win-x64") do set "NODE_DIR=%%D"
if defined NODE_DIR set "PATH=%NODE_DIR%;%PATH%"

"%SYS32%\where.exe" pnpm >nul 2>nul
if errorlevel 1 goto :front_ready

set "NEED_BUILD=0"
if not exist "%FRONTEND_DIR%\dist\index.html" set "NEED_BUILD=1"
if "%NEED_BUILD%"=="0" if exist "%~dp0_needs_rebuild.ps1" (
    "%SYS32%\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0_needs_rebuild.ps1" "%FRONTEND_DIR%"
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
echo [run] Backend sur http://127.0.0.1:%PORT%/
echo       Le navigateur va s'ouvrir.  Ctrl+C ici pour arreter.
echo.

start "" "http://127.0.0.1:%PORT%/"
"%PYTHON%" -s -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

echo.
echo [info] uvicorn arrete.
pause
