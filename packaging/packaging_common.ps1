# Shared path resolution and build guards for Atlas packaging scripts.

function Get-PackagingScriptDir {
    if ($PSScriptRoot) { return $PSScriptRoot }
    if ($PSCommandPath) { return (Split-Path -Parent $PSCommandPath) }
    throw @"
Cannot resolve packaging script directory (`$PSScriptRoot is null).
Run the script directly, for example:
  .\packaging\pyinstaller\build_atlas_exe.ps1
  .\packaging\installer\installer_build.ps1
"@
}

function Get-RepoRootFrom {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptDir,
        [int]$LevelsUp = 2
    )
    if (-not $ScriptDir) {
        throw "Get-RepoRootFrom: ScriptDir is null."
    }
    $dir = $ScriptDir
    for ($i = 0; $i -lt $LevelsUp; $i++) {
        $parent = Split-Path -Parent $dir
        if (-not $parent) {
            throw "Cannot walk up $LevelsUp level(s) from script dir '$ScriptDir' (stopped at '$dir')."
        }
        $dir = $parent
    }
    $resolved = Resolve-Path -LiteralPath $dir -ErrorAction Stop
    return $resolved.Path
}

function Join-PathSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Base,
        [Parameter(Mandatory = $true)]
        [string]$Child
    )
    if ([string]::IsNullOrWhiteSpace($Base)) {
        throw "Join-PathSafe: base path is null or empty (child: $Child)."
    }
    return (Join-Path $Base $Child)
}

function Assert-AtlasBuildRoot {
    param([Parameter(Mandatory = $true)][string]$Root)
    $index = Join-Path $Root "atlas_desktop\static\index.html"
    if (-not (Test-Path -LiteralPath $index)) {
        throw "Missing atlas_desktop static UI at $index"
    }
    $gitRoot = (& git -C $Root rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $gitRoot) {
        throw "Atlas packaging requires a Git worktree: $Root"
    }
    $resolvedRoot = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
    $resolvedGitRoot = (Resolve-Path -LiteralPath $gitRoot).Path.TrimEnd('\')
    if ($resolvedRoot -ne $resolvedGitRoot) {
        throw "Packaging root does not match the Git worktree root: $resolvedRoot (git: $resolvedGitRoot)"
    }
    & git -C $Root merge-base --is-ancestor 135d93d3488d4d6216018dcdeaa71ec64662d91e HEAD 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Atlas packaging requires a checkout descended from persistence baseline 135d93d3."
    }
    $dirtySource = @(& git -C $Root status --porcelain=v1 --untracked-files=all -- atlas_desktop builder_core accounts_service 2>$null)
    if ($LASTEXITCODE -ne 0) {
        throw "Could not verify Atlas source cleanliness at $Root"
    }
    if ($dirtySource.Count -gt 0) {
        throw @"
Atlas packaged source is dirty. Commit or remove scoped source changes before building:
$($dirtySource -join "`n")
"@
    }
}

function Find-StagedIndexHtml {
    param([Parameter(Mandatory = $true)][string]$StagingRoot)
    $direct = Join-Path $StagingRoot "_internal\atlas_desktop\static\index.html"
    if (Test-Path -LiteralPath $direct) { return $direct }
    $found = Get-ChildItem -Path $StagingRoot -Recurse -Filter "index.html" -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match "atlas_desktop\\static\\index\.html$" } |
        Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

function Test-HnLaunchUxPayload {
    param([Parameter(Mandatory = $true)][string]$IndexPath)
    $html = Get-Content -LiteralPath $IndexPath -Raw -ErrorAction Stop
    $issues = @()
    if ($html -notmatch 'data-view="ask"[^>]*>Ask</button>') { $issues += "nav missing Ask" }
    if ($html -notmatch 'data-view="center"[^>]*>Graph</button>') { $issues += "nav missing Graph" }
    foreach ($view in @("memory", "files", "agents", "diagnostics", "settings")) {
        if ($html -notmatch ('id="view-' + $view + '"')) { $issues += "workspace missing $view" }
    }
    if ($html -match ">Repository Context<") { $issues += "nav still has Repository Context (old UI)" }
    if ($html -notmatch "Load sample repository") { $issues += "home missing Load sample repository" }
    if ($html -notmatch 'data-atlas-version|Atlas v1\.0\.[0-9]+') { $issues += "missing launch build marker" }
    return $issues
}

function Find-InnoSetupCompiler {
    param([string]$Root)
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($env:ATLAS_INNO_COMPILER) {
        $candidates.Add($env:ATLAS_INNO_COMPILER)
    }
    if ($Root) {
        $candidates.Add((Join-Path $Root ".phase152_inno\ISCC.exe"))
        $candidates.Add((Join-Path $Root ".phase150_inno\ISCC.exe"))
    }
    $pf86 = ${env:ProgramFiles(x86)}
    if ($pf86) { $candidates.Add((Join-Path $pf86 "Inno Setup 6\ISCC.exe")) }
    if ($env:ProgramFiles) { $candidates.Add((Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")) }
    $candidates.Add("ISCC.exe")
    foreach ($path in $candidates) {
        if ($path -and (Test-Path -LiteralPath $path -ErrorAction SilentlyContinue)) {
            return (Resolve-Path -LiteralPath $path).Path
        }
    }
    return $null
}

function Get-AtlasProductVersion {
    <#
        The one place packaging reads the product version from. Everything the
        build emits  -  installer filename, Inno version defines, the executable
        version resource, build_info.json  -  must trace back to this single
        PRODUCT_VERSION so no two artifacts can disagree about what they are.
    #>
    param([Parameter(Mandatory = $true)][string]$Root)
    $productFile = Join-Path $Root "atlas_desktop\product_info.py"
    if (-not (Test-Path -LiteralPath $productFile)) {
        throw "Cannot resolve product version: missing $productFile"
    }
    $match = Select-String -Path $productFile -Pattern 'PRODUCT_VERSION\s*=\s*"([^"]+)"' | Select-Object -First 1
    if (-not $match) {
        throw "Cannot resolve product version: PRODUCT_VERSION not found in $productFile"
    }
    return $match.Matches[0].Groups[1].Value
}
