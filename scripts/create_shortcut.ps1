# Create desktop shortcut to run_atlas.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$RunScript = Join-Path $Root "scripts\run_atlas.ps1"
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Atlas.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = "powershell.exe"
$Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$RunScript`""
$Shortcut.WorkingDirectory = $Root
$Shortcut.Description = "Local Atlas Assistant"
$Shortcut.Save()
Write-Host "Shortcut created: $ShortcutPath"
