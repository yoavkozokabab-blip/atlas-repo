# One-click JARVIS launcher (Phase 30)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
Write-Host "JARVIS — text console. Tray: scripts\run_jarvis_tray.ps1" -ForegroundColor Cyan
py -3 main.py
