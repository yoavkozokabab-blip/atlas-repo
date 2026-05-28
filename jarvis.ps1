param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$JarvisArgs
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (Test-Path $VenvPython) {
    $Python = $VenvPython
} else {
    $Python = "py"
}

Write-Host "JARVIS launcher" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot" -ForegroundColor Cyan

if ($Python -eq "py") {
    Write-Host "Using: py -3 main.py $($JarvisArgs -join ' ')" -ForegroundColor Cyan
    & py -3 main.py @JarvisArgs
} else {
    Write-Host "Using: $Python main.py $($JarvisArgs -join ' ')" -ForegroundColor Cyan
    & $Python main.py @JarvisArgs
}

exit $LASTEXITCODE
