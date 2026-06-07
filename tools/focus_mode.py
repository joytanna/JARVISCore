"""
Focus Mode — Block distracting apps and protect deep-work sessions.
Optionally kills specified processes for the duration of a focus block.
"""
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import config
from tools.registry import register

_DIR = config.MEMORY_DIR / "focus"
_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _DIR / "focus_log.json"

import json

# ── State ──────────────────────────────────────────────────────────────────────
_focus_active   = False
_focus_end_ts   = 0.0
_focus_label    = ""
_focus_lock     = threading.Lock()

# Default list of apps considered distracting (process name fragments)
_DEFAULT_DISTRACTORS = [
    "chrome", "firefox", "msedge", "opera",
    "discord", "slack", "teams",
    "steam", "epicgameslauncher",
    "spotify",
    "netflix", "primevideo",
    "twitter", "facebook",
]


def _kill_processes(names: list[str]) -> list[str]:
    """Kill processes whose name contains any of the given fragments. Returns list killed."""
    killed = []
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name"]):
            pn = proc.info.get("name", "").lower()
            for n in names:
                if n.lower() in pn:
                    try:
                        proc.kill()
                        killed.append(proc.info["name"])
                    except Exception:
                        pass
                    break
    except Exception:
        pass
    return killed


def _log_session(label: str, start: float, end: float, duration_min: int):
    try:
        import json
        data = []
        if _LOG_FILE.exists():
            try:
                data = json.loads(_LOG_FILE.read_text())
            except Exception:
                pass
        data.append({
            "label":       label,
            "start":       datetime.fromtimestamp(start).isoformat(),
            "end":         datetime.fromtimestamp(end).isoformat(),
            "duration_min": duration_min,
        })
        _LOG_FILE.write_text(json.dumps(data[-100:], indent=2))  # keep last 100 sessions
    except Exception:
        pass


def _focus_timer(duration_min: int, label: str, kill_list: list[str]):
    global _focus_active
    start_ts = time.time()
    end_ts   = start_ts + duration_min * 60
    time.sleep(duration_min * 60)
    with _focus_lock:
        _focus_active = False
    _log_session(label, start_ts, time.time(), duration_min)
    # Notify
    try:
        from voice.speaker import speak
        speak(f"Focus session complete. {duration_min} minutes on {label}. Well done, sir.")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Focus session '{label}' complete!\n{duration_min} minutes of deep work. Take a break.",
            "JARVIS — Focus Mode",
            0x40,
        )
    except Exception:
        pass


# ── Enable Focus Mode ──────────────────────────────────────────────────────────
@register(
    name="enable_focus_mode",
    description=(
        "Start a focus/deep-work session. Optionally kills distracting apps "
        "(Chrome, Discord, Slack, Spotify, Steam, etc.) for the duration."
    ),
    parameters={"type": "object", "properties": {
        "duration_min": {"type": "integer", "description": "Session length in minutes (default 25)"},
        "task":         {"type": "string",  "description": "What you're working on"},
        "kill_apps":    {"type": "boolean", "description": "Kill distracting apps for the session (default False)"},
        "custom_kill":  {"type": "string",  "description": "Comma-separated extra process names to kill"},
    }},
)
def enable_focus_mode(duration_min: int = 25, task: str = "Deep work",
                      kill_apps: bool = False, custom_kill: str = "") -> str:
    global _focus_active, _focus_end_ts, _focus_label

    with _focus_lock:
        if _focus_active:
            rem = max(0, int(_focus_end_ts - time.time()))
            return (f"Focus mode already active — '{_focus_label}' — "
                    f"{rem//60}m {rem%60}s remaining, sir.")
        _focus_active = True
        _focus_end_ts = time.time() + duration_min * 60
        _focus_label  = task

    kill_list = _DEFAULT_DISTRACTORS.copy()
    if custom_kill:
        kill_list += [x.strip() for x in custom_kill.split(",")]

    killed = []
    if kill_apps:
        killed = _kill_processes(kill_list)

    threading.Thread(
        target=_focus_timer,
        args=(duration_min, task, kill_list),
        daemon=True,
        name="focus-timer",
    ).start()

    killed_msg = f" Killed: {', '.join(killed[:5])}." if killed else ""
    return (f"Focus mode enabled for {duration_min} min on '{task}'."
            f"{killed_msg} I'll notify you when done, sir.")


# ── Disable Focus Mode ─────────────────────────────────────────────────────────
@register(
    name="disable_focus_mode",
    description="End the current focus session early.",
    parameters={"type": "object", "properties": {}},
)
def disable_focus_mode() -> str:
    global _focus_active
    with _focus_lock:
        if not _focus_active:
            return "No focus session is currently active, sir."
        elapsed = max(0, int(time.time() - (_focus_end_ts - _focus_label.__len__()*0 - 1500)))
        _focus_active = False
    return "Focus mode disabled. Good work, sir."


# ── Focus Status ───────────────────────────────────────────────────────────────
@register(
    name="focus_status",
    description="Check if focus mode is currently active.",
    parameters={"type": "object", "properties": {}},
)
def focus_status() -> str:
    if not _focus_active:
        # Show recent sessions
        data = []
        if _LOG_FILE.exists():
            try:
                data = json.loads(_LOG_FILE.read_text())
            except Exception:
                pass
        if data:
            last = data[-1]
            return (f"No focus session active.\n"
                    f"Last session: '{last['label']}' — {last['duration_min']} min on {last['end'][:10]}, sir.")
        return "No focus session active, sir."
    rem = max(0, int(_focus_end_ts - time.time()))
    return (f"Focus mode ACTIVE — '{_focus_label}' — "
            f"{rem//60}m {rem%60}s remaining, sir.")


# ── Focus History ──────────────────────────────────────────────────────────────
@register(
    name="focus_history",
    description="Show your recent focus session history and total deep-work time.",
    parameters={"type": "object", "properties": {
        "n": {"type": "integer", "description": "Number of sessions to show (default 10)"},
    }},
)
def focus_history(n: int = 10) -> str:
    if not _LOG_FILE.exists():
        return "No focus sessions logged yet, sir."
    try:
        data = json.loads(_LOG_FILE.read_text())
    except Exception:
        return "Could not read focus log, sir."
    if not data:
        return "No focus sessions logged yet, sir."
    recent = data[-n:]
    total_min = sum(s.get("duration_min", 0) for s in data)
    lines = [f"Focus History ({len(data)} sessions, {total_min} min total):"]
    for s in reversed(recent):
        lines.append(f"  {s['start'][:16]}  {s['duration_min']:>3} min  '{s['label']}'")
    return "\n".join(lines)


# ── Add Distractor App ─────────────────────────────────────────────────────────
@register(
    name="add_distractor_app",
    description="Add an app to the distracting-apps list for future focus sessions.",
    parameters={"type": "object", "properties": {
        "name": {"type": "string", "description": "Process name fragment, e.g. 'whatsapp'"},
    }, "required": ["name"]},
)
def add_distractor_app(name: str) -> str:
    cfg_file = _DIR / "distractors.json"
    try:
        apps = json.loads(cfg_file.read_text()) if cfg_file.exists() else list(_DEFAULT_DISTRACTORS)
        n = name.lower().strip()
        if n not in apps:
            apps.append(n)
            cfg_file.write_text(json.dumps(apps, indent=2))
            return f"'{name}' added to distractor list, sir."
        return f"'{name}' is already in the distractor list, sir."
    except Exception as e:
        return f"Error updating distractor list: {e}"
