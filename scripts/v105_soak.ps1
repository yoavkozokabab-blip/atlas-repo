# Atlas v1.0.5 — installed-candidate soak.
# Drives the REAL installed exe over its authenticated API for -Minutes:
# repeated repository (demo pack) switching, navigation/workflow cycles,
# analytics toggling, scan cancellation, one mid-soak restart, and
# memory/handle sampling. Writes a JSON report.
param(
    [Parameter(Mandatory = $true)][string]$InstallDir,
    [Parameter(Mandatory = $true)][string]$DataDir,
    [int]$Minutes = 20,
    [string]$ReportPath = (Join-Path $env:TEMP "atlas_v105_soak.json")
)

$ErrorActionPreference = "Stop"

function Start-Atlas {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = Join-Path $InstallDir "Atlas.exe"
    $psi.Arguments = "--no-browser"
    $psi.WorkingDirectory = $InstallDir
    $psi.UseShellExecute = $false
    $psi.EnvironmentVariables["ATLAS_DESKTOP_DATA"] = $DataDir
    $proc = [System.Diagnostics.Process]::Start($psi)
    $descriptor = Join-Path $DataDir "runtime.json"
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-Path $descriptor) {
            try {
                $rt = Get-Content $descriptor -Raw | ConvertFrom-Json
                if ($rt.port) { return @{ proc = $proc; port = [int]$rt.port; token = "$($rt.runtime_token)" } }
            } catch {}
        }
        Start-Sleep -Milliseconds 500
    }
    throw "runtime never came up"
}

function Api($h, [string]$method, [string]$path, $body = $null) {
    $headers = @{ Cookie = "atlas_runtime_token=$($h.token)" }
    try {
        if ($null -ne $body) {
            return Invoke-RestMethod -Uri "http://127.0.0.1:$($h.port)$path" -Method $method -Headers $headers -Body ($body | ConvertTo-Json -Depth 5) -ContentType "application/json" -TimeoutSec 90
        }
        return Invoke-RestMethod -Uri "http://127.0.0.1:$($h.port)$path" -Method $method -Headers $headers -TimeoutSec 90
    } catch { return $null }
}

function Sample($h, $samples, [int]$cycle) {
    try {
        $p = Get-Process -Id $h.proc.Id -ErrorAction Stop
        $samples.Add([ordered]@{
            cycle = $cycle
            at = (Get-Date -Format "HH:mm:ss")
            rss_mb = [Math]::Round($p.WorkingSet64 / 1MB, 1)
            private_mb = [Math]::Round($p.PrivateMemorySize64 / 1MB, 1)
            handles = $p.HandleCount
            threads = $p.Threads.Count
        }) | Out-Null
    } catch {}
}

$h = Start-Atlas
$deadline = (Get-Date).AddMinutes($Minutes)
$samples = New-Object System.Collections.ArrayList
$counters = [ordered]@{ cycles = 0; switches = 0; asks = 0; impacts = 0; failures = 0; cancels = 0; restarts = 0 }
$packs = @("medium", "small")
$questions = @(
    "What breaks if I change services/billing.py?",
    "What are the top architectural risks?",
    "Where is billing handled?",
    "Explain the request flow.",
    "Which files should I read first?"
)
$navRoutes = @("/api/repositories/current/summary", "/api/health", "/api/history", "/api/integrations/mcp/status", "/api/analytics/preferences")

Sample $h $samples 0
$restartDone = $false
while ((Get-Date) -lt $deadline) {
    $cycle = ++$counters.cycles
    # repository switching every 5th cycle
    if ($cycle % 5 -eq 1) {
        $pack = $packs[[int][Math]::Floor($cycle / 5) % 2]
        $r = Api $h "POST" "/api/demo/load" @{ pack = $pack }
        if ($null -eq $r -or -not $r.ok) { $counters.failures++ } else { $counters.switches++ }
    }
    foreach ($route in $navRoutes) { $null = Api $h "GET" $route }
    $q = $questions[$cycle % $questions.Count]
    $a = Api $h "POST" "/api/copilot/ask" @{ question = $q; target = "none"; packet = "compact" }
    if ($null -ne $a -and $a.ok) { $counters.asks++ } else { $counters.failures++ }
    if ($cycle % 3 -eq 0) {
        $imp = Api $h "POST" "/api/planning/impact" @{ target = "services/billing.py" }
        if ($null -ne $imp -and $imp.ok) { $counters.impacts++ } else { $counters.failures++ }
    }
    if ($cycle % 10 -eq 0) {
        # scan cancellation exercise: request a cancel (safe when idle too)
        $null = Api $h "POST" "/api/repositories/current/cancel-scan"
        $counters.cancels++
        # analytics toggle round-trip
        $null = Api $h "POST" "/api/analytics/preferences" @{ opted_out = $true }
        $null = Api $h "POST" "/api/analytics/preferences" @{ opted_out = $false }
    }
    if (-not $restartDone -and (Get-Date) -gt (Get-Date).AddMinutes(0) -and $counters.cycles -ge 40) {
        # one mid-soak restart (runtime interruption + recovery)
        try { Stop-Process -Id $h.proc.Id -Force } catch {}
        Start-Sleep -Seconds 2
        $h = Start-Atlas
        $counters.restarts++
        $restartDone = $true
    }
    if ($cycle % 5 -eq 0) { Sample $h $samples $cycle }
}
Sample $h $samples $counters.cycles

$first = $samples | Select-Object -First 1
$last = $samples | Select-Object -Last 1
$report = [ordered]@{
    generated_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    minutes = $Minutes
    counters = $counters
    rss_start_mb = $first.rss_mb
    rss_end_mb = $last.rss_mb
    handles_start = $first.handles
    handles_end = $last.handles
    samples = $samples
}
$report | ConvertTo-Json -Depth 5 | Out-File -FilePath $ReportPath -Encoding utf8
try { Stop-Process -Id $h.proc.Id -Force } catch {}
Write-Host "SOAK_DONE cycles=$($counters.cycles) failures=$($counters.failures) rss $($first.rss_mb)MB -> $($last.rss_mb)MB handles $($first.handles) -> $($last.handles) report=$ReportPath"
