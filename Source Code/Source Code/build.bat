@echo off
REM ──────────────────────────────────────────────────────────────────────────
REM  SAS Modbus Toolkit — Build Script
REM  Creates a standalone Windows executable via PyInstaller.
REM  Run from the "Source Code" directory.
REM ──────────────────────────────────────────────────────────────────────────

echo.
echo  ============================================================
echo   SAS Modbus Toolkit — Build
echo  ============================================================
echo.

REM ── Check virtual environment ────────────────────────────────────────────
IF NOT EXIST ".venv\Scripts\activate.bat" (
    echo  [SETUP] Creating virtual environment...
    python -m venv .venv
)

echo  [SETUP] Activating virtual environment...
call .venv\Scripts\activate.bat

echo  [SETUP] Installing dependencies...
pip install -r requirements.txt --quiet

echo.
echo  [BUILD] Running PyInstaller...
echo.

pyinstaller ^
    --noconfirm ^
    --onefile ^
    --windowed ^
    --name "SAS-Modbus-Toolkit" ^
    --icon "assets\icon.ico" ^
    --add-data "assets;assets" ^
    --hidden-import "pymodbus.client.tcp" ^
    --hidden-import "pymodbus.client.serial" ^
    --hidden-import "pymodbus.server.async_io" ^
    --hidden-import "pymodbus.datastore" ^
    --hidden-import "pymodbus.datastore.store" ^
    --hidden-import "pymodbus.datastore.context" ^
    --hidden-import "serial.tools.list_ports" ^
    --hidden-import "PIL._tkinter_finder" ^
    main.py

IF %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [ERROR] Build failed — check output above.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   Build complete!
echo   Output: dist\SAS-Modbus-Toolkit.exe
echo  ============================================================
echo.
pause
