# Builds dist\JARVIS\JARVIS.exe and dist\JARVIS-<version>-win64.zip with PyInstaller.
# Usage (from the project folder):  .\build_exe.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = if (Test-Path ".venv\Scripts\python.exe") { ".venv\Scripts\python.exe" } else { "python" }
$version = & $python -c "import jarvis; print(jarvis.__version__)"

New-Item -ItemType Directory -Force build | Out-Null
& $python -c "from jarvis.ui.icon import save_ico; save_ico('build/jarvis.ico')"

& $python -m PyInstaller `
    --noconfirm `
    --windowed `
    --name JARVIS `
    --icon build\jarvis.ico `
    --add-data "jarvis\web\static;jarvis\web\static" `
    --collect-all customtkinter `
    --collect-all openwakeword `
    --collect-all piper `
    --collect-all faster_whisper `
    --collect-all ctranslate2 `
    --collect-all onnxruntime `
    --collect-submodules uvicorn `
    --collect-submodules pystray `
    --hidden-import pyttsx3.drivers.sapi5 `
    jarvis_gui.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Copy-Item config.example.json dist\JARVIS\config.example.json -Force
Copy-Item install.ps1 dist\JARVIS\install.ps1 -Force
Copy-Item README.md dist\JARVIS\README.md -Force

$zip = "dist\JARVIS-$version-win64.zip"
if (Test-Path $zip) { Remove-Item $zip }
Compress-Archive -Path dist\JARVIS\* -DestinationPath $zip

Write-Host "Built dist\JARVIS\JARVIS.exe and $zip"
