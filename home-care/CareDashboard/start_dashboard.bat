@echo off
rem Starts the Care Dashboard. Needs Python 3.8 or newer (https://www.python.org/downloads/). Nothing else to install.
cd /d "%~dp0"
where py >nul 2>nul && (py -3 care_dashboard.py & goto :done)
where python >nul 2>nul && (python care_dashboard.py & goto :done)
echo Python 3 was not found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") and run this again.
:done
pause
