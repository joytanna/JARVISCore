"""
Windows Native Integration — makes JARVIS a proper Windows app.

Handles:
  - Windows registry registration (startup, default assistant, URI handler)
  - Reading Windows Contacts from %USERPROFILE%\Contacts
  - Windows calendar events (via Windows.ApplicationModel.Calendar WinRT)
  - System notifications via Windows Toast API
  - Opening Windows Settings pages
  - Global hotkey registration
  - Registering as default assistant app
"""
import json
import os
import re
import subprocess
import winreg
from pathlib import Path

import config
from tools.registry import register

_JARVIS_DIR = Path(__file__).parent.parent
_PYTHON_EXE = Path(__file__).parent.parent.parent / "Python" / "Python312" / "python.exe"
_LAUNCH_SCRIPT = _JARVIS_DIR / "jarvis.py"


# ── Contacts ──────────────────────────────────────────────────────────────────

def _read_windows_contacts() -> list:
    """Read contacts from %USERPROFILE%\Contacts (Windows vCard/contact XML files)."""
    contacts = []
    contacts_dir = Path.home() / "Contacts"
    if not contacts_dir.exists():
        return contacts
    for f in contacts_dir.iterdir():
        if f.suffix.lower() == ".contact":
            # Windows .contact is XML
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                name  = re.search(r'<c:FormattedName>(.*?)</c:FormattedName>', text)
                phone = re.search(r'<c:Value[^>]*>(\+?[\d\s\-()]{7,})</c:Value>', text)
                email = re.search(r'<c:Value[^>]*>([^<@]+@[^<]+)</c:Value>', text)
                contacts.append({
                    "name":  name.group(1).strip() if name else f.stem,
                    "phone": re.sub(r'\s+', '', phone.group(1)) if phone else "",
                    "email": email.group(1).strip() if email else "",
                })
            except Exception:
                continue
        elif f.suffix.lower() == ".vcf":
            # vCard file
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
                fn    = re.search(r'^FN:(.+)$', text, re.M)
                tel   = re.search(r'^TEL[^:]*:(.+)$', text, re.M)
                email = re.search(r'^EMAIL[^:]*:(.+)$', text, re.M)
                contacts.append({
                    "name":  fn.group(1).strip() if fn else "",
                    "phone": tel.group(1).strip() if tel else "",
                    "email": email.group(1).strip() if email else "",
                })
            except Exception:
                continue
    return [c for c in contacts if c["name"]]


@register(
    name="get_windows_contacts",
    description="Read contacts from Windows Contacts folder (no permissions required).",
    parameters={"type": "object", "properties": {
        "search": {"type": "string", "description": "Filter by name (optional)"},
    }},
)
def get_windows_contacts(search: str = "") -> str:
    contacts = _read_windows_contacts()
    # Merge with JARVIS memory contacts
    mem_contacts_file = config.MEMORY_DIR / "contacts.json"
    if mem_contacts_file.exists():
        try:
            mem = json.loads(mem_contacts_file.read_text())
            # mem may be a list or dict
            if isinstance(mem, list):
                contacts.extend(mem)
            elif isinstance(mem, dict):
                for name, info in mem.items():
                    contacts.append({"name": name, **(info if isinstance(info, dict) else {})})
        except Exception:
            pass
    if search:
        contacts = [c for c in contacts if search.lower() in c.get("name", "").lower()]
    if not contacts:
        return f"No contacts found{f' matching \"{search}\"' if search else ''}, sir."
    lines = [f"--- Contacts ({len(contacts)}) ---"]
    for c in contacts[:30]:
        name  = c.get("name", "?")
        phone = c.get("phone", "")
        email = c.get("email", "")
        detail = []
        if phone:
            detail.append(phone)
        if email:
            detail.append(email)
        lines.append(f"  {name:30} {' | '.join(detail)}")
    if len(contacts) > 30:
        lines.append(f"  ... and {len(contacts)-30} more")
    return "\n".join(lines)


# ── Windows Startup ───────────────────────────────────────────────────────────

@register(
    name="register_windows_startup",
    description="Add JARVIS to Windows startup so it launches automatically at login.",
    parameters={"type": "object", "properties": {}},
)
def register_windows_startup() -> str:
    try:
        python = _find_python()
        cmd = f'"{python}" "{_LAUNCH_SCRIPT}"'
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "JARVIS", 0, winreg.REG_SZ, cmd)
        winreg.CloseKey(key)
        return "JARVIS added to Windows startup. It will launch automatically at login, sir."
    except Exception as e:
        return f"Startup registration failed: {e}"


@register(
    name="remove_windows_startup",
    description="Remove JARVIS from Windows startup.",
    parameters={"type": "object", "properties": {}},
)
def remove_windows_startup() -> str:
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE
        )
        try:
            winreg.DeleteValue(key, "JARVIS")
            winreg.CloseKey(key)
            return "JARVIS removed from Windows startup, sir."
        except FileNotFoundError:
            return "JARVIS was not registered in startup, sir."
    except Exception as e:
        return f"Error: {e}"


# ── Register as default assistant ─────────────────────────────────────────────

@register(
    name="register_as_default_assistant",
    description="Register JARVIS in Windows registry as a default assistant app and URI handler.",
    parameters={"type": "object", "properties": {}},
)
def register_as_default_assistant() -> str:
    """
    Registers JARVIS in Windows registry:
    1. HKCU\Software\RegisteredApplications
    2. HKCU\Software\JARVIS\Capabilities (appears in Default Apps settings)
    3. HKCU\Software\Classes\jarvis (jarvis:// URI handler)
    4. HKCU\Software\Classes\jarvis\shell\open\command
    """
    try:
        python = _find_python()
        launch = f'"{python}" "{_LAUNCH_SCRIPT}"'

        # 1. App Capabilities (appears in Windows Settings > Default Apps)
        _reg_set(r"Software\JARVIS\Capabilities", "", "JARVIS AI Assistant")
        _reg_set(r"Software\JARVIS\Capabilities", "ApplicationName", "JARVIS")
        _reg_set(r"Software\JARVIS\Capabilities", "ApplicationDescription",
                 "JARVIS — personal AI assistant with voice, tools, and smart home control.")
        _reg_set(r"Software\JARVIS\Capabilities\URLAssociations", "jarvis", "jarvis")

        # 2. Register app
        _reg_set(r"Software\RegisteredApplications", "JARVIS",
                 r"Software\JARVIS\Capabilities")

        # 3. jarvis:// URI scheme handler
        _reg_set(r"Software\Classes\jarvis", "", "JARVIS AI Protocol")
        _reg_set(r"Software\Classes\jarvis", "URL Protocol", "")
        _reg_set(r"Software\Classes\jarvis\DefaultIcon", "", f'"{python}",0')
        _reg_set(r"Software\Classes\jarvis\shell\open\command", "", f'{launch} "%1"')

        # 4. App path for launching via Run dialog or search
        _reg_set(r"Software\Microsoft\Windows\CurrentVersion\App Paths\jarvis.exe",
                 "", python)
        _reg_set(r"Software\Microsoft\Windows\CurrentVersion\App Paths\jarvis.exe",
                 "Path", str(_JARVIS_DIR))

        # 5. Shell command registration (shows in Open With menu)
        _reg_set(r"Software\Classes\Applications\JARVIS.exe",
                 "FriendlyAppName", "JARVIS AI")

        return (
            "JARVIS registered as a Windows app, sir.\n\n"
            "To set as default assistant:\n"
            "  Settings > Apps > Default Apps > scroll to JARVIS\n"
            "  Or say 'jarvis://' as a URI to open JARVIS\n\n"
            "JARVIS will appear in Settings after restarting Explorer or logging out/in."
        )
    except Exception as e:
        return f"Registration error: {e}"


def _reg_set(path: str, name: str, value: str):
    """Create registry key and set a string value under HKCU."""
    key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, path, 0,
                             winreg.KEY_SET_VALUE | winreg.KEY_CREATE_SUB_KEY)
    winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
    winreg.CloseKey(key)


def _find_python() -> str:
    """Find the Python executable path."""
    import sys
    return sys.executable


# ── Windows Settings ──────────────────────────────────────────────────────────

_SETTINGS_PAGES = {
    "default apps":   "ms-settings:defaultapps",
    "apps":           "ms-settings:appsfeatures",
    "privacy":        "ms-settings:privacy",
    "notifications":  "ms-settings:notifications",
    "voice":          "ms-settings:speech",
    "microphone":     "ms-settings:privacy-microphone",
    "bluetooth":      "ms-settings:bluetooth",
    "wifi":           "ms-settings:network-wifi",
    "accessibility":  "ms-settings:easeofaccess",
    "display":        "ms-settings:display",
    "sound":          "ms-settings:sound",
    "startup":        "ms-settings:startupapps",
}

@register(
    name="open_windows_settings",
    description="Open a Windows Settings page (default apps, privacy, notifications, voice, etc.).",
    parameters={"type": "object", "properties": {
        "page": {"type": "string", "description": "Settings page name"},
    }, "required": ["page"]},
)
def open_windows_settings(page: str) -> str:
    key = page.lower().strip()
    uri = _SETTINGS_PAGES.get(key)
    if not uri:
        available = ", ".join(sorted(_SETTINGS_PAGES.keys()))
        return f"Unknown settings page '{page}'. Available: {available}, sir."
    try:
        os.startfile(uri)
        return f"Opening Windows Settings — {page}, sir."
    except Exception as e:
        return f"Could not open settings: {e}"


# ── Windows Notifications ─────────────────────────────────────────────────────

@register(
    name="windows_notify",
    description="Show a Windows toast notification.",
    parameters={"type": "object", "properties": {
        "title":   {"type": "string"},
        "message": {"type": "string"},
    }, "required": ["title", "message"]},
)
def windows_notify(title: str, message: str) -> str:
    """Send a Windows toast notification using PowerShell."""
    try:
        script = f"""
Add-Type -AssemblyName System.Windows.Forms
$n = New-Object System.Windows.Forms.NotifyIcon
$n.Icon = [System.Drawing.SystemIcons]::Information
$n.Visible = $true
$n.ShowBalloonTip(4000, '{title.replace("'", "")}', '{message.replace("'", "")}', [System.Windows.Forms.ToolTipIcon]::None)
Start-Sleep -Milliseconds 4500
$n.Dispose()
"""
        subprocess.Popen(
            ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return f"Notification sent: {title}, sir."
    except Exception as e:
        return f"Notification error: {e}"


# ── System info via WinRT ─────────────────────────────────────────────────────

@register(
    name="get_installed_apps",
    description="List installed Windows apps and programs.",
    parameters={"type": "object", "properties": {
        "search": {"type": "string", "description": "Filter by name"},
        "n":      {"type": "integer", "description": "Max results (default 20)"},
    }},
)
def get_installed_apps(search: str = "", n: int = 20) -> str:
    """Read installed apps from Windows registry."""
    apps = []
    paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    for hive, path in [(winreg.HKEY_LOCAL_MACHINE, p) for p in paths] + \
                      [(winreg.HKEY_CURRENT_USER, paths[0])]:
        try:
            key = winreg.OpenKey(hive, path)
            for i in range(winreg.QueryInfoKey(key)[0]):
                try:
                    sub_name = winreg.EnumKey(key, i)
                    sub_key  = winreg.OpenKey(key, sub_name)
                    try:
                        name, _ = winreg.QueryValueEx(sub_key, "DisplayName")
                        if name and (not search or search.lower() in name.lower()):
                            apps.append(name)
                    except FileNotFoundError:
                        pass
                    winreg.CloseKey(sub_key)
                except Exception:
                    continue
            winreg.CloseKey(key)
        except Exception:
            continue
    apps = sorted(set(apps))
    if not apps:
        return f"No apps found{f' matching \"{search}\"' if search else ''}, sir."
    shown = apps[:n]
    lines = [f"--- Installed Apps ({len(apps)} total) ---"]
    lines.extend(f"  {a}" for a in shown)
    if len(apps) > n:
        lines.append(f"  ... and {len(apps)-n} more")
    return "\n".join(lines)


# ── Clipboard (Windows-native) ────────────────────────────────────────────────

@register(
    name="set_clipboard",
    description="Set text content to the Windows clipboard.",
    parameters={"type": "object", "properties": {
        "text": {"type": "string"},
    }, "required": ["text"]},
)
def set_clipboard(text: str) -> str:
    try:
        import subprocess
        proc = subprocess.Popen(
            ["clip"], stdin=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        proc.communicate(text.encode("utf-16-le"))
        return f"Clipboard set ({len(text)} chars), sir."
    except Exception as e:
        return f"Clipboard error: {e}"


# ── Windows App shortcuts (open by name) ──────────────────────────────────────

@register(
    name="open_windows_app",
    description="Open a built-in Windows app by name (settings, calculator, notepad, calendar, contacts, etc.).",
    parameters={"type": "object", "properties": {
        "app": {"type": "string", "description": "App name"},
    }, "required": ["app"]},
)
def open_windows_app(app: str) -> str:
    """Open Windows built-in apps via their ms-* URI schemes or shell commands."""
    _apps = {
        "settings":      "ms-settings:",
        "calculator":    "calculator:",
        "calendar":      "outlookcal:",
        "contacts":      "ms-people:",
        "mail":          "ms-outlook:",
        "maps":          "bingmaps:",
        "camera":        "ms-camera:",
        "phone":         "ms-phone:",
        "photos":        "ms-photos:",
        "store":         "ms-windows-store:",
        "notepad":       "notepad.exe",
        "paint":         "mspaint.exe",
        "explorer":      "explorer.exe",
        "task manager":  "taskmgr.exe",
        "device manager":"devmgmt.msc",
        "snipping tool": "snippingtool.exe",
        "xbox":          "xbox:",
        "spotify":       "spotify:",
        "microsoft edge":"microsoft-edge:",
    }
    key = app.lower().strip()
    uri = _apps.get(key)
    if not uri:
        # Try to open directly
        try:
            os.startfile(key)
            return f"Attempting to open '{app}', sir."
        except Exception:
            available = ", ".join(sorted(_apps.keys()))
            return f"Unknown app '{app}'. Try: {available}, sir."
    try:
        if uri.endswith(".exe") or uri.endswith(".msc"):
            subprocess.Popen(uri, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.startfile(uri)
        return f"Opening {app.title()}, sir."
    except Exception as e:
        return f"Could not open {app}: {e}"
