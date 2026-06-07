@echo off
title JARVIS AI - Setup Wizard
color 0B
cls

echo.
echo  ============================================================
echo    JARVIS AI - Personal AI Assistant
echo    Setup Wizard v1.0
echo  ============================================================
echo.

REM ── Check Python ────────────────────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo  [!] Python not found.
    echo      Please install Python 3.10+ from https://python.org
    echo      Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo  [OK] Python %PY_VER% found
echo.

REM ── Install dependencies ─────────────────────────────────────────
echo  [1/4] Installing dependencies (this takes 1-2 minutes)...
echo.
pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo  [!] Some packages failed - trying one by one...
    for /f %%p in (requirements.txt) do pip install %%p --quiet 2>nul
)
echo  [OK] Dependencies installed
echo.

REM ── Create .env if missing ───────────────────────────────────────
echo  [2/4] Checking configuration...
if not exist .env (
    echo  Creating .env file...
    (
        echo # JARVIS AI Configuration
        echo # Get your free Gemini key at: https://ai.google.dev
        echo GEMINI_API_KEY=
        echo.
        echo # Optional: Groq for faster responses (https://console.groq.com)
        echo GROQ_API_KEY=
        echo.
        echo # Your email (for JARVIS21 approval notifications)
        echo ADMIN_EMAIL=
        echo.
        echo # Server port
        echo API_PORT=8765
    ) > .env
    echo  [OK] .env created - edit it to add your API keys
) else (
    echo  [OK] .env already exists
)
echo.

REM ── Set up JARVIS password ────────────────────────────────────────
echo  [3/4] Setting up JARVIS password...
python -c "
from api.auth_manager import is_setup_done
if is_setup_done():
    print('  [OK] Password already configured')
else:
    import getpass, sys
    print('  Create a password for JARVIS (used to log in from phone):')
    print('  ', end='', flush=True)
" 2>nul
echo.

REM ── Done ─────────────────────────────────────────────────────────
echo  [4/4] Setup complete!
echo.
echo  ============================================================
echo    JARVIS is ready to launch!
echo  ============================================================
echo.
echo  HOW TO USE:
echo  1. Double-click launch.bat to start JARVIS
echo  2. Open your browser to: http://localhost:8765
echo  3. On your phone: install the Android app and connect
echo.
echo  FIRST LAUNCH:
echo  - You'll be asked to set a password
echo  - Enter your Gemini API key (free at ai.google.dev)
echo  - On Android: enter your PC's IP address to connect
echo.
echo  Press any key to launch JARVIS now...
pause >nul

start "" python jarvis.py
timeout /t 3 /nobreak >nul
start "" http://localhost:8765
