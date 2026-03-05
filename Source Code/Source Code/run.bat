@echo off
REM ──────────────────────────────────────────────────────────────────────────
REM  SAS Modbus Toolkit — Quick Setup & Run
REM  Sets up the environment and launches the app directly from source.
REM ──────────────────────────────────────────────────────────────────────────

echo.
echo  SAS Modbus Toolkit — Setup
echo.

IF NOT EXIST ".venv\Scripts\activate.bat" (
    echo  Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo  Installing dependencies...
pip install -r requirements.txt --quiet

echo  Launching SAS Modbus Toolkit...
python main.py
