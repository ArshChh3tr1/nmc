@echo off
title NMC Harmonizer - Starting...
cd /d "%~dp0"

echo ============================================
echo   NMC Harmonizer - Starting Application
echo ============================================
echo.

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found. Creating one now...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo Installing dependencies, this may take a few minutes...
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo.
echo Launching NMC Harmonizer in your browser...
echo.

python -m streamlit run app/NMC.py --server.headless false

pause
