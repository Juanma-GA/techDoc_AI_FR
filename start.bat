@echo off
REM Sert le portail pour permettre le chargement de config.json.
set "PORT=8090"
set "PORTAL_DIR=%~dp0deploy\portal"
start "AI4TECHDOC Portal Server" /D "%PORTAL_DIR%" python -m http.server %PORT%
ping 127.0.0.1 -n 2 >nul
start "" "http://127.0.0.1:%PORT%/"
