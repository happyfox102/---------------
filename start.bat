@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Run install.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -c "import friday.qt, speech_recognition, openpyxl, docx, win32com.client, vosk" >nul 2>&1
if errorlevel 1 (
    echo Dependencies are missing. Run install.bat first.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0main.py"
