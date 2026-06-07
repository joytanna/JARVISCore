"""App launcher, switcher, and closer."""
import subprocess, os, difflib
from tools.registry import register

# Common app name → executable mapping (Windows)
_APPS: dict[str, str] = {
    "chrome":              "chrome",
    "google chrome":       "chrome",
    "firefox":             "firefox",
    "edge":                "msedge",
    "microsoft edge":      "msedge",
    "vs code":             "code",
    "vscode":              "code",
    "visual studio code":  "code",
    "notepad":             "notepad",
    "notepad++":           "notepad++",
    "calculator":          "calc",
    "spotify":             "spotify",
    "discord":             "discord",
    "slack":               "slack",
    "teams":               "teams",
    "microsoft teams":     "teams",
    "word":                "winword",
    "excel":               "excel",
    "powerpoint":          "powerpnt",
    "outlook":             "outlook",
    "file explorer":       "explorer",
    "explorer":            "explorer",
    "task manager":        "taskmgr",
    "cmd":                 "cmd",
    "terminal":            "wt",
    "windows terminal":    "wt",
    "paint":               "mspaint",
    "settings":            "ms-settings:",
    "control panel":       "control",
    "vlc":                 "vlc",
    "zoom":                "zoom",
    "obs":                 "obs64",
    "steam":               "steam",
    "whatsapp":            "whatsapp",
    "telegram":            "telegram",
}


def _resolve(name: str) -> str | None:
    n = name.lower().strip()
    if n in _APPS:
        return _APPS[n]
    matches = difflib.get_close_matches(n, _APPS.keys(), n=1, cutoff=0.6)
    return _APPS[matches[0]] if matches else None


@register(
    name="open_app",
    description="Open an application by name (e.g. Chrome, Spotify, VS Code)",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def open_app(name: str) -> str:
    exe = _resolve(name)
    if not exe:
        return f"Don't know how to open '{name}', sir. Try the exact app name."
    try:
        if exe.startswith("ms-"):
            os.startfile(exe)
        else:
            subprocess.Popen(exe, shell=True,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
        return f"Opening {name}, sir."
    except Exception as e:
        return f"Could not open {name}: {e}"


@register(
    name="close_app",
    description="Close/kill a running application by name",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def close_app(name: str) -> str:
    exe = _resolve(name) or name
    # Strip path separators for taskkill
    proc = exe.replace("/", "").replace("\\", "")
    if not proc.endswith(".exe"):
        proc += ".exe"
    try:
        result = subprocess.run(
            ["taskkill", "/F", "/IM", proc],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            return f"Closed {name}, sir."
        return f"Could not close {name}: {result.stderr.strip()}"
    except Exception as e:
        return f"Error closing {name}: {e}"


@register(
    name="switch_to_app",
    description="Bring an already-open application window to the foreground",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def switch_to_app(name: str) -> str:
    try:
        import pygetwindow as gw
        wins = gw.getWindowsWithTitle(name)
        if not wins:
            # fuzzy: find any window whose title contains name
            all_wins = gw.getAllTitles()
            matches = [t for t in all_wins if name.lower() in t.lower() and t.strip()]
            if not matches:
                return f"No window found matching '{name}', sir."
            wins = gw.getWindowsWithTitle(matches[0])
        wins[0].activate()
        return f"Switched to {name}, sir."
    except ImportError:
        # Fallback: use PowerShell
        try:
            subprocess.run(
                ["powershell", "-Command",
                 f'(Get-Process | Where-Object {{$_.MainWindowTitle -like "*{name}*"}} '
                 f'| Select-Object -First 1).MainWindowHandle | '
                 f'ForEach-Object {{[void][System.Runtime.InteropServices.Marshal]::GetIUnknownForObject($_)}}'],
                capture_output=True, timeout=5,
            )
            return f"Attempted to switch to {name}, sir."
        except Exception as e:
            return f"Switch failed: {e}"
    except Exception as e:
        return f"Switch failed: {e}"
