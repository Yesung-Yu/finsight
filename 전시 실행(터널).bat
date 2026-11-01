@echo off
rem Exhibition mode via Cloudflare tunnel. Visitors scan qr.png with mobile data.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\serve_kiosk.ps1" -Tunnel
pause
