@echo off
setlocal
set "REPO_ROOT=%~dp0..\.."
where node >nul 2>nul
if errorlevel 1 (
    echo [error] Node.js 20+ is required.
    exit /b 1
)
if /i "%~1"=="desktop" goto :desktop
node "%REPO_ROOT%\scripts\package_pdf_toolkit.mjs" --out "%~dp0dist"
exit /b %ERRORLEVEL%

:desktop
node "%REPO_ROOT%\scripts\package_pdf_toolkit_desktop.mjs" --out "%~dp0dist"
exit /b %ERRORLEVEL%
