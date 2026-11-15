@echo off
title YT-Z - Ultimate YouTube Music & Downloader
cd /d "%~dp0"

echo ========================================================
echo        YT-Z: Music Player & 4K Downloader
echo ========================================================

:: Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo [!] Python was not found in PATH. Please install Python 3.10+.
    pause
    exit /b 1
)

:: If user passed argument like "browser" or "b"
if /i "%1"=="browser" goto launch_browser
if /i "%1"=="b" goto launch_browser
if /i "%1"=="window" goto launch_window
if /i "%1"=="w" goto launch_window

:menu
echo.
echo   [1] Launch Native Desktop App [Default]
echo   [2] Launch in Web Browser (Chrome / Edge / Firefox)
echo   [3] Exit
echo.
set "choice="
set /p choice="Select an option [1-3] (Default: 1): "

if "%choice%"=="" set choice=1
if "%choice%"=="1" goto launch_window
if "%choice%"=="2" goto launch_browser
if "%choice%"=="3" exit /b 0

:launch_window
echo.
echo [*] Starting YT-Z Native Desktop App...
python main.py
goto end

:launch_browser
echo.
echo [*] Starting YT-Z in Web Browser...
python main.py --browser
goto end

:end
if %errorlevel% neq 0 (
    echo.
    echo [!] Application exited with an error.
    pause
)
