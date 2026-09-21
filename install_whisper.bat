@echo off
setlocal
cd /d "%~dp0"
set PIP_DEFAULT_TIMEOUT=120
if not exist ".venv\Scripts\python.exe" (
    echo Run install.bat first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m pip install -r requirements-offline.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8'); print('Whisper small ready.')"
if errorlevel 1 goto failed
pause
exit /b 0
:failed
echo Whisper installation failed. Check the messages above.
pause
exit /b 1
