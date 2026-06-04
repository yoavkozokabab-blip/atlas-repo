# Delegates to Phase 152 packaging script.
& (Join-Path $PSScriptRoot "packaging\installer\installer_build.ps1") @args
exit $LASTEXITCODE
