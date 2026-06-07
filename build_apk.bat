@echo off
REM JARVIS AI — Build Android APK (free, no Android Studio needed)
REM Uses PWABuilder cloud API + ngrok for public URL
REM Run this script, then follow the instructions
REM ─────────────────────────────────────────────────────────────────────────────

title JARVIS AI — APK Builder
color 0B
echo.
echo  ██████████████████████████████████████████████████
echo       JARVIS AI — Android APK Builder
echo       Free distribution via GitHub Releases
echo  ██████████████████████████████████████████████████
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo  [ERROR] Python not found. Install from python.org
    pause & exit /b 1
)

REM Check Node.js (for bubblewrap)
node --version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] Node.js not found. Installing via winget...
    winget install OpenJS.NodeJS.LTS
    echo  [INFO] Please restart this script after Node.js installs.
    pause & exit /b 0
)

REM Check ngrok
ngrok version >nul 2>&1
if errorlevel 1 (
    echo  [INFO] ngrok not found. You can get it free at ngrok.com
    echo  [INFO] Alternatively, use Cloudflare Tunnel:
    echo         winget install Cloudflare.cloudflared
    echo.
)

echo  [1/4] Starting JARVIS server...
start /B "JARVIS Server" python "%~dp0jarvis.py" --no-ui --no-voice
timeout /t 3 /nobreak >nul

echo  [2/4] Opening PWABuilder in browser...
echo.
echo  ┌─────────────────────────────────────────────────────────┐
echo  │  INSTRUCTIONS:                                          │
echo  │                                                         │
echo  │  1. Run ngrok first: ngrok http 8100                   │
echo  │     (or: cloudflared tunnel --url http://localhost:8100) │
echo  │                                                         │
echo  │  2. Copy the HTTPS URL from ngrok                       │
echo  │     (e.g. https://abc123.ngrok-free.app)               │
echo  │                                                         │
echo  │  3. Go to: https://www.pwabuilder.com                  │
echo  │     Enter your ngrok URL + /android                     │
echo  │     Click Start → Package For Stores → Android          │
echo  │                                                         │
echo  │  4. Download the APK — it's completely FREE            │
echo  │                                                         │
echo  │  OR: Push to GitHub → Actions auto-builds the APK!     │
echo  │      Go to: github.com/YOUR_USER/JARVISCore/releases   │
echo  └─────────────────────────────────────────────────────────┘
echo.

start "" "https://www.pwabuilder.com"
start "" "https://dashboard.ngrok.com/get-started/setup"

echo  [3/4] Install Bubblewrap CLI (for offline builds):
call npm install -g @bubblewrap/cli >nul 2>&1
if errorlevel 0 (
    echo  [OK] bubblewrap installed
) else (
    echo  [SKIP] bubblewrap install skipped
)

echo.
echo  [4/4] Alternative: Direct APK via GitHub Actions
echo.
echo  Push your code to GitHub and the APK builds automatically!
echo  See: .github/workflows/build_apk.yml
echo.
echo  Free GitHub Releases hosts the APK for download.
echo  Users can install it without the Play Store.
echo.
echo  ─────────────────────────────────────────────────────────
echo  Amazon Appstore (FREE to publish):
echo    See: AMAZON_APPSTORE.md for step-by-step guide
echo.
echo  Google Play ($25 one-time fee):
echo    See: BUILD_PLAY_STORE.md
echo  ─────────────────────────────────────────────────────────
echo.
pause
