@echo off
setlocal
cd /d "%~dp0"

:: Elevate to Administrator if not already elevated
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Run using pythonw.exe to suppress console window
start "" pythonw.exe usb_sentry.py
exit /b
