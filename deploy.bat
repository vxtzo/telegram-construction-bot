@echo off
echo ========================================
echo   Git Push and Deploy Script
echo ========================================
echo.

cd /d "C:\Users\Admin\Desktop\telegram-construction-bot-main"

echo [1/4] Checking git status...
git status
echo.

echo [2/4] Adding files to git...
git add .
echo.

echo [3/4] Creating commit...
git commit -m "fix: Fix enum case sensitivity for PostgreSQL (uppercase values)"
echo.

echo [4/4] Pushing to GitHub (will trigger Railway deploy)...
git push origin main
echo.

echo ========================================
echo   DONE! Check Railway for deploy status
echo ========================================
pause

