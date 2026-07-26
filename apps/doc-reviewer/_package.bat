@echo off
chcp 65001 >nul
setlocal

REM ===========================================================================
REM  Doc Reviewer - Generation du package partageable
REM
REM  Genere apps\doc-reviewer\dist\doc-reviewer-vX.Y.Z-YYYYMMDD.zip pret a
REM  envoyer a un collegue (Python embarque + UI buildee + start.bat).
REM  La logique vit dans scripts\package_doc_reviewer.py - ce wrapper offre
REM  l UX double-clic.
REM ===========================================================================

cd /d "%~dp0..\.."

echo ============================================================
echo  Doc Reviewer - Generation du package partageable
echo ============================================================
echo.

REM Node portable (sans install admin) prefixe au PATH si present, pour que
REM pnpm resolve lors du build front (--build-frontend embarque frontend/dist).
set "NODE_DIR="
for /d %%D in ("%LOCALAPPDATA%\node-portable\node-v*-win-x64") do set "NODE_DIR=%%D"
if defined NODE_DIR set "PATH=%NODE_DIR%;%PATH%"

REM --build-frontend : construit et EMBARQUE l'UI React (frontend/dist) dans le
REM ZIP pour que le collegue voie l'app sans Node ni build (sinon 503).
python scripts\package_doc_reviewer.py --out apps\doc-reviewer\dist --build-frontend
if errorlevel 1 (
    echo.
    echo [erreur] Packaging echoue.
    pause
    exit /b 1
)

echo.
pause
