@echo off
chcp 65001 >nul
title JARVIS AI

REM ── Auto-elevate to admin ──────────────────────────────────────
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting admin rights...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Run SETUP.bat first.
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo    JARVIS AI - Starting...
echo  ============================================================
echo.

set PYTHONIOENCODING=utf-8
python jarvis.py
pause
