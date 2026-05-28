# Phase 68 — one-click alpha launcher for friend & family testing
Param(
    [switch]$SkipBrowserCheck,
    [switch]$TextOnly
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

function Write-Step($msg) { Write-Host "[alpha] $msg" }

function Fail($msg, $hint) {
    Write-Host ""
    Write-Host "ALPHA LAUNCH FAILED" -ForegroundColor Red
    Write-Host $msg -ForegroundColor Red
    if ($hint) { Write-Host $hint -ForegroundColor Yellow }
    exit 1
}

Write-Step "JARVIS Friend & Family Alpha Launcher"
Write-Step "Project: $ProjectRoot"

# Recommended env for alpha
$env:ALPHA_MODE = "true"
$env:DEVELOPER_MODE = "false"
$env:PYTHONUTF8 = "1"
$env:MEMORY_ENABLED = "true"
$env:SCREEN_UNDERSTANDING_ENABLED = "true"
$env:COMPUTER_CONTROL_ENABLED = "false"
$env:DESKTOP_OPERATOR_SAFE_MODE = "true"
$env:PATCH_APPLY_ENABLED = "false"
$env:INTEGRATIONS_EMAIL_MODE = "mock"
$env:INTEGRATIONS_CALENDAR_MODE = "mock"
$env:VOICE_RUNTIME_MODE = "stable"
$env:HUMAN_CONVERSATIONAL_RUNTIME_ENABLED = "true"
$env:ALPHA_SUPPRESS_DEV_NOTIFICATIONS = "true"

if (-not (Test-Path ".\main.py")) {
    Fail "main.py not found." "Run from local_jarvis folder."
}

# Python version
$pyCmd = $null
if (Get-Command py -ErrorAction SilentlyContinue) { $pyCmd = @("py", "-3") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { $pyCmd = @("python") }
else {
    Fail "Python not found." "Install Python 3.11+ from python.org (not Windows Store stub)."
}

$verOut = & $pyCmd[0] $pyCmd[1..99] -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
$verParts = $verOut.Trim().Split(".")
$major = [int]$verParts[0]
$minor = [int]$verParts[1]
if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
    Fail "Python $verOut is too old." "Requires Python 3.10 or newer."
}
Write-Step "Python $verOut OK"

# Required packages
$pkgCheck = @"
import importlib
required = ['sounddevice', 'PIL', 'playwright']
missing = []
for name in required:
    try:
        importlib.import_module(name if name != 'PIL' else 'PIL')
    except ImportError:
        missing.append(name)
if missing:
    raise SystemExit('MISSING:' + ','.join(missing))
print('PACKAGES_OK')
"@
$pkgResult = & $pyCmd[0] $pyCmd[1..99] -c $pkgCheck 2>&1
if ($LASTEXITCODE -ne 0 -or "$pkgResult" -notmatch "PACKAGES_OK") {
    Fail "Missing Python packages." "Run: pip install -r requirements.txt"
}
Write-Step "Core packages OK"

# Playwright
if (-not $SkipBrowserCheck) {
    $pwCheck = @"
try:
    from playwright.sync_api import sync_playwright
    print('PLAYWRIGHT_OK')
except Exception as e:
    raise SystemExit(str(e))
"@
    $pwResult = & $pyCmd[0] $pyCmd[1..99] -c $pwCheck 2>&1
    if ($LASTEXITCODE -ne 0) {
        Fail "Playwright not installed." "Run: pip install playwright ; playwright install chromium"
    }
    Write-Step "Playwright OK"

    $chromiumCheck = @"
from pathlib import Path
import playwright
root = Path(playwright.__file__).resolve().parent
found = any(root.rglob('chrome.exe')) or any(root.rglob('chromium'))
print('CHROMIUM_OK' if found else 'CHROMIUM_MISSING')
"@
    $chResult = & $pyCmd[0] $pyCmd[1..99] -c $chromiumCheck 2>&1
    if ("$chResult" -match "CHROMIUM_MISSING") {
        Fail "Chromium browser not installed for Playwright." "Run: playwright install chromium"
    }
    Write-Step "Chromium OK"
}

# Microphone
$micCheck = @"
from voice.microphone import check_microphone_available
check_microphone_available()
print('MIC_OK')
"@
$micResult = & $pyCmd[0] $pyCmd[1..99] -c $micCheck 2>&1
if ($LASTEXITCODE -ne 0) {
    Fail "Microphone check failed." "$micResult`nGrant mic access in Windows Settings > Privacy."
}
Write-Step "Microphone OK"

# TTS path
$ttsCheck = @"
from voice.pyttsx3_completion import run_direct_tts_isolated_test
r = run_direct_tts_isolated_test('Alpha launcher TTS check.')
print('TTS_OK' if r.ok else 'TTS_FAIL')
"@
$ttsResult = & $pyCmd[0] $pyCmd[1..99] -c $ttsCheck 2>&1
if ($LASTEXITCODE -ne 0 -or "$ttsResult" -notmatch "TTS_OK") {
    Fail "TTS/speaker path failed." "Check default audio output device and pyttsx3."
}
Write-Step "TTS/speaker OK"

Write-Step "Starting JARVIS (ALPHA_MODE=true)..."
if ($TextOnly) {
    & $pyCmd[0] $pyCmd[1..99] .\main.py --text --speak --wakeword
}
else {
    & $pyCmd[0] $pyCmd[1..99] .\main.py --tray --voice --speak --wakeword
}
