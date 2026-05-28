# Install Python dependencies for local_jarvis
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Write-Host "Done. Copy .env.example to .env if needed."
