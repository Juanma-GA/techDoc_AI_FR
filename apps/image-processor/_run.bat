@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
set "PORT=8010"
set "LAMA_PORT=8011"
set "APP_DIR=%~dp0"
for %%I in ("%APP_DIR%..\..") do set "REPO_ROOT=%%~fI"
set "BACKEND_DIR=%APP_DIR%backend"
set "LAMA_DIR=%BACKEND_DIR%\lama_service"
set "FRONTEND_DIR=%APP_DIR%frontend"
echo ============================================================
echo  image-processor - Local launch
echo ============================================================
set "MAIN_PY=%REPO_ROOT%\python-embed\python.exe"
set "MAIN_MARK=%REPO_ROOT%\python-embed\.image-processor-installed"
if not exist "%MAIN_PY%" (
    set "MAIN_BASE_PY="
    where py >nul 2>nul
    if errorlevel 1 goto :python313_missing
    for /f "delims=" %%P in ('py -3.13 -c "import sys; print(sys.executable)" 2^>nul') do set "MAIN_BASE_PY=%%P"
    if not defined MAIN_BASE_PY goto :python313_missing
    if not exist "%BACKEND_DIR%\.venv\Scripts\python.exe" (
        echo [setup] Creating Python 3.13 environment...
        py -3.13 -m venv "%BACKEND_DIR%\.venv"
        if errorlevel 1 goto :setup_error
    )
    set "MAIN_PY=%BACKEND_DIR%\.venv\Scripts\python.exe"
    set "MAIN_MARK=%BACKEND_DIR%\.venv\.image-processor-installed"
)
if not exist "%MAIN_MARK%" (
    echo [setup] Installing PaddleOCR backend dependencies...
    "%MAIN_PY%" -m pip install --upgrade pip setuptools wheel
    if errorlevel 1 goto :setup_error
    "%MAIN_PY%" -m pip install --no-build-isolation -e "%BACKEND_DIR%"
    if errorlevel 1 goto :setup_error
    type nul > "%MAIN_MARK%"
)
set "LAMA_PY=%REPO_ROOT%\python-embed-lama\python.exe"
set "LAMA_MARK=%REPO_ROOT%\python-embed-lama\.image-processor-lama-installed"
if not exist "%LAMA_PY%" (
    set "LAMA_BASE_PY="
    where py >nul 2>nul
    if not errorlevel 1 (
        for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "LAMA_BASE_PY=%%P"
    )
    if not defined LAMA_BASE_PY (
        if not exist "%REPO_ROOT%\tools\python-installer.exe" goto :python311_missing
        echo [setup] Installing Python 3.11 for the local LaMa service...
        "%REPO_ROOT%\tools\python-installer.exe" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 SimpleInstall=1
        if errorlevel 1 goto :setup_error
        for /f "delims=" %%P in ('py -3.11 -c "import sys; print(sys.executable)" 2^>nul') do set "LAMA_BASE_PY=%%P"
        if not defined LAMA_BASE_PY if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" set "LAMA_BASE_PY=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        if not defined LAMA_BASE_PY goto :python311_missing
    )
    if not exist "%LAMA_DIR%\.venv\Scripts\python.exe" (
        echo [setup] Creating Python 3.11 LaMa environment...
        "!LAMA_BASE_PY!" -m venv "%LAMA_DIR%\.venv"
        if errorlevel 1 goto :setup_error
    )
    set "LAMA_PY=%LAMA_DIR%\.venv\Scripts\python.exe"
    set "LAMA_MARK=%LAMA_DIR%\.venv\.image-processor-lama-installed"
)
if not exist "%LAMA_MARK%" (
    echo [setup] Installing local LaMa dependencies...
    "%LAMA_PY%" -m pip install --upgrade pip setuptools wheel
    if errorlevel 1 goto :setup_error
    "%LAMA_PY%" -m pip install --no-build-isolation -e "%LAMA_DIR%"
    if errorlevel 1 goto :setup_error
    type nul > "%LAMA_MARK%"
)
cd /d "%BACKEND_DIR%"
echo [setup] Applying database migrations...
"%MAIN_PY%" -m alembic upgrade head
if errorlevel 1 goto :setup_error
where curl.exe >nul 2>nul
if errorlevel 1 (
    echo [error] curl.exe is required to check the local LaMa service.
    pause
    exit /b 1
)
set /a PORT_TRY=%PORT%
set /a PORT_MAX=%PORT% + 20
:find_port
netstat -ano | findstr ":%PORT_TRY%" | findstr "LISTENING" >nul 2>nul
if errorlevel 1 goto :api_port_found
set /a PORT_TRY=PORT_TRY + 1
if %PORT_TRY% GTR %PORT_MAX% goto :no_port
goto :find_port
:api_port_found
if not "%PORT_TRY%"=="%PORT%" echo [info] API port %PORT% is busy; using %PORT_TRY%.
set "PORT=%PORT_TRY%"
set "LAMA_REUSE=0"
set /a LAMA_TRY=8011
set /a LAMA_MAX=8031
:find_lama_port
if "%LAMA_TRY%"=="%PORT%" goto :next_lama_port
if "%LAMA_TRY%"=="8011" (
    curl.exe -fsS --max-time 2 http://127.0.0.1:%LAMA_TRY%/health >nul 2>&1
    if not errorlevel 1 (
        set "LAMA_REUSE=1"
        goto :lama_port_found
    )
)
netstat -ano | findstr ":%LAMA_TRY%" | findstr "LISTENING" >nul 2>nul
if errorlevel 1 goto :lama_port_found
:next_lama_port
set /a LAMA_TRY=LAMA_TRY + 1
if %LAMA_TRY% GTR %LAMA_MAX% goto :no_lama_port
goto :find_lama_port
:lama_port_found
set "LAMA_PORT=%LAMA_TRY%"
if "%LAMA_REUSE%"=="0" (
    echo [run] Starting local LaMa service on port %LAMA_PORT%...
    start "image-processor LaMa" /D "%LAMA_DIR%" cmd /k ""%LAMA_PY%" -m uvicorn app:app --host 127.0.0.1 --port %LAMA_PORT%"
    set "LAMA_READY=0"
    for /L %%I in (1,1,180) do (
        curl.exe -fsS --max-time 2 http://127.0.0.1:%LAMA_PORT%/health >nul 2>&1
        if not errorlevel 1 (
            set "LAMA_READY=1"
            goto :lama_ready
        )
        timeout /t 1 /nobreak >nul
    )
    goto :lama_start_error
)
:lama_ready
set "LAMA_SERVICE_PORT=%LAMA_PORT%"
set "NODE_DIR="
for /d %%D in ("%LOCALAPPDATA%\node-portable\node-v*-win-x64") do set "NODE_DIR=%%D"
if defined NODE_DIR set "PATH=%NODE_DIR%;%PATH%"
where pnpm >nul 2>nul
if not errorlevel 1 (
    set "NEED_BUILD=0"
    if not exist "%FRONTEND_DIR%\dist\index.html" set "NEED_BUILD=1"
    if "!NEED_BUILD!"=="0" if exist "%APP_DIR%_needs_rebuild.ps1" (
        powershell -NoProfile -ExecutionPolicy Bypass -File "%APP_DIR%_needs_rebuild.ps1" "%FRONTEND_DIR%"
        if errorlevel 1 set "NEED_BUILD=1"
    )
    if "!NEED_BUILD!"=="1" (
        echo [setup] Building React frontend...
        pushd "%FRONTEND_DIR%"
        if not exist node_modules call pnpm install
        if errorlevel 1 (
            popd
            goto :frontend_error
        )
        set "BUILD_ERROR=0"
        call pnpm build
        if errorlevel 1 set "BUILD_ERROR=1"
        popd
        if "!BUILD_ERROR!"=="1" if not exist "%FRONTEND_DIR%\dist\index.html" goto :frontend_error
        if "!BUILD_ERROR!"=="1" echo [warn] Build failed; serving the existing frontend bundle.
    )
)
echo.
echo [run] App: http://127.0.0.1:%PORT%/
echo       LaMa: http://127.0.0.1:%LAMA_PORT%/health
echo       API docs: http://127.0.0.1:%PORT%/api/v1/docs
echo       Ctrl+C here to stop the API.
echo.
start "" "http://127.0.0.1:%PORT%/"
set "LAMA_SERVICE_PORT=%LAMA_PORT%"
"%MAIN_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT%
echo.
echo [info] API server stopped.
pause
exit /b 0
:python313_missing
echo [error] Python 3.13 is required. Install it or use the packaged Python runtime.
pause
exit /b 1
:python311_missing
echo [error] Python 3.11 is required for LaMa. Install it and relaunch.
pause
exit /b 1
:no_port
echo [error] No free API port in the configured range.
pause
exit /b 1
:no_lama_port
echo [error] No free local port for the LaMa service.
pause
exit /b 1
:lama_start_error
echo [error] The LaMa service did not become ready. Check its console window.
pause
exit /b 1
:frontend_error
echo [error] Frontend build failed and no valid dist bundle is available.
pause
exit /b 1
:setup_error
echo [error] Runtime setup failed. See the message above.
pause
exit /b 1
