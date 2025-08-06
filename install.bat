@echo off
title Fortify Tool - Installation

echo ========================================
echo    Fortify Tool - Installation Script
echo ========================================
echo.

echo [1/2] Checking Python and uv environment...
uv --version >nul 2>nul
if %errorlevel% neq 0 (
    echo Error: uv command not found!
    echo.
    echo Required installations:
    echo.
    echo 1. Install Python:
    echo    - Go to https://www.python.org/downloads/
    echo    - Download Python 3.8+ and install
    echo    - Make sure to check "Add Python to PATH"
    echo.
    echo 2. Install uv:
    echo    - Open Command Prompt and run: pip install uv
    echo    - Or use: python -m pip install uv
    echo.
    echo 3. Restart Command Prompt and run this script again
    echo.
    echo Alternative: If you have Python but not uv, try running:
    echo    python -m pip install uv
    echo.
    pause
    exit /b 1
)

echo Success: uv is available
uv --version

echo.
echo [2/2] Installing project dependencies...
if not exist "pyproject.toml" (
    echo Error: pyproject.toml file not found!
    echo Please ensure you are running this script in the correct project directory.
    pause
    exit /b 1
)

echo Installing dependencies with uv...
uv sync
if %errorlevel% neq 0 (
    echo Error: Dependencies installation failed!
    echo.
    echo Possible solutions:
    echo    1. Check network connection
    echo    2. Try running as Administrator
    echo    3. Check if antivirus is blocking the installation
    echo    4. Manual installation: uv sync --verbose
    echo.
    pause
    exit /b 1
)

echo Success: Dependencies installed successfully

echo.
echo [Config Check] Checking configuration file...
if not exist "config\config.yaml" (
    echo Warning: Configuration file does not exist
    echo Please ensure config/config.yaml is properly set up
) else (
    echo Success: Configuration file exists
)

echo.
echo ========================================
echo           Installation Complete!
echo ========================================
echo.
echo Next Steps:
echo    1. Start GUI: Double-click start_gui.bat
echo    2. Or manually run: uv run python fortify_gui.py
echo    3. First time: Set Azure DevOps PAT in Settings tab
echo.
echo Important Files:
echo    - fortify_gui.py - Main GUI program
echo    - config/config.yaml - Configuration file
echo    - README.md - Detailed usage guide
echo.
echo If you encounter issues:
echo    - Check README.md troubleshooting section
echo    - Ensure PAT permissions are correct
echo    - Check network connection and firewall settings
echo.
pause
