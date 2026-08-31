@echo off
setlocal
set "SCRIPT=%~dp0ensure_mumu.py"

where py >nul 2>&1
if %ERRORLEVEL%==0 goto :use_py
where python >nul 2>&1
if %ERRORLEVEL%==0 goto :use_python
echo [MuMu pretask] Python not found. Install Python 3.10+ and add it to PATH.
exit /b 1

:use_py
py -3 "%SCRIPT%" %*
exit /b %ERRORLEVEL%

:use_python
python "%SCRIPT%" %*
exit /b %ERRORLEVEL%
