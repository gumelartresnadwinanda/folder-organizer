@echo off
title Folder Organizer by Username
cd /d "%~dp0"
echo ========================================================
echo       Folder Organizer by Username
echo ========================================================
echo.
echo Checking Python environment...
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH!
    echo Please install Python 3.8+ and ensure "Add Python to PATH" is checked.
    pause
    exit /b
)

echo Starting web server on http://localhost:5000 ...
start "" "http://localhost:5000"
python app.py
if %errorlevel% neq 0 (
    echo.
    echo [NOTE] If Flask is missing, run: pip install flask
    pause
)
