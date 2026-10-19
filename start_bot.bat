@echo off
title Yuna Supreme Security Bot
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    echo Starting Yuna Supreme using local .venv...
    ".venv\Scripts\python.exe" app.py
) else if exist "..\Yuna V 7.00\yuna bot\.venv\Scripts\python.exe" (
    echo Starting Yuna Supreme using shared .venv...
    "..\Yuna V 7.00\yuna bot\.venv\Scripts\python.exe" app.py
) else (
    echo Starting Yuna Supreme using system python...
    python app.py
)
pause
