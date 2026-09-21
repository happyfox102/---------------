@echo off
setlocal
cd /d "%~dp0"
set PIP_DEFAULT_TIMEOUT=120
set PIP_DISABLE_PIP_VERSION_CHECK=1
if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 goto failed
)
set "FRIDAY_REQUIREMENTS=requirements.txt"
if exist "requirements-lock.txt" set "FRIDAY_REQUIREMENTS=requirements-lock.txt"
".venv\Scripts\python.exe" -m pip install -r "%FRIDAY_REQUIREMENTS%"
if errorlevel 1 goto failed
echo Installation completed. Run start.bat
pause
exit /b 0
:failed
echo Installation failed. Install Python 3.12 and check your internet connection.
pause
exit /b 1
