@echo off
title Maharashtra Directory B2B Lead Scraper
color 0B
echo ========================================================
echo    Maharashtra Directory B2B Lead Data Scraper
echo ========================================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.10+ and check 'Add to PATH'.
    pause
    exit /b
)

python main.py
pause

