# Capture screenshots of the Atlas installer running-application dialogs.
# Launches the verification harness (RunningAppFlowTest.exe) for each dialog
# state, captures the dialog window, then closes the harness.
$ErrorActionPreference = "Stop"
$Root = "C:\J.A.R.V.I.S\local_jarvis"
$Harness = Join-Path $Root "packaging\installer\_verify\RunningAppFlowTest.exe"
$OutDir = Join-Path $Root "reports\installer_update_flow"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win {
  [DllImport("user32.dll", CharSet=CharSet.Auto)] public static extern IntPtr FindWindow(string c, string n);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr h);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

function Capture-Window([IntPtr]$h, [string]$path) {
  [Win]::SetForegroundWindow($h) | Out-Null
  Start-Sleep -Milliseconds 500
  $r = New-Object Win+RECT
  [Win]::GetWindowRect($h, [ref]$r) | Out-Null
  $w = $r.Right - $r.Left; $ht = $r.Bottom - $r.Top
  if ($w -le 0 -or $ht -le 0) { throw "bad rect for $path" }
  Add-Type -AssemblyName System.Drawing
  $bmp = New-Object System.Drawing.Bitmap $w, $ht
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.CopyFromScreen($r.Left, $r.Top, 0, 0, (New-Object System.Drawing.Size($w, $ht)))
  $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose(); $bmp.Dispose()
  Write-Host "  saved $path ($w x $ht)"
}

function Run-State([string]$state, [string]$title, [string]$outName) {
  Write-Host "== state: $state =="
  $p = Start-Process -FilePath $Harness -ArgumentList "/state=$state" -PassThru
  Start-Sleep -Milliseconds 1500
  $h = [IntPtr]::Zero
  for ($i = 0; $i -lt 60; $i++) {
    if ($title) { $h = [Win]::FindWindow($null, $title) }
    if ($h -eq [IntPtr]::Zero) { $h = [Win]::GetForegroundWindow() }
    if ($h -ne [IntPtr]::Zero -and [Win]::IsWindow($h)) { break }
    Start-Sleep -Milliseconds 250
  }
  if ($h -eq [IntPtr]::Zero) { Write-Host "  WARN: window not found for $state" }
  else { Capture-Window $h (Join-Path $OutDir $outName) }
  # Inno relaunches as RunningAppFlowTest.tmp — kill both the launcher and child.
  Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -like "RunningAppFlowTest*" } |
    Stop-Process -Force -ErrorAction SilentlyContinue
  Start-Sleep -Milliseconds 500
}

Run-State "normal"  "Atlas is currently running" "01_atlas_running_dialog.png"
Run-State "failed"  "Atlas is currently running" "02_close_failed_dialog.png"
Run-State "taskmgr" $null                          "03_task_manager_instructions.png"

Write-Host "DONE -> $OutDir"
Get-ChildItem $OutDir -Filter *.png | ForEach-Object { Write-Host ("  {0} ({1:N0} bytes)" -f $_.Name, $_.Length) }
