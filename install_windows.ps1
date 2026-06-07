# JARVIS Windows Installer
# Run this once to register JARVIS as a proper Windows app
# Usage: Right-click → Run with PowerShell (or: powershell -File install_windows.ps1)

$ErrorActionPreference = "Continue"
$JARVIS_DIR = $PSScriptRoot

Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  JARVIS AI — Windows Installation" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Python & dependencies ───────────────────────────────────────────────────
Write-Host "[1/5] Installing Python dependencies..." -ForegroundColor Yellow

$packages = @(
    "groq", "fastapi", "uvicorn", "python-dotenv", "psutil",
    "SpeechRecognition", "pyaudio", "pyttsx3", "pyperclip",
    "requests", "beautifulsoup4", "Pillow", "pystray",
    "google-genai", "pywebview", "keyboard", "pywin32",
    "youtube-transcript-api", "sympy", "feedparser"
)

foreach ($pkg in $packages) {
    $result = pip install $pkg --quiet 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [ok] $pkg" -ForegroundColor Green
    } else {
        Write-Host "  [skip] $pkg (optional)" -ForegroundColor Gray
    }
}

# ── 2. Registry registration ──────────────────────────────────────────────────
Write-Host ""
Write-Host "[2/5] Registering JARVIS in Windows..." -ForegroundColor Yellow

$python = (Get-Command python).Source
$launchCmd = "`"$python`" `"$JARVIS_DIR\jarvis.py`""

# Add to startup
$regRun = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
Set-ItemProperty -Path $regRun -Name "JARVIS" -Value $launchCmd -Force
Write-Host "  [ok] Added to Windows startup" -ForegroundColor Green

# Register app capabilities (shows in Default Apps)
$capPath = "HKCU:\Software\JARVIS\Capabilities"
New-Item -Path $capPath -Force | Out-Null
Set-ItemProperty -Path $capPath -Name "ApplicationName" -Value "JARVIS AI" -Force
Set-ItemProperty -Path $capPath -Name "ApplicationDescription" -Value "Personal AI Assistant with Gemini AI" -Force
New-Item -Path "$capPath\URLAssociations" -Force | Out-Null
Set-ItemProperty -Path "$capPath\URLAssociations" -Name "jarvis" -Value "jarvis" -Force

$regApps = "HKCU:\Software\RegisteredApplications"
New-Item -Path $regApps -Force | Out-Null
Set-ItemProperty -Path $regApps -Name "JARVIS" -Value "Software\JARVIS\Capabilities" -Force
Write-Host "  [ok] Registered in Windows Default Apps" -ForegroundColor Green

# jarvis:// URI handler
$uriPath = "HKCU:\Software\Classes\jarvis"
New-Item -Path $uriPath -Force | Out-Null
Set-ItemProperty -Path $uriPath -Name "(default)" -Value "JARVIS AI Protocol" -Force
Set-ItemProperty -Path $uriPath -Name "URL Protocol" -Value "" -Force
New-Item -Path "$uriPath\shell\open\command" -Force | Out-Null
Set-ItemProperty -Path "$uriPath\shell\open\command" -Name "(default)" -Value "$launchCmd `"%1`"" -Force
Write-Host "  [ok] Registered jarvis:// URI handler" -ForegroundColor Green

# ── 3. App shortcut ───────────────────────────────────────────────────────────
Write-Host ""
Write-Host "[3/5] Creating shortcuts..." -ForegroundColor Yellow

# Desktop shortcut
$WshShell = New-Object -ComObject WScript.Shell
$shortcut = $WshShell.CreateShortcut("$([Environment]::GetFolderPath('Desktop'))\JARVIS AI.lnk")
$shortcut.TargetPath = $python
$shortcut.Arguments = "`"$JARVIS_DIR\jarvis.py`""
$shortcut.WorkingDirectory = $JARVIS_DIR
$shortcut.Description = "JARVIS AI Personal Assistant"
$icon = "$JARVIS_DIR\static\icon.ico"
if (Test-Path $icon) { $shortcut.IconLocation = $icon }
$shortcut.Save()
Write-Host "  [ok] Desktop shortcut created" -ForegroundColor Green

# Start Menu shortcut
$startMenu = "$([Environment]::GetFolderPath('Programs'))\JARVIS"
New-Item -Path $startMenu -ItemType Directory -Force | Out-Null
$sm = $WshShell.CreateShortcut("$startMenu\JARVIS AI.lnk")
$sm.TargetPath = $python
$sm.Arguments = "`"$JARVIS_DIR\jarvis.py`""
$sm.WorkingDirectory = $JARVIS_DIR
$sm.Description = "JARVIS AI Personal Assistant"
if (Test-Path $icon) { $sm.IconLocation = $icon }
$sm.Save()
Write-Host "  [ok] Start Menu shortcut created" -ForegroundColor Green

# ── 4. Firewall rule for phone remote ─────────────────────────────────────────
Write-Host ""
Write-Host "[4/5] Setting up network access for phone remote..." -ForegroundColor Yellow

$fwRule = Get-NetFirewallRule -DisplayName "JARVIS AI" -ErrorAction SilentlyContinue
if (-not $fwRule) {
    try {
        New-NetFirewallRule -DisplayName "JARVIS AI" -Direction Inbound `
            -Protocol TCP -LocalPort 8100 -Action Allow -Profile Any `
            -Description "Allow JARVIS phone remote access" | Out-Null
        Write-Host "  [ok] Firewall rule added (port 8100)" -ForegroundColor Green
    } catch {
        Write-Host "  [warn] Run as Admin to add firewall rule" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [ok] Firewall rule already exists" -ForegroundColor Green
}

# ── 5. Sparse package registration (optional, requires admin) ─────────────────
Write-Host ""
Write-Host "[5/5] Attempting sparse package registration..." -ForegroundColor Yellow

$manifest = "$JARVIS_DIR\AppxManifest.xml"
if (Test-Path $manifest) {
    try {
        Add-AppxPackage -ExternalLocation $JARVIS_DIR -Path $manifest -ErrorAction Stop
        Write-Host "  [ok] JARVIS registered as a Windows app package" -ForegroundColor Green
        Write-Host "       Go to Settings > Apps > Default Apps to set as default" -ForegroundColor Cyan
    } catch {
        Write-Host "  [info] Sparse package skipped (needs Admin + Dev Mode)" -ForegroundColor Gray
        Write-Host "         To enable: Settings > System > For Developers > turn on" -ForegroundColor Gray
    }
} else {
    Write-Host "  [skip] AppxManifest.xml not found" -ForegroundColor Gray
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host "  JARVIS installation complete!" -ForegroundColor Green
Write-Host "======================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Launch: python `"$JARVIS_DIR\jarvis.py`"" -ForegroundColor White
Write-Host "  Or:     double-click the JARVIS AI desktop shortcut" -ForegroundColor White
Write-Host ""
Write-Host "  Phone remote: open JARVIS and say 'phone link'" -ForegroundColor White
Write-Host "  Default Apps: Settings > Apps > Default Apps > JARVIS" -ForegroundColor White
Write-Host ""

# Launch JARVIS now?
$launch = Read-Host "Launch JARVIS now? (y/n)"
if ($launch -eq 'y' -or $launch -eq 'Y') {
    Start-Process $python -ArgumentList "`"$JARVIS_DIR\jarvis.py`"" -WorkingDirectory $JARVIS_DIR
    Write-Host "JARVIS launching..." -ForegroundColor Green
}
