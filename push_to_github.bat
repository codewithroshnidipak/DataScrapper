@echo off
cd /d "%~dp0"
echo ===================================================
echo   Pushing DataScrapper to GitHub (codewithroshnidipak)
echo ===================================================
echo.
git push -u origin main
echo.
if %ERRORLEVEL% EQU 0 (
    echo ===================================================
    echo [SUCCESS] Code successfully pushed to GitHub!
    echo ===================================================
) else (
    echo [ERROR] Push failed. Please check your credentials.
)
pause

