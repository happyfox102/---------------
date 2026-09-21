@echo off
cd /d "%~dp0"
powershell -NoProfile -Command "Remove-Item -LiteralPath 'data/stop-ai-install.flag' -ErrorAction SilentlyContinue; Start-Process -FilePath '.venv/Scripts/pythonw.exe' -ArgumentList 'tools/ai_install_job.py' -WorkingDirectory (Get-Location).Path -WindowStyle Hidden"
echo Background installation started. Use ai_download_status.bat to check progress.
pause
