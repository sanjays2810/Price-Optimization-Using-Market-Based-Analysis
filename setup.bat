@echo off
REM One-time setup for Windows
cd /d "%~dp0"
python --version || (echo Python is not installed or not in PATH & exit /b 1)
if not exist venv python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
if not exist .env copy .env.example .env
echo.
echo Setup finished. Now open .env and set DB_PASSWORD to your MySQL root password,
echo then run:  python check_env.py   and then  run.bat
pause
