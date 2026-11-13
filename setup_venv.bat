@echo off
REM Creates .venv with Python 3.12 (the version in the PyCharm config) and installs dependencies.
REM Run from the project root: double-click or `setup_venv.bat` in a terminal.
cd /d "%~dp0"
py -3.12 --version >nul 2>&1 || (echo Python 3.12 not found. Install it from python.org, then re-run. & exit /b 1)
if exist .venv (echo .venv already exists - delete it first if you want a clean one. & exit /b 1)
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install --upgrade pip
REM psycopg2 is skipped: PostgreSQL is not used and it fails to build on Windows.
findstr /v /i "psycopg2" requirements.txt > "%TEMP%\hrp_req.txt"
.venv\Scripts\python -m pip install -r "%TEMP%\hrp_req.txt"
.venv\Scripts\python -m pip install pytesseract
echo.
echo Done. In PyCharm: Settings ^> Python Interpreter ^> Add ^> Existing ^> %~dp0.venv\Scripts\python.exe
