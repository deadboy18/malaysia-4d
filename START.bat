@echo off
title Deadboy4D Analytics
color 0A

echo.
echo  ============================================
echo     Deadboy4D Analytics - Launcher
echo  ============================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Download Python from: https://www.python.org/downloads/
    echo  Make sure to check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

echo  [OK] Python found
python --version

:: Check and install requirements
echo.
echo  Checking dependencies...
python -c "import flask, pandas, numpy, requests, bs4, scipy" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [INSTALLING] Some packages are missing. Installing now...
    echo.
    pip install -r requirements.txt
    echo.
    if %errorlevel% neq 0 (
        echo  [ERROR] Failed to install packages. Try manually:
        echo  pip install -r requirements.txt
        pause
        exit /b 1
    )
    echo  [OK] All packages installed.
) else (
    echo  [OK] All packages already installed.
)

:: Check if data folder exists
if not exist "data" mkdir data

:: Show data status
echo.
echo  ============================================
echo     Data Status
echo  ============================================
if exist "data\sportstoto_draws.csv" (
    for %%A in ("data\sportstoto_draws.csv") do echo  [SPORT TOTO]  %%~zA bytes
) else (
    echo  [SPORT TOTO]  No data - use Scraper tab
)
if exist "data\magnum_draws.csv" (
    for %%A in ("data\magnum_draws.csv") do echo  [MAGNUM 4D]   %%~zA bytes
) else (
    echo  [MAGNUM 4D]   No data - use Scraper tab
)
if exist "data\damacai_draws.csv" (
    for %%A in ("data\damacai_draws.csv") do echo  [DA MA CAI]   %%~zA bytes
) else (
    echo  [DA MA CAI]   No data - use Scraper tab
)

:: Start server and open browser
echo.
echo  ============================================
echo     Starting Server
echo  ============================================
echo.
echo  Opening http://localhost:8080 in your browser...
echo  Press Ctrl+C to stop the server.
echo.

:: Open browser after 2 second delay (gives server time to start)
start "" cmd /c "timeout /t 2 /nobreak >nul & start http://localhost:8080"

:: Start the Flask server (this blocks until Ctrl+C)
python server.py

pause
