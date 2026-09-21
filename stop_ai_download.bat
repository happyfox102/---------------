@echo off
cd /d "%~dp0"
if not exist data mkdir data
echo stop>data\stop-ai-install.flag
echo Stop requested. Downloaded parts will be kept.
pause
