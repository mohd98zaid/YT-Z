@echo off
title YT-Z - Local Network Media Server
cd /d "%~dp0"
python main.py --server-only
pause
