@echo off
setlocal
cd /d "%~dp0..\.."
if not exist ".venv\Scripts\python.exe" (
    echo [erreur] Backend venv introuvable: %CD%\.venv\Scripts\python.exe
    echo          Creez-le puis installez les dependances dev.
    exit /b 1
)
if "%~1"=="" (
    echo Usage: run_manual_verification.bat chemin\vers\document.pdf [options]
    echo Exemple: run_manual_verification.bat C:\docs\manual.docx --skip-analysis
    exit /b 2
)
".venv\Scripts\python.exe" "tests\backend_only_tests\run_manual_verification.py" %*
exit /b %ERRORLEVEL%
