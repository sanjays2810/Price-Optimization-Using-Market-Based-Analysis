@echo off
cd /d "%~dp0"
call venv\Scripts\activate
echo Starting server at http://127.0.0.1:8000  (Ctrl+C to stop)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
