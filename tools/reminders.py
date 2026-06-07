"""Proactive reminders — fire a spoken + UI alert at a specified time."""
import re, datetime, threading, time
from tools.registry import register

_reminders: list[dict] = []
_lock = threading.Lock()
_speak_fn  = None  # injected by jarvis.py
_notify_fn = None  # injected by jarvis.py


def set_callbacks(speak, notify):
    global _speak_fn, _notify_fn
    _speak_fn  = speak
    _notify_fn = notify


def _parse_delay(when: str) -> int | None:
    """Convert natural-language time to delay in seconds. Returns None if unparseable."""
    w = when.lower().strip()

    # "in X minutes/hours/seconds"
    m = re.match(r"in\s+(\d+)\s*(sec|min|hour|hr|day)", w)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        return n * {"sec": 1, "min": 60, "hour": 3600, "hr": 3600, "day": 86400}[unit]

    # "at HH:MM am/pm" or "at 3pm"
    m = re.match(r"at\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", w)
    if m:
        hour   = int(m.group(1))
        minute = int(m.group(2) or 0)
        ampm   = m.group(3)
        if ampm == "pm" and hour != 12: hour += 12
        if ampm == "am" and hour == 12: hour  = 0
        now    = datetime.datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += datetime.timedelta(days=1)
        return max(1, int((target - now).total_seconds()))

    return None


def _fire(rid: int, task: str):
    msg = f"Reminder, sir: {task}"
    try:
        if _speak_fn:  _speak_fn(msg)
        if _notify_fn: _notify_fn(f"⏰ {task}", "jarvis")
    except Exception:
        pass
    with _lock:
        global _reminders
        _reminders = [r for r in _reminders if r["id"] != rid]


@register(
    name="set_reminder",
    description="Set a reminder to fire at a specific time (e.g. 'in 20 minutes', 'at 3pm')",
    parameters={
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "What to remind about"},
            "when": {"type": "string", "description": "When: 'in 20 minutes', 'in 2 hours', 'at 3pm'"},
        },
        "required": ["task", "when"],
    },
)
def set_reminder(task: str, when: str) -> str:
    delay = _parse_delay(when)
    if delay is None:
        return f"Could not parse time '{when}', sir. Try 'in 20 minutes' or 'at 3pm'."
    if delay < 5:
        return "That time has already passed, sir."

    with _lock:
        rid = int(time.time() * 1000)
        timer = threading.Timer(delay, _fire, args=(rid, task))
        timer.daemon = True
        timer.start()
        _reminders.append({"id": rid, "task": task, "timer": timer,
                           "fires_at": datetime.datetime.now() + datetime.timedelta(seconds=delay)})

    mins = delay // 60
    secs = delay % 60
    human = f"{mins}m {secs}s" if mins else f"{secs}s"
    return f"Reminder set for '{task}' in {human}, sir."


@register(
    name="list_reminders",
    description="List all active reminders",
    parameters={"type": "object", "properties": {}},
)
def list_reminders() -> str:
    with _lock:
        if not _reminders:
            return "No active reminders, sir."
        lines = [f"• {r['task']} — fires at {r['fires_at'].strftime('%H:%M:%S')}"
                 for r in _reminders]
    return "\n".join(lines)


@register(
    name="cancel_reminder",
    description="Cancel a reminder by task keyword",
    parameters={
        "type": "object",
        "properties": {"keyword": {"type": "string"}},
        "required": ["keyword"],
    },
)
def cancel_reminder(keyword: str) -> str:
    with _lock:
        global _reminders
        kw = keyword.lower()
        cancelled = [r for r in _reminders if kw in r["task"].lower()]
        if not cancelled:
            return f"No reminder matching '{keyword}', sir."
        for r in cancelled:
            r["timer"].cancel()
        _reminders = [r for r in _reminders if r not in cancelled]
    return f"Cancelled {len(cancelled)} reminder(s), sir."
