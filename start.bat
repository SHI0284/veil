@echo off
cd /d "%~dp0"
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
python -X utf8 main.py
if errorlevel 1 pause
