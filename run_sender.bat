@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 sender_gui.py
) else (
  python sender_gui.py
)
if errorlevel 1 pause
