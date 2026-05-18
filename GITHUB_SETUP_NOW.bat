@echo off
title GitHub Setup for URL Announcer
color 0A
echo.
echo =====================================================
echo   URL Announcer - GitHub Setup (One Time Only)
echo =====================================================
echo.
echo STEP 1: You need a GitHub Personal Access Token.
echo.
echo Opening GitHub token creation page in your browser...
start https://github.com/settings/tokens/new?description=urlAnnouncer^&scopes=repo
echo.
echo In the browser:
echo   1. Make sure you are logged in to GitHub
echo   2. The page will show "New personal access token"
echo   3. At the bottom tick the checkbox next to "repo"
echo   4. Scroll down and click "Generate token"
echo   5. COPY the token that appears (starts with ghp_)
echo.
echo =====================================================
echo.
set /p GITHUB_USER="Enter your GitHub username: "
echo.
set /p GITHUB_TOKEN="Paste your GitHub token here (it will not show): "
echo.
echo Creating repository on GitHub...
curl -s -X POST ^
  -H "Authorization: token %GITHUB_TOKEN%" ^
  -H "Accept: application/vnd.github.v3+json" ^
  https://api.github.com/user/repos ^
  -d "{\"name\":\"urlAnnouncer\",\"description\":\"NVDA addon to announce, copy and share browser URLs - by Tirupati Janardhan Gaikwad, NVDA Certified 2025\",\"private\":false,\"has_issues\":true,\"has_wiki\":false}" > repo_result.tmp 2>&1

findstr /C:"full_name" repo_result.tmp >nul 2>&1
if %ERRORLEVEL%==0 (
    echo Repository created successfully!
) else (
    findstr /C:"already exists" repo_result.tmp >nul 2>&1
    if %ERRORLEVEL%==0 (
        echo Repository already exists - continuing with push.
    ) else (
        echo Repository creation response:
        type repo_result.tmp
    )
)
del repo_result.tmp 2>nul

echo.
echo Setting up git credentials...
cd /d "C:\URL announcer"
git remote set-url origin https://%GITHUB_USER%:%GITHUB_TOKEN%@github.com/%GITHUB_USER%/urlAnnouncer.git

echo.
echo Pushing all files to GitHub...
git push -u origin main

if %ERRORLEVEL%==0 (
    echo.
    color 0A
    echo =====================================================
    echo   SUCCESS! All files are now on GitHub!
    echo =====================================================
    echo.
    echo Your repository: https://github.com/%GITHUB_USER%/urlAnnouncer
    echo.
    echo Opening your repository in browser...
    start https://github.com/%GITHUB_USER%/urlAnnouncer
    echo.
    echo Saving credentials for automatic future pushes...
    git config credential.helper manager
    git remote set-url origin https://github.com/%GITHUB_USER%/urlAnnouncer.git
    echo Done! Future pushes will happen automatically.
) else (
    echo.
    color 0C
    echo =====================================================
    echo   Push failed. Check your token and try again.
    echo =====================================================
)

echo.
pause
