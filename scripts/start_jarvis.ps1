Param(
    [switch]$StableMode = $true
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

if (-not (Test-Path ".\main.py")) {
    throw "main.py not found in $ProjectRoot"
}

# Core runtime defaults for reliable desktop startup.
$env:PYTHONUTF8 = "1"
$env:HUMAN_CONVERSATIONAL_RUNTIME_ENABLED = "true"
$env:CONVERSATION_CONTINUOUS_MIC_ENABLED = "true"
$env:STT_STREAMING_BUFFER_ENABLED = "true"
$env:TTS_POLICY_TRACE = "true"

if ($StableMode) {
    $env:VOICE_RUNTIME_MODE = "stable"
}

Write-Host "Starting JARVIS from $ProjectRoot"
Write-Host "  VOICE_RUNTIME_MODE=$($env:VOICE_RUNTIME_MODE)"
Write-Host "  STT_STREAMING_BUFFER_ENABLED=$($env:STT_STREAMING_BUFFER_ENABLED)"
Write-Host "  HUMAN_CONVERSATIONAL_RUNTIME_ENABLED=$($env:HUMAN_CONVERSATIONAL_RUNTIME_ENABLED)"

if (Get-Command py -ErrorAction SilentlyContinue) {
    py -3 .\main.py
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    python .\main.py
}
else {
    throw "Python launcher not found (py/python)."
}

