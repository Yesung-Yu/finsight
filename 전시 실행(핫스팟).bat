@echo off
rem Exhibition mode on the same hotspot. Connect this PC to the hotspot first.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\serve_kiosk.ps1"
pause
