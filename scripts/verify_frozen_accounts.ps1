# Phase 192 — fresh-install verification of the bundled accounts service.
# Installs Atlas_Setup.exe silently to a temp dir, launches ONLY Atlas.exe, and
# verifies the accounts service comes up on :8788 with register/login working —
# zero manual commands.
$ErrorActionPreference = "Continue"
$root = "C:\J.A.R.V.I.S\local_jarvis"
$setup = Join-Path $root "packaging\installer\output\Atlas_Setup.exe"
$work = Join-Path $env:TEMP "atlas_fresh192"
$installDir = Join-Path $work "App"
$dataDir = Join-Path $work "Data"
$result = [ordered]@{}

function Kill-Atlas {
  Get-CimInstance Win32_Process -Filter "Name='Atlas.exe' OR Name='AtlasAccounts.exe'" -ErrorAction SilentlyContinue |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
  Start-Sleep 1
}

Kill-Atlas
if (Test-Path $work) { try { Remove-Item -Recurse -Force -LiteralPath $work } catch {} }
New-Item -ItemType Directory -Force -Path $installDir, $dataDir | Out-Null

Write-Output "=== [1] Clean silent install ==="
$pi = Start-Process $setup -ArgumentList "/VERYSILENT","/SUPPRESSMSGBOXES","/DIR=$installDir","/NOICONS" -PassThru
$pi.WaitForExit(120000) | Out-Null
$atlasExe = Join-Path $installDir "Atlas.exe"
$acctExe = Join-Path $installDir "accounts\AtlasAccounts.exe"
$result.installed_atlas = Test-Path $atlasExe
$result.installed_accounts = Test-Path $acctExe
Write-Output ("installed Atlas.exe={0}  accounts\AtlasAccounts.exe={1}" -f $result.installed_atlas, $result.installed_accounts)

Write-Output "=== [2] Launch ONLY Atlas.exe (no manual setup) ==="
$env:ATLAS_DESKTOP_DATA = $dataDir   # isolate data for the test
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$pa = Start-Process $atlasExe -ArgumentList "--no-browser" -PassThru -WorkingDirectory $installDir

Write-Output "=== [3] Verify :8788/health within 15s ==="
$health = $false
while ($sw.Elapsed.TotalSeconds -lt 15) {
  try { $r = Invoke-WebRequest "http://127.0.0.1:8788/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; if ($r.StatusCode -eq 200) { $health=$true; break } } catch {}
  Start-Sleep -Milliseconds 500
}
$result.health_seconds = [math]::Round($sw.Elapsed.TotalSeconds,1)
$result.health_ok = $health
Write-Output ("health_ok={0} in {1}s" -f $health, $result.health_seconds)

if ($health) {
  Write-Output "=== [4] Register via the installed product ==="
  $email = "fresh.$([guid]::NewGuid().ToString('N').Substring(0,6))@example.com"
  $body = @{ email=$email; password="SecurePass1!"; device_id=("b"*32); app_version="0.1.0-beta"; platform="windows"; beta_profile=@{ currently_developer=$true; project_use="work"; company_size="2_10"; developer_experience="3_5"; primary_role="full_stack"; coding_tools=@("claude"); repo_size="small"; atlas_help=@("planning_changes") } } | ConvertTo-Json
  try { $reg = Invoke-WebRequest "http://127.0.0.1:8788/auth/register" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing; $result.register_status = $reg.StatusCode } catch { $result.register_status = "ERR: $($_.Exception.Message)" }
  Write-Output ("register_status={0}" -f $result.register_status)

  Write-Output "=== [5] Login via the installed product ==="
  $lbody = @{ email=$email; password="SecurePass1!"; device_id=("b"*32); app_version="0.1.0-beta"; platform="windows" } | ConvertTo-Json
  try { $lg = Invoke-WebRequest "http://127.0.0.1:8788/auth/login" -Method POST -Body $lbody -ContentType "application/json" -UseBasicParsing; $result.login_status = $lg.StatusCode } catch {
    # pending accounts may 403 on login (expected) — capture status
    $result.login_status = if ($_.Exception.Response) { [int]$_.Exception.Response.StatusCode } else { "ERR" }
  }
  Write-Output ("login_status={0} (pending accounts return 403 by design)" -f $result.login_status)

  Write-Output "=== [6] Desktop proxy (8777 -> 8788) register path ==="
  try { $ds = Invoke-WebRequest "http://127.0.0.1:8777/api/accounts/service-status" -TimeoutSec 4 -UseBasicParsing; $result.desktop_proxy = $ds.StatusCode } catch { $result.desktop_proxy = "ERR" }
  Write-Output ("desktop_service_status={0}" -f $result.desktop_proxy)
}

# Memory overhead of the accounts process
$acctProc = Get-Process -Name AtlasAccounts -ErrorAction SilentlyContinue | Select-Object -First 1
if ($acctProc) { $result.accounts_rss_mb = [math]::Round($acctProc.WorkingSet64/1MB,1); Write-Output ("AtlasAccounts RSS: {0} MB" -f $result.accounts_rss_mb) }

Write-Output "=== cleanup ==="
Kill-Atlas
$result | ConvertTo-Json | Out-File -Encoding utf8 (Join-Path $root "reports\phase192_fresh_install_result.json")
Write-Output "RESULT JSON written."
$result.GetEnumerator() | ForEach-Object { Write-Output ("  {0} = {1}" -f $_.Key, $_.Value) }
$overall = $result.installed_atlas -and $result.installed_accounts -and $result.health_ok -and ($result.register_status -eq 201)
Write-Output ("OVERALL: {0}" -f $(if($overall){"PASS"}else{"FAIL"}))