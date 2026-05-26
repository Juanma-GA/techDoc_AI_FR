@echo off
chcp 65001 >nul
setlocal

REM ===========================================================================
REM  PDF Reviewer - Generation du package partageable
REM
REM  Genere apps\pdf-reviewer\dist\pdf-reviewer-vX.Y.Z-YYYYMMDD.zip pret a
REM  envoyer a un collegue (Python embarque + UI buildee + start.bat).
REM  La logique vit dans scripts\package_pdf_reviewer.py - ce wrapper offre
REM  l UX double-clic.
REM ===========================================================================

cd /d "%~dp0..\.."

echo ============================================================
echo  PDF Reviewer - Generation du package partageable
echo ============================================================
echo.

python scripts\package_pdf_reviewer.py --out apps\pdf-reviewer\dist
if errorlevel 1 (
    echo.
    echo [erreur] Packaging echoue.
    pause
    exit /b 1
)

echo.
pause
