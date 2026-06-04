@echo off
REM Atlas — Repository Intelligence (Phase 143 one-click launcher)
title Atlas
cd /d "%~dp0"
if exist "%~dp0Atlas.exe" (
  start "" "%~dp0Atlas.exe"
  exit /b 0
)
echo.
echo   Starting Atlas...
echo.
py -3 run_atlas.py %*
if errorlevel 1 (
  echo.
  echo   Could not start with 'py'. Trying 'python'...
  python run_atlas.py %*
)
if errorlevel 1 (
  echo.
  echo   Atlas could not start. Install Python 3.10+ from https://www.python.org/downloads/
  echo   Then double-click "Launch Atlas.bat" again.
  pause
)
exit /b %ERRORLEVEL%
