# JARVIS tray launcher — background quiet mode (no console window when possible)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $Root

$LogDir = Join-Path $Root "reports\jarvis_logs"
if (-not (Test-Path -LiteralPath $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
$LogFile = Join-Path $LogDir ("jarvis_tray_{0:yyyyMMdd}.log" -f (Get-Date))

function Write-Log($Message) {
    $line = "[{0:yyyy-MM-dd HH:mm:ss}] {1}" -f (Get-Date), $Message
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
}

Write-Log "Starting JARVIS tray (background) from $Root"

$Args = @("main.py", "--tray", "--voice", "--speak", "--wakeword")
$VenvPythonw = Join-Path $Root ".venv\Scripts\pythonw.exe"
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (Test-Path -LiteralPath $VenvPythonw) {
    Write-Log "Launching with pythonw (no console): $VenvPythonw"
    $proc = Start-Process -FilePath $VenvPythonw -ArgumentList $Args -WorkingDirectory $Root -WindowStyle Hidden -PassThru
    Write-Log "Started PID $($proc.Id)"
    exit 0
}

if (Test-Path -LiteralPath $VenvPython) {
    Write-Log "pythonw missing; using venv python with hidden window"
    $proc = Start-Process -FilePath $VenvPython -ArgumentList $Args -WorkingDirectory $Root -WindowStyle Hidden -PassThru
    Write-Log "Started PID $($proc.Id)"
    exit 0
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    Write-Log "Using py -3 with hidden window"
    $proc = Start-Process -FilePath "py" -ArgumentList (@("-3") + $Args) -WorkingDirectory $Root -WindowStyle Hidden -PassThru
    Write-Log "Started PID $($proc.Id)"
    exit 0
}

Write-Log "WARNING: falling back to visible python"
& python @Args 2>&1 | ForEach-Object { Write-Log $_ }
exit $LASTEXITCODE
