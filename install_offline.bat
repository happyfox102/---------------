@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Run install.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" tools\download_model.py
if errorlevel 1 (
    echo Model download failed. Check your internet connection.
    pause
    exit /b 1
)
echo Offline Russian model is ready. Choose Vosk in Settings.
pause
