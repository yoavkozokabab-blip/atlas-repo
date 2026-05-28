# Create desktop shortcut to run_jarvis.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RunScript = Join-Path $Root "scripts\run_jarvis.ps1"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "JARVIS.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`""
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "Local JARVIS Assistant"
$Shortcut.Save()
Write-Host "Shortcut created: $ShortcutPath"
