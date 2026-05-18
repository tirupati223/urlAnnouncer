@echo off
title Push URL Announcer to GitHub
echo.
echo ===================================
echo  URL Announcer - Push to GitHub
echo ===================================
echo.
cd /d "C:\URL announcer"

echo Checking git status...
git status
echo.

echo Adding all changed files...
git add -A
echo.

echo Enter your commit message (or press Enter for default):
set /p COMMIT_MSG="Message: "
if "%COMMIT_MSG%"=="" set COMMIT_MSG=Update URL Announcer addon

git commit -m "%COMMIT_MSG%"
echo.

echo Pushing to GitHub...
git push origin main
echo.

if %ERRORLEVEL%==0 (
    echo SUCCESS! All files are now on GitHub.
    echo Visit: https://github.com/tirupatiygaikwad/urlAnnouncer
) else (
    echo Push failed. Make sure you are connected to the internet
    echo and that you have set up GitHub credentials.
    echo.
    echo See SETUP_GITHUB.md for instructions.
)

echo.
pause
