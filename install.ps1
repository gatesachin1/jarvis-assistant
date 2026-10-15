# Installs JARVIS for the current user (no admin rights needed).
# Run from the unzipped release folder:
#   powershell -ExecutionPolicy Bypass -File install.ps1 [-StartWithWindows] [-Uninstall]

param(
    [switch]$StartWithWindows,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$target = Join-Path $env:LOCALAPPDATA "Programs\JARVIS"
$shortcut = Join-Path ([Environment]::GetFolderPath("Programs")) "JARVIS.lnk"
$desktopShortcut = Join-Path ([Environment]::GetFolderPath("Desktop")) "JARVIS.lnk"

if ($Uninstall) {
    if (Test-Path "$target\JARVIS.exe") { & "$target\JARVIS.exe" --remove-startup | Out-Null }
    Remove-Item $shortcut, $desktopShortcut -ErrorAction SilentlyContinue
    Remove-Item $target -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "JARVIS uninstalled. (Your data folder was inside $target and has been removed.)"
    return
}

if (-not (Test-Path "$PSScriptRoot\JARVIS.exe")) {
    throw "Run this script from the unzipped JARVIS folder (JARVIS.exe not found next to it)."
}

New-Item -ItemType Directory -Force $target | Out-Null
# Keep the user's config.json, data\ and logs\ when upgrading.
robocopy $PSScriptRoot $target /E /NFL /NDL /NJH /NJS /XF config.json /XD data logs | Out-Null

$shell = New-Object -ComObject WScript.Shell
foreach ($path in @($shortcut, $desktopShortcut)) {
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = "$target\JARVIS.exe"
    $link.Arguments = "--web"
    $link.WorkingDirectory = $target
    $link.IconLocation = "$target\JARVIS.exe,0"
    $link.Save()
}

if ($StartWithWindows) {
    & "$target\JARVIS.exe" --install-startup | Out-Null
}

Write-Host "JARVIS installed to $target"
Write-Host "Start it from the Start menu or the desktop shortcut."
