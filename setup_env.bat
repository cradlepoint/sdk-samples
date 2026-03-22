@echo off
REM Cross-platform venv setup for NCOS SDK development on Windows
setlocal

set VENV_DIR=.venv

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python not found. Install Python 3.7+ from https://www.python.org/downloads/windows/
    exit /b 1
)

echo Creating virtual environment in %VENV_DIR%...
if not exist "%VENV_DIR%" (
    python -m venv %VENV_DIR%
) else (
    echo Virtual environment already exists in %VENV_DIR%
)

call %VENV_DIR%\Scripts\activate.bat

echo Upgrading pip...
pip install -U pip

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Setup complete! Activate the venv with: %VENV_DIR%\Scripts\activate.bat
