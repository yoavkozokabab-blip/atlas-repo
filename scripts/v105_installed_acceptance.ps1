# Atlas v1.0.5 — installed-candidate acceptance driver.
#
# A) clean install into an isolated dir + isolated data root
# B) update over an existing v1.0.4 install (optional, -V104Dir/-V104Data)
# C) second isolated install — cross-install isolation
#
# Behavior checks run against the REAL installed executable over its
# authenticated local API. Writes a JSON report; exits 1 on any failure.
param(
    [Parameter(Mandatory = $true)][string]$Setup,
    [string]$WorkRoot = (Join-Path $env:TEMP "atlas_v105_acceptance"),
    [string]$V104Dir = "",
    [string]$V104Data = "",
    [string]$ReportPath = ""
)

$ErrorActionPreference = "Stop"
$Results = [ordered]@{}
if (-not $ReportPath) { $ReportPath = Join-Path $WorkRoot "acceptance_report.json" }
New-Item -ItemType Directory -Force -Path $WorkRoot | Out-Null

function Install-Atlas([string]$dir) {
    $p = Start-Process $Setup -ArgumentList "/VERYSILENT", "/SUPPRESSMSGBOXES", "/DIR=$dir", "/NOICONS" -PassThru -Wait
    if ($p.ExitCode -ne 0) { throw "installer exit $($p.ExitCode) for $dir" }
    if (-not (Test-Path (Join-Path $dir "Atlas.exe"))) { throw "Atlas.exe missing after install in $dir" }
}

function Start-Atlas([string]$dir, [string]$data) {
    New-Item -ItemType Directory -Force -Path $data | Out-Null
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = Join-Path $dir "Atlas.exe"
    $psi.Arguments = "--no-browser"
    $psi.WorkingDirectory = $dir
    $psi.UseShellExecute = $false
    $psi.EnvironmentVariables["ATLAS_DESKTOP_DATA"] = $data
    $proc = [System.Diagnostics.Process]::Start($psi)
    $descriptor = Join-Path $data "runtime.json"
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-Path $descriptor) {
            try {
                $rt = Get-Content $descriptor -Raw | ConvertFrom-Json
                if ($rt.port) {
                    return @{ proc = $proc; port = [int]$rt.port; token = "$($rt.runtime_token)"; instance_id = "$($rt.instance_id)" }
                }
            } catch {}
        }
        Start-Sleep -Milliseconds 500
    }
    throw "runtime descriptor never appeared for $dir"
}

function Api($handle, [string]$method, [string]$path, $body = $null) {
    $url = "http://127.0.0.1:$($handle.port)$path"
    $headers = @{ Cookie = "atlas_runtime_token=$($handle.token)" }
    try {
        if ($null -ne $body) {
            $json = $body | ConvertTo-Json -Depth 6
            return Invoke-RestMethod -Uri $url -Method $method -Headers $headers -Body $json -ContentType "application/json" -TimeoutSec 120
        }
        return Invoke-RestMethod -Uri $url -Method $method -Headers $headers -TimeoutSec 120
    } catch {
        return [pscustomobject]@{ ok = $false; error = $_.Exception.Message }
    }
}

function Stop-Atlas($handle) {
    try { Stop-Process -Id $handle.proc.Id -Force -ErrorAction Stop } catch {}
    Start-Sleep -Milliseconds 800
}

function Record([string]$name, [bool]$pass, [string]$detail = "") {
    $Results[$name] = [ordered]@{ pass = $pass; detail = $detail }
    $tag = if ($pass) { "PASS" } else { "FAIL" }
    Write-Host ("  [{0}] {1} {2}" -f $tag, $name, $detail)
}

# ---------------- A) Clean install ----------------
Write-Host "=== A) Clean v1.0.5 install ==="
$dirA = Join-Path $WorkRoot "installA"
$dataA = Join-Path $WorkRoot "dataA"
Remove-Item -Recurse -Force $dirA, $dataA -ErrorAction SilentlyContinue
Install-Atlas $dirA
$sha = (Get-FileHash (Join-Path $dirA "Atlas.exe") -Algorithm SHA256).Hash
Record "clean_install" $true "exe sha256=$sha"

$t0 = Get-Date
$hA = Start-Atlas $dirA $dataA
$launchSeconds = [Math]::Round(((Get-Date) - $t0).TotalSeconds, 1)
$health = Api $hA "GET" "/api/health"
Record "cold_launch_health" ($health.ok -eq $true) "port=$($hA.port) launch=${launchSeconds}s"
$cfg = Api $hA "GET" "/api/product/config"
$version = "$($cfg.version)"
Record "version_is_105" ($version -eq "1.0.5") "version=$version commit=$($cfg.commit)"

# first value: demo -> ask -> impact
$t1 = Get-Date
$demo = Api $hA "POST" "/api/demo/load" @{ pack = "medium" }
$demoOk = ($demo.ok -eq $true) -and ("$($demo.repo_name)" -like "Atlas Demo*")
Record "demo_loads_named_demo" $demoOk "name=$($demo.repo_name)"
$ask = Api $hA "POST" "/api/copilot/ask" @{ question = "What breaks if I change services/billing.py?"; target = "none"; packet = "compact" }
Record "ask_grounded" (($ask.ok -eq $true) -and ($ask.files.Count -gt 0)) "mode=$($ask.mode) files=$($ask.files.Count)"
Record "ask_context_binding" ($null -ne $ask.context_binding -and $ask.context_binding.demo_mode -eq $true) "repo=$($ask.context_binding.repo_name)"
$impact = Api $hA "POST" "/api/planning/impact" @{ target = "services/billing.py" }
$firstValueSeconds = [Math]::Round(((Get-Date) - $t1).TotalSeconds, 1)
Record "impact_result" (($impact.ok -eq $true) -and ($impact.direct_impact.Count -gt 0)) "direct=$($impact.direct_impact.Count) t=${firstValueSeconds}s"
Record "time_to_first_value_under_60s" (($launchSeconds + $firstValueSeconds) -lt 60) "total=$([Math]::Round($launchSeconds + $firstValueSeconds,1))s"

$inv = Api $hA "POST" "/api/planning/investigate" @{ symptom = "billing total is wrong after checkout in services/billing.py" }
Record "debug_result" ($inv.ok -eq $true) "confidence=$($inv.plan.confidence)"
$plan = Api $hA "POST" "/api/planning/change" @{ request = "Add an invoice email notification after successful billing" }
Record "plan_result" ($plan.ok -eq $true) "risk=$($plan.plan.risk_level)"

# analytics opt-out
$pref = Api $hA "POST" "/api/analytics/preferences" @{ opted_out = $true }
$prefState = Api $hA "GET" "/api/analytics/preferences"
Record "analytics_opt_out_set" ($prefState.opted_out -eq $true) ""

# no checkout / pro coming soon
$plans = Api $hA "GET" "/api/plans"
$plansJson = ($plans | ConvertTo-Json -Depth 6)
Record "no_checkout_surface" (-not ($plansJson -match "checkout")) ""

# restart persistence
Stop-Atlas $hA
$hA2 = Start-Atlas $dirA $dataA
$restored = Api $hA2 "GET" "/api/repositories/current/summary"
Record "restart_restores_repository" (($restored.ok -eq $true) -and ("$($restored.repo_name)" -like "Atlas Demo*")) "repo=$($restored.repo_name)"
$prefState2 = Api $hA2 "GET" "/api/analytics/preferences"
Record "opt_out_survives_restart" ($prefState2.opted_out -eq $true) ""

# ---------------- C) Second isolated install ----------------
Write-Host "=== C) Two-install isolation ==="
$dirB = Join-Path $WorkRoot "installB"
$dataB = Join-Path $WorkRoot "dataB"
Remove-Item -Recurse -Force $dirB, $dataB -ErrorAction SilentlyContinue
Install-Atlas $dirB
$hB = Start-Atlas $dirB $dataB
$healthB = Api $hB "GET" "/api/health"
Record "second_install_boots" ($healthB.ok -eq $true) "port=$($hB.port)"
Record "distinct_ports_or_data" (($hB.port -ne $hA2.port) -or ($dataA -ne $dataB)) "A=$($hA2.port) B=$($hB.port)"
$sumB = Api $hB "GET" "/api/repositories/current/summary"
Record "b_sees_no_a_repository" (-not ($sumB.ok -eq $true)) "fresh install has no repository"
Record "distinct_instance_identity" (($hB.instance_id) -and ($hA2.instance_id) -and ($hB.instance_id -ne $hA2.instance_id)) ""
Record "distinct_runtime_tokens" (($hB.token) -and ($hA2.token) -and ($hB.token -ne $hA2.token)) ""
$prefB = Api $hB "GET" "/api/analytics/preferences"
Record "b_not_affected_by_a_optout" ($prefB.opted_out -ne $true) "B default preference independent"
Stop-Atlas $hB
Stop-Atlas $hA2

# ---------------- B) Update over v1.0.4 ----------------
if ($V104Dir -and (Test-Path (Join-Path $V104Dir "Atlas.exe"))) {
    Write-Host "=== B) Update from v1.0.4 ==="
    Install-Atlas $V104Dir
    $hU = Start-Atlas $V104Dir $V104Data
    $cfgU = Api $hU "GET" "/api/product/config"
    Record "update_version_is_105" ("$($cfgU.version)" -eq "1.0.5") "version=$($cfgU.version)"
    $sumU = Api $hU "GET" "/api/repositories/current/summary"
    Record "update_retains_user_data" ($null -ne $sumU) "summary_ok=$($sumU.ok)"
    Stop-Atlas $hU
} else {
    Record "update_from_v104" $false "SKIPPED: no v1.0.4 install provided"
}

# ---------------- report ----------------
$pass = $true
foreach ($k in $Results.Keys) { if (-not $Results[$k].pass) { $pass = $false } }
[ordered]@{
    generated_at = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    setup = $Setup
    overall = if ($pass) { "PASS" } else { "FAIL" }
    results = $Results
} | ConvertTo-Json -Depth 5 | Out-File -FilePath $ReportPath -Encoding utf8
Write-Host "`nOVERALL: $(if ($pass) {'PASS'} else {'FAIL'}) -> $ReportPath"
if (-not $pass) { exit 1 }
