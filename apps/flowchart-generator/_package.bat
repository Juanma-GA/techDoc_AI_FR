@echo off
chcp 65001 >nul
setlocal

REM Logique reelle du packaging - delegue a scripts\package_flowchart-generator.py.
REM Pour un nouveau POC : remplace flowchart-generator par le nom du POC.
cd /d "%~dp0..\.."

echo ============================================================
echo  flowchart-generator - Generation du package partageable
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo [erreur] Python introuvable dans le PATH.
    echo          Installe Python 3.11+ et relance.
    exit /b 1
)

python scripts\package_flowchart-generator.py --out apps\flowchart-generator\dist
if errorlevel 1 (
    echo.
    echo [erreur] Packaging echoue.
    exit /b 1
)

echo.
echo [info] Packaging termine. ZIP dans apps\flowchart-generator\dist\.
