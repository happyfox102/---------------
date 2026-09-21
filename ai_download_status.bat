@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -Command "Get-Content -LiteralPath 'data/ai-install-status.json' -Encoding UTF8"
pause
