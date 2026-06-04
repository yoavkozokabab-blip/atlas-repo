# Delegates to Phase 152 packaging script.
& (Join-Path $PSScriptRoot "packaging\pyinstaller\build_atlas_exe.ps1") @args
exit $LASTEXITCODE
