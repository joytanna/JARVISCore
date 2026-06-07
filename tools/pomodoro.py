"""
Pomodoro Timer — focus in 25-minute sprints, rest in 5-minute breaks.
Background thread counts down; announces via voice + beep when time is up.
Logs completed sessions so you can track total focused time.
"""
import json
import threading
import time
from datetime import datetime, date
from pathlib import Path

import config
from tools.registry import register

_DIR  = config.MEMORY_DIR / "pomodoro"
_DIR.mkdir(parents=True, exist_ok=True)
_LOG  = _DIR / "sessions.json"

# State
_state = {
    "mode":       None,     # "work" | "break" | "long_break" | None
    "task":       "",
    "end_time":   0.0,
    "start_time": 0.0,
    "work_mins":  25,
    "break_mins": 5,
    "session_n":  0,        # completed work sessions in this cycle
    "timer":      None,     # threading.Timer reference
}
_lock = threading.Lock()


def _log_session(task: str, duration_mins: int):
    log = []
    if _LOG.exists():
        try:
            log = json.loads(_LOG.read_text())
        except Exception:
            pass
    log.append({"date": date.today().isoformat(),
                "time": datetime.now().strftime("%H:%M"),
                "task": task, "duration_mins": duration_mins})
    # Keep last 200 sessions
    _LOG.write_text(json.dumps(log[-200:], indent=2))


def _beep_and_announce(message: str):
    try:
        import winsound
        for _ in range(3):
            winsound.Beep(880, 400)
            time.sleep(0.15)
    except Exception:
        pass
    try:
        from voice.speaker import speak
        speak(message)
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, "JARVIS Pomodoro", 0x40)
    except Exception:
        pass


def _on_work_done():
    with _lock:
        task = _state["task"]
        mins = _state["work_mins"]
        _state["session_n"] += 1
        n = _state["session_n"]
        _log_session(task, mins)
        if n % 4 == 0:
            brk = 15
            _state["mode"] = "long_break"
        else:
            brk = _state["break_mins"]
            _state["mode"] = "break"
        _state["end_time"]   = time.time() + brk * 60
        _state["start_time"] = time.time()
        msg = (f"Pomodoro {n} complete! Time for a "
               f"{'long break (15 min)' if n%4==0 else f'{brk}-minute break'}, sir.")
        t = threading.Timer(brk * 60, _on_break_done)
        t.daemon = True
        _state["timer"] = t
    t.start()
    _beep_and_announce(msg)


def _on_break_done():
    with _lock:
        _state["mode"] = None
        _state["timer"] = None
    _beep_and_announce("Break is over! Ready for the next Pomodoro, sir. "
                       "Say 'start pomodoro' when you're ready.")


# ── Start ─────────────────────────────────────────────────────────────────────
@register(
    name="start_pomodoro",
    description="Start a Pomodoro work session (default 25 min). Say what you're working on.",
    parameters={"type": "object", "properties": {
        "task":      {"type": "string",  "description": "What you're working on"},
        "work_mins": {"type": "integer", "description": "Work duration in minutes (default 25)"},
    }},
)
def start_pomodoro(task: str = "focused work", work_mins: int = 25) -> str:
    with _lock:
        if _state["mode"] == "work":
            remaining = max(0, int(_state["end_time"] - time.time()))
            m, s = divmod(remaining, 60)
            return (f"Pomodoro already running — {m}m {s}s left on '{_state['task']}', sir. "
                    f"Say 'stop pomodoro' to cancel.")
        if _state["mode"] in ("break", "long_break"):
            remaining = max(0, int(_state["end_time"] - time.time()))
            m, s = divmod(remaining, 60)
            return f"On break — {m}m {s}s left. Finish the break or say 'stop pomodoro', sir."
        work_mins = max(1, min(120, work_mins))
        _state.update({
            "mode": "work", "task": task,
            "work_mins": work_mins,
            "start_time": time.time(),
            "end_time": time.time() + work_mins * 60,
        })
        t = threading.Timer(work_mins * 60, _on_work_done)
        t.daemon = True
        _state["timer"] = t
    t.start()
    return (f"Pomodoro started — {work_mins} minutes on '{task}'. "
            f"Focus up, sir. I'll alert you when it's done.")


# ── Stop ──────────────────────────────────────────────────────────────────────
@register(
    name="stop_pomodoro",
    description="Stop the current Pomodoro or break early.",
    parameters={"type": "object", "properties": {}},
)
def stop_pomodoro() -> str:
    with _lock:
        if _state["mode"] is None:
            return "No Pomodoro is running, sir."
        if _state["timer"]:
            _state["timer"].cancel()
        mode      = _state["mode"]
        task      = _state["task"]
        elapsed_s = int(time.time() - _state["start_time"])
        _state["mode"]  = None
        _state["timer"] = None
    m, s = divmod(elapsed_s, 60)
    if mode == "work":
        _log_session(task, elapsed_s // 60)
        return f"Pomodoro stopped after {m}m {s}s on '{task}', sir."
    return f"Break stopped after {m}m {s}s, sir."


# ── Status ────────────────────────────────────────────────────────────────────
@register(
    name="pomodoro_status",
    description="Check current Pomodoro timer status and today's session count.",
    parameters={"type": "object", "properties": {}},
)
def pomodoro_status() -> str:
    with _lock:
        mode  = _state["mode"]
        task  = _state["task"]
        end_t = _state["end_time"]
        n     = _state["session_n"]
    # Today's completed sessions from log
    today = date.today().isoformat()
    today_n = 0
    today_mins = 0
    if _LOG.exists():
        try:
            log = json.loads(_LOG.read_text())
            today_sessions = [s for s in log if s.get("date") == today]
            today_n    = len(today_sessions)
            today_mins = sum(s.get("duration_mins", 0) for s in today_sessions)
        except Exception:
            pass
    if mode is None:
        return (f"No Pomodoro running.\n"
                f"Today: {today_n} session{'s' if today_n!=1 else ''}, "
                f"{today_mins} minutes of focused work, sir.")
    remaining = max(0, int(end_t - time.time()))
    m, s = divmod(remaining, 60)
    label = {"work": f"Working on '{task}'",
             "break": "On a break",
             "long_break": "On a long break"}[mode]
    return (f"{label} — {m}m {s}s remaining.\n"
            f"Today: {today_n} Pomodoro{'s' if today_n!=1 else ''} complete, "
            f"{today_mins} mins focused, sir.")


# ── History ───────────────────────────────────────────────────────────────────
@register(
    name="pomodoro_history",
    description="Show Pomodoro session history and total focused time statistics.",
    parameters={"type": "object", "properties": {
        "days": {"type": "integer", "description": "Days to look back (default 7)"},
    }},
)
def pomodoro_history(days: int = 7) -> str:
    if not _LOG.exists():
        return "No Pomodoro sessions logged yet, sir."
    try:
        log = json.loads(_LOG.read_text())
    except Exception:
        return "Error reading session log, sir."
    from datetime import timedelta
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    recent = [s for s in log if s.get("date", "") >= cutoff]
    if not recent:
        return f"No sessions in the last {days} days, sir."
    total_mins = sum(s.get("duration_mins", 0) for s in recent)
    hours, mins = divmod(total_mins, 60)
    # Group by date
    by_day: dict = {}
    for s in recent:
        d = s.get("date", "?")
        by_day.setdefault(d, []).append(s)
    lines = [f"--- Pomodoro History (last {days}d: {len(recent)} sessions, "
             f"{hours}h {mins}m total) ---"]
    for d in sorted(by_day.keys(), reverse=True):
        sessions  = by_day[d]
        day_mins  = sum(s.get("duration_mins", 0) for s in sessions)
        lines.append(f"  {d}  ({len(sessions)} sessions, {day_mins}m)")
        for s in sessions[:3]:
            lines.append(f"    • {s.get('time','?')}  {s.get('task','?')} ({s.get('duration_mins',0)}m)")
        if len(sessions) > 3:
            lines.append(f"    … +{len(sessions)-3} more")
    return "\n".join(lines)
