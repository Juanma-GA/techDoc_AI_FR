@echo off
chcp 65001 >nul
setlocal

REM ===========================================================================
REM  Corpus Agent v4 - Generation du package partageable
REM
REM  Genere apps\corpus-agent\dist\corpus-vX.Y.Z-YYYYMMDD.zip pret a envoyer
REM  a un collegue (Python embarque + UI buildee + start.bat). La logique
REM  vit dans scripts\package_corpus_agent.py - ce wrapper offre l UX double-clic.
REM ===========================================================================

cd /d "%~dp0..\.."

echo ============================================================
echo  Corpus Agent v4 - Generation du package partageable
echo ============================================================
echo.

python scripts\package_corpus_agent.py --out apps\corpus-agent\dist
if errorlevel 1 (
    echo.
    echo [erreur] Packaging echoue.
    pause
    exit /b 1
)

echo.
pause
