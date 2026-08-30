@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 goto :use_py
where python >nul 2>&1
if %ERRORLEVEL%==0 goto :use_python
echo [ERROR] Python not found. Install Python 3.10+ and enable "Add python.exe to PATH".
pause
exit /b 1

:use_py
echo Using: py -3
py -3 -m pip install -U -r "%~dp0agent\requirements.txt"
goto :after_pip

:use_python
echo Using: python
python -m pip install -U -r "%~dp0agent\requirements.txt"
goto :after_pip

:after_pip
if errorlevel 1 (
  echo [ERROR] pip install failed.
  pause
  exit /b 1
)

echo.
echo Agent deps installed. Start MFAAvalonia.exe next.
if not exist "%~dp0config\orders_source.json" (
  echo Tip: for order-friend tasks, copy config\orders_source.example.json
  echo      to config\orders_source.json and set your url.
)
pause
exit /b 0
