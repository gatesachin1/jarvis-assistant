@echo off
rem Double-click launcher: desktop app + web dashboard.
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m jarvis --web %*
) else (
    python -m jarvis --web %*
)
if errorlevel 1 pause
