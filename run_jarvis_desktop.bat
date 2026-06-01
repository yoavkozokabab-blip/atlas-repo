@echo off
REM JARVIS Desktop - Repository Intelligence Platform (Phase 107 MVP)
REM Zero external dependencies. Opens http://127.0.0.1:8777 in your browser.
setlocal
cd /d "%~dp0"
echo.
echo   Starting JARVIS Desktop...
echo   (Repository Intelligence Platform - local, no API keys)
echo.
py -3 run_jarvis_desktop.py %*
if errorlevel 1 (
  echo.
  echo   Could not start with 'py'. Trying 'python'...
  python run_jarvis_desktop.py %*
)
endlocal
