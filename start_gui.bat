@echo off
title Fortify Tool

echo ========================================
echo      Fortify Tool - Starting...
echo ========================================
echo.

if not exist "fortify_gui.py" (
    echo Error: Cannot find fortify_gui.py!
    echo Please run this script in the correct project directory.
    pause
    exit /b 1
)

echo Checking environment...
uv --version >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: uv command not found!
    echo.
    echo Please run install.bat first to set up the environment.
    echo.
    echo If you have already run install.bat:
    echo    1. Restart Command Prompt
    echo    2. Make sure Python and uv are installed
    echo    3. Try running: python -m pip install uv
    echo.
    pause
    exit /b 1
)

echo Environment ready, starting GUI...
echo.

uv run python fortify_gui.py

if %errorlevel% neq 0 (
    echo.
    echo Error: Program encountered an error!
    echo.
    echo Possible solutions:
    echo    1. Check config/config.yaml settings
    echo    2. Ensure Azure DevOps PAT is configured
    echo    3. Check network connection
    echo    4. Re-run install.bat
    echo.
    pause
)
