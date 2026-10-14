@echo off
chcp 65001 >nul
setlocal EnableExtensions

set "APP_DIR=%~dp0"
set "BACKEND_DIR=%APP_DIR%backend"
set "FRONTEND_DIR=%APP_DIR%frontend"
set "STATIC_DIR=%BACKEND_DIR%\web\static\generated"
set "PORT=8085"
set /a PORT_MAX=PORT+20

echo ============================================================
echo  PDF Toolkit - lancement local
echo ============================================================
echo.

where go >nul 2>nul
if errorlevel 1 (
    echo [erreur] Go 1.25 ou plus recent est requis.
    echo          Installez Go depuis https://go.dev/dl/ puis relancez.
    pause
    exit /b 1
)
for /f "tokens=3" %%V in ('go version') do echo [info] %%V detecte.

set "NEED_BUILD=0"
if not exist "%STATIC_DIR%\index.html" set "NEED_BUILD=1"
if "%NEED_BUILD%"=="0" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%_needs_rebuild.ps1" "%FRONTEND_DIR%" "%STATIC_DIR%"
    if errorlevel 1 set "NEED_BUILD=1"
)

if "%NEED_BUILD%"=="0" goto :front_ready

where node >nul 2>nul
if errorlevel 1 (
    echo [erreur] Node.js 20+ est requis pour construire le frontend.
    pause
    exit /b 1
)
where pnpm >nul 2>nul
if errorlevel 1 (
    echo [erreur] pnpm 9+ est requis pour construire le frontend.
    echo          Activez pnpm avec Corepack ou installez-le via npm.
    pause
    exit /b 1
)

pushd "%FRONTEND_DIR%"
if not exist node_modules (
    echo [setup] Installation des dependances frontend...
    call pnpm install
    if errorlevel 1 (
        popd
        echo [erreur] Installation frontend echouee.
        pause
        exit /b 1
    )
)
echo [setup] Build du frontend...
call pnpm build
if errorlevel 1 (
    popd
    echo [erreur] Build frontend echoue.
    pause
    exit /b 1
)
popd

:front_ready
set /a PORT_TRY=PORT

:find_port
netstat -ano | findstr /R /C:":%PORT_TRY% .*LISTENING" >nul 2>nul
if errorlevel 1 goto :port_ok
set /a PORT_TRY=PORT_TRY+1
if %PORT_TRY% GTR %PORT_MAX% goto :no_port
goto :find_port

:no_port
echo [erreur] Aucun port libre entre 8085 et %PORT_MAX%.
pause
exit /b 1

:port_ok
if not "%PORT_TRY%"=="%PORT%" echo [info] Port 8085 occupe ; utilisation du port %PORT_TRY%.
set "PDF_TOOLKIT_ADDR=127.0.0.1:%PORT_TRY%"
set "PDF_TOOLKIT_OPEN_BROWSER=1"
echo.
echo [run] Demarrage du serveur sur http://127.0.0.1:%PORT_TRY%/
echo [wait] Le navigateur s'ouvrira quand le serveur sera pret.
echo [info] La compilation Go peut prendre un moment au premier lancement.
echo.
pushd "%BACKEND_DIR%"
go run -v .\cmd\pdf-toolkit
set "RUN_STATUS=%ERRORLEVEL%"
popd

if not "%RUN_STATUS%"=="0" (
    echo.
    echo [erreur] Le serveur PDF Toolkit s'est arrete avec le code %RUN_STATUS%.
)
pause
exit /b %RUN_STATUS%
