@echo off
title YT-Z - Ultimate YouTube Music & Downloader
echo ========================================================
echo         YT-Z: Music Player & 4K Downloader
echo ========================================================
cd /d "%~dp0"

echo [*] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python is not installed or not in PATH. Please install Python 3.10+.
    pause
    exit /b 1
)

echo [*] Launching YT-Z...
python main.py

if %errorlevel% neq 0 (
    echo.
    echo [!] Application exited with an error.
    pause
)
