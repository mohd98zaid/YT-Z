@echo off
title YT-Z - Music Player & 4K Downloader
cd /d "%~dp0"

:: Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python was not found in PATH. Please install Python 3.10+.
    pause
    exit /b 1
)

:: If argument passed explicitly
if /i "%1"=="browser" goto launch_browser
if /i "%1"=="b" goto launch_browser
if /i "%1"=="server" goto launch_server
if /i "%1"=="s" goto launch_server

:launch_app
cls
echo ========================================================
echo        YT-Z: Music Player ^& 4K Downloader
echo ========================================================
echo.
echo [*] Launching dedicated native app...
echo.

:: Launch the dedicated app in the background
start "YT-Z Dedicated App" python main.py

:: Short pause to let backend and window initialize
timeout /t 2 /nobreak >nul

:action_loop
cls
echo ========================================================
echo        YT-Z: Music Player ^& 4K Downloader
echo ========================================================
echo.
echo   [✓] Dedicated Native Desktop App is running!
echo   [✓] Local Stream URL:   http://127.0.0.1:47892
echo.
echo --------------------------------------------------------
echo   Actions:
echo.
echo   [O] Open in Web Browser (Chrome / Edge / Firefox)
echo   [R] Restart Dedicated App
echo   [Q] Quit ^& Stop YT-Z
echo --------------------------------------------------------
echo.
set "choice="
set /p choice="Enter an action [O / R / Q] (Default: Q): "

if /i "%choice%"=="o" (
    echo [*] Opening in default web browser...
    start http://127.0.0.1:47892
    goto action_loop
)

if /i "%choice%"=="r" (
    echo.
    echo [*] Restarting dedicated app...
    taskkill /f /fi "WINDOWTITLE eq YT-Z Dedicated App*" >nul 2>nul
    timeout /t 1 /nobreak >nul
    goto launch_app
)

if /i "%choice%"=="q" goto do_quit
if "%choice%"=="" goto do_quit

goto action_loop

:launch_browser
echo.
echo [*] Starting YT-Z in Web Browser...
python main.py --browser
goto end

:launch_server
echo.
echo [*] Starting YT-Z Local Network Media Server...
python main.py --server-only
goto end

:do_quit
echo.
echo [*] Shutting down YT-Z...
taskkill /f /fi "WINDOWTITLE eq YT-Z Dedicated App*" >nul 2>nul
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":47892" ^| findstr "LISTENING"') do (
    taskkill /f /pid %%a >nul 2>nul
)
echo [✓] YT-Z stopped cleanly.
exit /b 0

:end
if %errorlevel% neq 0 (
    echo.
    echo [!] Application exited with an error.
    pause
)
