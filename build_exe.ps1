# Builds dist\JARVIS\JARVIS.exe with PyInstaller.
# Usage (from the project folder, with the venv active):  .\build_exe.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m PyInstaller `
    --noconfirm `
    --windowed `
    --name JARVIS `
    --add-data "jarvis\web\static;jarvis\web\static" `
    --collect-all customtkinter `
    --collect-all openwakeword `
    --hidden-import pyttsx3.drivers.sapi5 `
    jarvis_gui.py

Copy-Item config.example.json dist\JARVIS\config.example.json -Force
Write-Host "Built dist\JARVIS\JARVIS.exe"
