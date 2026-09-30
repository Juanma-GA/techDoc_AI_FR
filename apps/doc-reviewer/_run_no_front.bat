@echo off
chcp 65001 >nul
setlocal

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
    where python >nul 2>nul
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
echo.

"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

echo.
echo [info] uvicorn arrete.
pause
