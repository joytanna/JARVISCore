"""
Smart Alarm System — set, list, cancel and snooze time-based alarms.
Uses winsound for audio alerts and Windows MessageBox for visual notification.
Background thread checks every 30 s — zero CPU when idle.
"""
import json
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

import config
from tools.registry import register

_DIR  = config.MEMORY_DIR / "alarms"
_DIR.mkdir(parents=True, exist_ok=True)
_FILE = _DIR / "alarms.json"
_LOCK = threading.Lock()


# ── Persistence ────────────────────────────────────────────────────────────────
def _load() -> list:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text())
        except Exception:
            pass
    return []


def _save(data: list):
    _FILE.write_text(json.dumps(data, indent=2))


# ── Time parser ────────────────────────────────────────────────────────────────
def _parse_time(when: str) -> float:
    now  = datetime.now()
    text = when.lower().strip()

    # "in X minutes/hours"
    m = re.search(r'in\s+(\d+)\s*(min|hour)', text)
    if m:
        n     = int(m.group(1))
        delta = timedelta(hours=n) if 'hour' in m.group(2) else timedelta(minutes=n)
        return (now + delta).timestamp()

    # "HH:MM am/pm"  or  "HH:MM"
    m = re.search(r'(\d{1,2}):(\d{2})\s*(am|pm)?', text)
    if m:
        hr, mn = int(m.group(1)), int(m.group(2))
        ap = m.group(3)
        if ap == 'pm' and hr != 12: hr += 12
        if ap == 'am' and hr == 12: hr  = 0
        t = now.replace(hour=hr, minute=mn, second=0, microsecond=0)
        if t <= now:
            t += timedelta(days=1)
        return t.timestamp()

    # "7pm"  "9 am"
    m = re.search(r'(\d{1,2})\s*(am|pm)', text)
    if m:
        hr, ap = int(m.group(1)), m.group(2)
        if ap == 'pm' and hr != 12: hr += 12
        if ap == 'am' and hr == 12: hr  = 0
        t = now.replace(hour=hr, minute=0, second=0, microsecond=0)
        if t <= now:
            t += timedelta(days=1)
        return t.timestamp()

    # Fallback — 1 hour
    return (now + timedelta(hours=1)).timestamp()


# ── Ring ───────────────────────────────────────────────────────────────────────
def _ring(label: str):
    try:
        import winsound
        for _ in range(3):
            winsound.Beep(880, 500)
            time.sleep(0.25)
    except Exception:
        pass
    try:
        from voice.speaker import speak
        speak(f"Alarm: {label}, sir.")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f"⏰ {label}", "JARVIS — Alarm", 0x40)
    except Exception:
        pass


# ── Background watcher ─────────────────────────────────────────────────────────
def _watcher():
    while True:
        now = time.time()
        with _LOCK:
            alarms  = _load()
            changed = False
            for a in alarms:
                if not a.get('fired') and a.get('ts', 0) <= now:
                    a['fired'] = True
                    changed    = True
                    threading.Thread(target=_ring,
                                     args=(a.get('label', 'Alarm'),),
                                     daemon=True).start()
            if changed:
                _save(alarms)
        time.sleep(30)


threading.Thread(target=_watcher, daemon=True, name="alarm-watcher").start()


# ── Tools ──────────────────────────────────────────────────────────────────────
@register(
    name="set_alarm",
    description="Set an alarm for a specific time or duration. e.g. '7:30 am', '9pm', 'in 45 minutes'.",
    parameters={"type": "object", "properties": {
        "when":  {"type": "string", "description": "When to ring: '7:30 am', '9pm', 'in 30 minutes'"},
        "label": {"type": "string", "description": "Alarm label / reason"},
    }, "required": ["when"]},
)
def set_alarm(when: str, label: str = "Alarm") -> str:
    ts = _parse_time(when)
    dt = datetime.fromtimestamp(ts)
    with _LOCK:
        alarms = _load()
        alarms.append({"label": label, "ts": ts,
                        "created": datetime.now().isoformat(), "fired": False})
        _save(alarms)
    return f"Alarm '{label}' set for {dt.strftime('%a %b %d at %H:%M')}, sir."


@register(
    name="list_alarms",
    description="List all pending alarms.",
    parameters={"type": "object", "properties": {}},
)
def list_alarms() -> str:
    alarms  = _load()
    pending = [a for a in alarms if not a.get('fired')]
    if not pending:
        return "No pending alarms, sir."
    now   = time.time()
    lines = []
    for a in sorted(pending, key=lambda x: x.get('ts', 0)):
        dt    = datetime.fromtimestamp(a['ts'])
        rem   = max(0, int(a['ts'] - now))
        h, r  = divmod(rem, 3600)
        m, s  = divmod(r, 60)
        rem_s = (f"{h}h {m}m" if h else f"{m}m {s}s")
        lines.append(f"⏰ {dt.strftime('%a %H:%M')}  '{a['label']}'  (in {rem_s})")
    return "\n".join(lines)


@register(
    name="cancel_alarm",
    description="Cancel a pending alarm by label.",
    parameters={"type": "object", "properties": {
        "label": {"type": "string", "description": "Alarm label (partial match ok)"},
    }, "required": ["label"]},
)
def cancel_alarm(label: str) -> str:
    q  = label.lower()
    with _LOCK:
        alarms = _load()
        count  = 0
        for a in alarms:
            if q in a.get('label', '').lower() and not a.get('fired'):
                a['fired'] = True
                count += 1
        _save(alarms)
    return (f"Cancelled {count} alarm(s) matching '{label}', sir."
            if count else f"No alarm found matching '{label}', sir.")


@register(
    name="snooze_alarm",
    description="Snooze the most recently fired alarm.",
    parameters={"type": "object", "properties": {
        "minutes": {"type": "integer", "description": "Snooze duration in minutes (default 5)"},
    }},
)
def snooze_alarm(minutes: int = 5) -> str:
    with _LOCK:
        alarms = _load()
        fired  = [a for a in alarms if a.get('fired')]
        if not fired:
            return "No recently fired alarms to snooze, sir."
        last         = max(fired, key=lambda x: x.get('ts', 0))
        last['ts']   = time.time() + minutes * 60
        last['fired']= False
        last['label']= f"Snoozed: {last.get('label', 'Alarm')}"
        _save(alarms)
    dt = datetime.fromtimestamp(last['ts'])
    return f"Snoozed {minutes} minutes. Rings at {dt.strftime('%H:%M')}, sir."
