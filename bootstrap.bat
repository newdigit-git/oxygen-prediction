@echo off
REM Bootstrap script for Windows local development

echo Smart Oxygen Energy Intelligence System - Bootstrap Script
echo ============================================================

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set python_version=%%i
echo Python version: %python_version%

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
    echo Virtual environment created
)

REM Activate virtual environment
call venv\Scripts\activate.bat
echo Virtual environment activated

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt -q
echo Dependencies installed

REM Create .env if it doesn't exist
if not exist ".env" (
    echo Creating .env from .env.example...
    copy .env.example .env
    echo Please update .env with your database credentials
)

echo.
echo Bootstrap complete! Next steps:
echo 1. Update .env with your PostgreSQL credentials
echo 2. Create database: createdb oxygen_pred
echo 3. Start API: uvicorn app.main:app --reload
echo 4. View docs: http://localhost:8000/docs
