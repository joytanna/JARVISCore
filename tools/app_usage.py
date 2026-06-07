"""
App Usage Tracker — passively tracks which apps you use and for how long.
Samples the foreground window every 10 s (negligible CPU). Shows daily/weekly
usage stats and helps identify your most-used (or most distracting) apps.
"""
import json
import threading
import time
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import config
from tools.registry import register

_DIR      = config.MEMORY_DIR / "usage"
_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _DIR / "usage_log.json"
_LOCK     = threading.Lock()

_tracking = True   # set False to pause


def _get_foreground_app() -> str:
    """Return the process name of the active window (Windows only)."""
    try:
        import ctypes
        import ctypes.wintypes
        user32   = ctypes.windll.user32
        hwnd     = user32.GetForegroundWindow()
        pid      = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        import psutil
        p = psutil.Process(pid.value)
        return p.name().lower().replace(".exe", "")
    except Exception:
        return ""


def _load_log() -> dict:
    if _LOG_FILE.exists():
        try:
            return json.loads(_LOG_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_log(data: dict):
    _LOG_FILE.write_text(json.dumps(data, indent=2))


def _tracker():
    """Background thread — samples foreground app every 10 s."""
    INTERVAL = 10  # seconds
    while True:
        if _tracking:
            app = _get_foreground_app()
            if app:
                today = date.today().isoformat()
                with _LOCK:
                    log = _load_log()
                    if today not in log:
                        log[today] = {}
                    log[today][app] = log[today].get(app, 0) + INTERVAL
                    # Keep only last 30 days
                    days = sorted(log.keys())
                    if len(days) > 30:
                        for old in days[:-30]:
                            del log[old]
                    _save_log(log)
        time.sleep(10)


threading.Thread(target=_tracker, daemon=True, name="usage-tracker").start()


# ── Today's Usage ─────────────────────────────────────────────────────────────
@register(
    name="app_usage_today",
    description="Show which apps you've used today and for how long.",
    parameters={"type": "object", "properties": {
        "top": {"type": "integer", "description": "Top N apps to show (default 10)"},
    }},
)
def app_usage_today(top: int = 10) -> str:
    log   = _load_log()
    today = date.today().isoformat()
    usage = log.get(today, {})
    if not usage:
        return "No app usage recorded yet today, sir."
    total_s = sum(usage.values())
    items   = sorted(usage.items(), key=lambda x: -x[1])[:top]
    lines   = [f"--- App Usage Today ({_fmt_time(total_s)} total) ---"]
    for app, secs in items:
        pct = secs / total_s * 100
        bar = "#" * min(20, int(pct / 5))
        lines.append(f"  {app:22} {bar:20} {_fmt_time(secs):>8}  {pct:.0f}%")
    return "\n".join(lines)


def _fmt_time(secs: int) -> str:
    h, r = divmod(secs, 3600)
    m, s = divmod(r, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


# ── Weekly Summary ─────────────────────────────────────────────────────────────
@register(
    name="app_usage_weekly",
    description="Show app usage summary for the past 7 days.",
    parameters={"type": "object", "properties": {
        "top": {"type": "integer", "description": "Top N apps to show (default 10)"},
    }},
)
def app_usage_weekly(top: int = 10) -> str:
    log   = _load_log()
    today = date.today()
    totals: dict = defaultdict(int)
    for i in range(7):
        day   = (today - timedelta(days=i)).isoformat()
        usage = log.get(day, {})
        for app, secs in usage.items():
            totals[app] += secs

    if not totals:
        return "No usage data for the past 7 days, sir."
    grand = sum(totals.values())
    items = sorted(totals.items(), key=lambda x: -x[1])[:top]
    lines = [f"--- Weekly App Usage ({_fmt_time(grand)} total) ---"]
    for app, secs in items:
        pct = secs / grand * 100
        bar = "#" * min(20, int(pct / 5))
        lines.append(f"  {app:22} {bar:20} {_fmt_time(secs):>9}  {pct:.0f}%")
    return "\n".join(lines)


# ── Most Used / Most Distracting ───────────────────────────────────────────────
_DISTRACTING = {
    "chrome", "firefox", "msedge", "opera",
    "discord", "slack", "teams",
    "steam", "epicgameslauncher",
    "spotify", "netflix",
    "youtube", "twitch",
}

@register(
    name="productivity_score",
    description="Calculate today's productivity score based on app usage (productive vs distracting apps).",
    parameters={"type": "object", "properties": {}},
)
def productivity_score() -> str:
    log   = _load_log()
    today = date.today().isoformat()
    usage = log.get(today, {})
    if not usage:
        return "No usage data for today yet, sir."

    distract_s  = sum(s for app, s in usage.items() if any(d in app for d in _DISTRACTING))
    total_s     = sum(usage.values())
    productive_s= total_s - distract_s
    if total_s == 0:
        return "No usage recorded today, sir."
    score = int(productive_s / total_s * 100)
    grade = ("A" if score >= 80 else "B" if score >= 65
             else "C" if score >= 50 else "D" if score >= 35 else "F")

    return (f"Productivity Score: {score}/100  (Grade: {grade})\n"
            f"Productive time:   {_fmt_time(productive_s)}\n"
            f"Distracting time:  {_fmt_time(distract_s)}\n"
            f"Total screen time: {_fmt_time(total_s)}, sir.")


# ── Pause / Resume ────────────────────────────────────────────────────────────
@register(
    name="pause_usage_tracking",
    description="Pause or resume app usage tracking (e.g. during private sessions).",
    parameters={"type": "object", "properties": {
        "pause": {"type": "boolean", "description": "True to pause, False to resume"},
    }},
)
def pause_usage_tracking(pause: bool = True) -> str:
    global _tracking
    _tracking = not pause
    state = "paused" if pause else "resumed"
    return f"App usage tracking {state}, sir."
