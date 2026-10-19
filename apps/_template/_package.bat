@echo off
chcp 65001 >nul
setlocal
if /i "%~1"=="desktop" goto :desktop

REM Logique reelle du packaging - delegue a scripts\package_TEMPLATE.py.
REM Pour un nouveau POC : remplace TEMPLATE par le nom du POC.
cd /d "%~dp0..\.."

echo ============================================================
echo  TEMPLATE - Generation du package partageable
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [erreur] Python introuvable dans le PATH.
    echo          Installe Python 3.11+ et relance.
    exit /b 1
)

python scripts\package_TEMPLATE.py --out apps\_template\dist
if errorlevel 1 (
    echo.
    echo [erreur] Packaging echoue.
    exit /b 1
)

echo.
echo [info] Packaging termine. ZIP dans apps\_template\dist\.
exit /b 0

:desktop
if not exist "%~dp0frontend\desktop.json" (
    echo [error] Desktop is not enabled. Generate the app with --desktop.
    exit /b 1
)
set "CARGO_TARGET_DIR=%~dp0dist\tauri"
pushd "%~dp0frontend"
if not exist node_modules call pnpm install
if errorlevel 1 (
    popd
    exit /b 1
)
call pnpm tauri:build
set "STATUS=%ERRORLEVEL%"
popd
exit /b %STATUS%
