@echo off
rem PC Xavfsizlik - oson ishga tushirish (Windows)
setlocal
cd /d "%~dp0"

if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate.bat
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

echo Dashboard: http://127.0.0.1:%PCX_PORT%
if "%PCX_PORT%"=="" echo Dashboard: http://127.0.0.1:8000
python app.py --arm %*
endlocal
