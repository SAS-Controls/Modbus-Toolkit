@echo off
echo.
echo  ============================================================
echo   SAS Modbus Toolkit — Development Setup
echo  ============================================================
echo.

IF NOT EXIST ".venv\Scripts\activate.bat" (
    echo  [SETUP] Creating virtual environment...
    python -m venv .venv
)

echo  [SETUP] Activating virtual environment...
call .venv\Scripts\activate.bat

echo  [SETUP] Installing dependencies...
pip install -r requirements.txt

echo.
echo  ============================================================
echo   Setup complete! Run with: python main.py
echo  ============================================================
echo.
pause
