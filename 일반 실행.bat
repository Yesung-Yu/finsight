@echo off
rem Normal mode on this PC only: http://localhost:8501
cd /d "%~dp0"
".venv\Scripts\streamlit.exe" run app.py
pause
