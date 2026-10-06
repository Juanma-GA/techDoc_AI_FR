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

REM ---- Install deps si absentes OU si pyproject.toml a change depuis le
REM      dernier install (hash SHA256 stocke dans le marker). H-02 hardening :
REM      un simple marker vide ne se reinvalide jamais -- une dependance
REM      ajoutee a pyproject.toml (ex. regex) ne s'installait plus du tout
REM      sur un poste ou doc-reviewer avait deja tourne avant le pull.
set "PYPROJECT=%BACKEND_DIR%\pyproject.toml"
set "NEED_INSTALL=0"
if not exist "%INSTALLED_MARK%" set "NEED_INSTALL=1"

REM Comparaison hors bloc parenthese : l'expansion %VAR% dans un bloc if (...)
REM est figee a l'ouverture du bloc (pas de delayed expansion ici), donc le
REM calcul et la comparaison du hash doivent rester en lignes simples.
set "CURRENT_HASH="
if exist "%INSTALLED_MARK%" for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash -LiteralPath '%PYPROJECT%' -Algorithm SHA256).Hash"`) do set "CURRENT_HASH=%%H"
set "STORED_HASH="
if exist "%INSTALLED_MARK%" set /p STORED_HASH=<"%INSTALLED_MARK%"
if not "%CURRENT_HASH%"=="%STORED_HASH%" set "NEED_INSTALL=1"

if "%NEED_INSTALL%"=="1" (
    echo [setup] Installation des dependances Python ^(1 a 3 min^)...
    "%PYTHON%" -m pip install --upgrade pip >nul
    "%PYTHON%" -m pip install -e .
    if errorlevel 1 (
        echo [erreur] Echec installation des deps.
        pause
        exit /b 1
    )
    for /f "usebackq delims=" %%H in (`powershell -NoProfile -Command "(Get-FileHash -LiteralPath '%PYPROJECT%' -Algorithm SHA256).Hash"`) do >"%INSTALLED_MARK%" echo %%H
    echo [setup] OK.
)

REM ---- Auto-provision ENCRYPTION_KEY en posture locale (hardening H-03) ----
REM Sans cle, POST /settings/mistral refuse TOUTE sauvegarde de cle Mistral
REM (503) tant qu'un humain n'a pas genere+colle une cle Fernet a la main
REM dans backend\.env. Inerte des que BIND_HOST s'ecarte du defaut local
REM 127.0.0.1 : ce cas (deploiement palier 2/3) reste gere par
REM app.main._validate_security_posture, qui EXIGE une cle fournie par l'IT
REM et refuse de demarrer sans elle -- une auto-provision serait dangereuse
REM hors du poste local du developpeur.
set "ENV_FILE=%BACKEND_DIR%\.env"
set "BIND_HOST_VALUE="
if exist "%ENV_FILE%" for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /i "BIND_HOST=" "%ENV_FILE%"`) do set "BIND_HOST_VALUE=%%B"
set "IS_LOCAL_BIND=1"
if defined BIND_HOST_VALUE if /i not "%BIND_HOST_VALUE%"=="127.0.0.1" set "IS_LOCAL_BIND=0"

set "ENCRYPTION_KEY_VALUE="
if exist "%ENV_FILE%" for /f "usebackq tokens=1,* delims==" %%A in (`findstr /b /i "ENCRYPTION_KEY=" "%ENV_FILE%"`) do set "ENCRYPTION_KEY_VALUE=%%B"

if "%IS_LOCAL_BIND%"=="1" if not defined ENCRYPTION_KEY_VALUE (
    echo [setup] Generation d'une cle de chiffrement locale ^(ENCRYPTION_KEY^)...
    set "NEW_ENCRYPTION_KEY="
    for /f "usebackq delims=" %%K in (`"%PYTHON%" -c "from app.core.encryption import generate_key; print(generate_key())"`) do set "NEW_ENCRYPTION_KEY=%%K"
    if not defined NEW_ENCRYPTION_KEY (
        echo [erreur] Echec generation de la cle de chiffrement.
        pause
        exit /b 1
    )
    >>"%ENV_FILE%" echo ENCRYPTION_KEY=%NEW_ENCRYPTION_KEY%
    echo [setup] OK -- cle ecrite dans backend\.env.
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
REM  rien n'a change. Node portable (sans install admin) prefixe au PATH si present.
set "FRONTEND_DIR=%~dp0frontend"
set "NODE_DIR="
for /d %%D in ("%LOCALAPPDATA%\node-portable\node-v*-win-x64") do set "NODE_DIR=%%D"
if defined NODE_DIR set "PATH=%NODE_DIR%;%PATH%"

where pnpm >nul 2>nul
if errorlevel 1 goto :front_ready

set "NEED_BUILD=0"
if not exist "%FRONTEND_DIR%\dist\index.html" set "NEED_BUILD=1"
if "%NEED_BUILD%"=="0" if exist "%~dp0_needs_rebuild.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_needs_rebuild.ps1" "%FRONTEND_DIR%"
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
"%PYTHON%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%

echo.
echo [info] uvicorn arrete.
pause
