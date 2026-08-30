@echo off
setlocal
set "SCRIPT=%~dp0ensure_mumu.py"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 "%SCRIPT%" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  python "%SCRIPT%" %*
  exit /b %ERRORLEVEL%
)

echo [MuMu pretask] Python not found. Install Python 3.10+ and add it to PATH.
exit /b 1
