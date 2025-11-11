@echo off
REM USGS Data Downloader - Windows Installation Script
REM This script sets up the Python environment and installs all dependencies

echo ==========================================
echo USGS Data Downloader - Windows Installation
echo ==========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [X] Python is not installed.
    echo Please install Python 3 from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [+] Python found:
python --version
echo.

REM Check if pip is installed
pip --version >nul 2>&1
if errorlevel 1 (
    echo [X] pip is not installed.
    echo Installing pip...
    python -m ensurepip --upgrade
)

echo [+] pip found:
pip --version
echo.

REM Create virtual environment
echo [*] Creating virtual environment...
python -m venv venv

REM Activate virtual environment
echo [*] Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo [*] Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements
echo [*] Installing Python dependencies...
pip install -r requirements.txt

echo.
echo ==========================================
echo [+] Installation Complete!
echo ==========================================
echo.
echo To run the application:
echo   1. Activate the virtual environment:
echo      venv\Scripts\activate.bat
echo.
echo   2. Run the application:
echo      python app.py
echo.
echo   3. Open your browser and go to:
echo      http://127.0.0.1:5001
echo.
echo To deactivate the virtual environment later, type:
echo      deactivate
echo.
pause
