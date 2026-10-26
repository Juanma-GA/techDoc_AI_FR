@echo off
setlocal EnableExtensions
set "PORT=8085"
set "APP_DIR=%~dp0"
set "REPO_ROOT=%APP_DIR%..\.."
set "BINARY=%APP_DIR%backend\bin\pdf-toolkit-backend.exe"
set /a PORT_MAX=PORT+20

if exist "%REPO_ROOT%\go-embed\bin\go.exe" goto :embedded_go
if not exist "%REPO_ROOT%\scripts\build_pdf_toolkit.mjs" goto :runtime
where node >nul 2>nul
if errorlevel 1 if exist "C:\PROJETS\AI4TECHDOC\node.exe" (
    set "PATH=C:\PROJETS\AI4TECHDOC;%PATH%"
)
where node >nul 2>nul
if errorlevel 1 (
    echo [error] Node.js 20+ is required to build the app from source.
    exit /b 1
)
where go >nul 2>nul
if errorlevel 1 (
    echo [error] Go 1.25+ is required to build the backend from source.
    exit /b 1
)
node "%REPO_ROOT%\scripts\build_pdf_toolkit.mjs" --allow-stale
if errorlevel 1 exit /b 1
goto :runtime

:embedded_go
powershell -NoProfile -File "%APP_DIR%_build_backend.ps1" -AppDir "%APP_DIR%."
if errorlevel 1 exit /b 1

:runtime
if not exist "%BINARY%" (
    echo [error] Missing PDF Toolkit backend binary.
    exit /b 1
)
set /a PORT_TRY=PORT
:find_port
netstat -ano | findstr /R /C:":%PORT_TRY% " | findstr "LISTENING" >nul 2>nul
if errorlevel 1 goto :port_ok
set /a PORT_TRY=PORT_TRY+1
if %PORT_TRY% GTR %PORT_MAX% (
    echo [error] No free port between %PORT% and %PORT_MAX%.
    exit /b 1
)
goto :find_port

:port_ok
set "PDF_TOOLKIT_ADDR=127.0.0.1:%PORT_TRY%"
set "PDF_TOOLKIT_OPEN_BROWSER=1"
echo [run] PDF Toolkit: http://127.0.0.1:%PORT_TRY%/
echo [info] Ctrl+C to stop the server.
"%BINARY%"
set "STATUS=%ERRORLEVEL%"
if not "%STATUS%"=="0" (
    echo [error] Backend stopped or Windows denied execution. Exit code: %STATUS%.
    echo [info] Contact IT if Windows Security reports a block. No protection was changed.
)
exit /b %STATUS%
