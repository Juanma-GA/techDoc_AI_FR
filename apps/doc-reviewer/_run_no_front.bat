@echo off
setlocal

REM ---- Durcissement : outils systeme par chemin absolu, Python -s (cf. _run.bat)
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

REM ---- Dependencies: skip preinstalled embed, refresh changed local env -----
if "%USE_EMBED%"=="1" if exist "%INSTALLED_MARK%" goto deps_ready
set "DEPS_HASH="
set "DEPS_HASH_FILE=%TEMP%\docreviewer_deps_hash_%RANDOM%_%RANDOM%.txt"
"%SYS32%\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "$ErrorActionPreference='Stop'; $p=(Get-FileHash -Algorithm SHA256 -LiteralPath pyproject.toml).Hash; $l=(Get-FileHash -Algorithm SHA256 -LiteralPath requirements.lock.txt).Hash; $p+$l" > "%DEPS_HASH_FILE%"
if errorlevel 1 (
    del "%DEPS_HASH_FILE%" >nul 2>nul
    echo [erreur] Impossible de calculer l'empreinte des dependances.
    pause
    exit /b 1
)
set /p DEPS_HASH=<"%DEPS_HASH_FILE%"
del "%DEPS_HASH_FILE%" >nul 2>nul
if not defined DEPS_HASH (
    echo [erreur] Impossible de calculer l'empreinte des dependances.
    pause
    exit /b 1
)
set "INSTALLED_HASH="
if exist "%INSTALLED_MARK%" set /p INSTALLED_HASH=<"%INSTALLED_MARK%"
if /i "%INSTALLED_HASH%"=="%DEPS_HASH%" goto deps_ready

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
>"%INSTALLED_MARK%" echo %DEPS_HASH%
echo [setup] OK.
:deps_ready

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

REM ---- Lancement uvicorn + ouverture navigateur -----------------------------
echo.
echo [run] Backend sur http://127.0.0.1:%PORT%/
echo.

"%PYTHON%" -s -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

echo.
echo [info] uvicorn arrete.
pause
