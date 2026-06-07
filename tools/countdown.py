"""
Countdown & Date Tracker — track important dates, days until events,
and get a quick "days until" for birthdays, deadlines, holidays.
"""
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import config
from tools.registry import register

_DIR  = config.MEMORY_DIR / "countdowns"
_DIR.mkdir(parents=True, exist_ok=True)
_FILE = _DIR / "events.json"


def _load() -> list:
    if _FILE.exists():
        try: return json.loads(_FILE.read_text())
        except: pass
    return []

def _save(data: list):
    _FILE.write_text(json.dumps(data, indent=2))

def _parse_date(text: str) -> str:
    """Return ISO date string from various inputs."""
    t = text.strip().lower()
    today = date.today()

    # Already ISO
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', t)
    if m:
        return t

    # DD/MM/YYYY or DD-MM-YYYY
    m = re.match(r'^(\d{1,2})[/-](\d{1,2})[/-](\d{4})$', t)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"

    # Month name  "June 15", "15 June", "June 15 2026"
    months = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,
               "jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12}
    m = re.search(r'(\d{1,2})\s+([a-z]+)|\s*([a-z]+)\s+(\d{1,2})', t)
    if m:
        if m.group(1):
            day = int(m.group(1)); mo_str = m.group(2)[:3]
        else:
            day = int(m.group(4)); mo_str = m.group(3)[:3]
        mo = months.get(mo_str)
        if mo:
            yr_m = re.search(r'\b(\d{4})\b', t)
            yr   = int(yr_m.group(1)) if yr_m else today.year
            d    = date(yr, mo, day)
            if d < today and not yr_m:
                d = date(yr + 1, mo, day)
            return d.isoformat()

    raise ValueError(f"Cannot parse date: {text!r}")


# ── Add Countdown ──────────────────────────────────────────────────────────────
@register(
    name="add_countdown",
    description="Track a countdown to an important date (birthday, exam, holiday, deadline).",
    parameters={"type": "object", "properties": {
        "name":  {"type": "string", "description": "Event name, e.g. 'Birthday', 'Exam'"},
        "date":  {"type": "string", "description": "Date: 'YYYY-MM-DD', 'June 15', '15/06/2026'"},
        "emoji": {"type": "string", "description": "Optional emoji for the event"},
        "repeat_yearly": {"type": "boolean", "description": "Auto-advance date each year (for birthdays etc.)"},
    }, "required": ["name", "date"]},
)
def add_countdown(name: str, date: str, emoji: str = "",
                  repeat_yearly: bool = False) -> str:
    try:
        iso = _parse_date(date)
    except ValueError as e:
        return str(e)
    events = _load()
    events = [e for e in events if e['name'].lower() != name.lower()]
    events.append({"name": name, "date": iso, "emoji": emoji or "📅",
                   "repeat_yearly": repeat_yearly,
                   "created": datetime.now().isoformat()})
    _save(events)
    d    = datetime.fromisoformat(iso).date()
    days = (d - datetime.today().date()).days
    if days < 0:
        return f"That date is in the past ({iso}). Did you mean next year? Use YYYY-MM-DD, sir."
    return f"Countdown to '{name}' set — {days} days to go! ({iso}), sir."


# ── List Countdowns ────────────────────────────────────────────────────────────
@register(
    name="list_countdowns",
    description="List all upcoming countdown events sorted by how soon they are.",
    parameters={"type": "object", "properties": {}},
)
def list_countdowns() -> str:
    events = _load()
    if not events:
        return "No countdowns set yet, sir."

    today = datetime.today().date()
    rows  = []
    for e in events:
        try:
            d    = datetime.fromisoformat(e['date']).date()
            # Advance yearly countdowns if past
            if e.get('repeat_yearly') and d < today:
                d = d.replace(year=today.year)
                if d < today:
                    d = d.replace(year=today.year + 1)
                e['date'] = d.isoformat()
            days = (d - today).days
            rows.append((days, e['emoji'], e['name'], d.strftime('%b %d %Y'), days))
        except Exception:
            pass

    _save(events)  # update any advanced yearly dates
    rows.sort()
    if not rows:
        return "No upcoming countdowns, sir."

    lines = ["--- Countdowns ---"]
    for days, emoji, name, date_str, _ in rows:
        if days == 0:
            msg = "TODAY!"
        elif days == 1:
            msg = "TOMORROW!"
        else:
            msg = f"{days} days"
        lines.append(f"  {emoji} {name:25}  {date_str}  ({msg})")
    return "\n".join(lines)


# ── Days Until ────────────────────────────────────────────────────────────────
@register(
    name="days_until",
    description="Quick calculation: how many days until a specific date?",
    parameters={"type": "object", "properties": {
        "date": {"type": "string", "description": "Date string: 'Dec 25', '2026-06-15', '25/12/2026'"},
    }, "required": ["date"]},
)
def days_until(date: str) -> str:
    try:
        iso  = _parse_date(date)
        d    = datetime.fromisoformat(iso).date()
        days = (d - datetime.today().date()).days
        if days < 0:
            return f"That was {abs(days)} day(s) ago ({iso}), sir."
        if days == 0:
            return f"That's today! ({iso}), sir."
        weeks, rem = divmod(days, 7)
        wk_str = f" ({weeks}w {rem}d)" if weeks else ""
        return f"{days} days until {d.strftime('%a, %B %d %Y')}{wk_str}, sir."
    except ValueError as e:
        return str(e)


# ── Delete Countdown ───────────────────────────────────────────────────────────
@register(
    name="delete_countdown",
    description="Remove a countdown event.",
    parameters={"type": "object", "properties": {
        "name": {"type": "string"},
    }, "required": ["name"]},
)
def delete_countdown(name: str) -> str:
    events = _load()
    q      = name.lower()
    before = len(events)
    events = [e for e in events if q not in e['name'].lower()]
    _save(events)
    removed = before - len(events)
    return (f"Removed {removed} countdown(s) matching '{name}', sir."
            if removed else f"No countdown matching '{name}', sir.")


# ── Age Calculator ─────────────────────────────────────────────────────────────
@register(
    name="calculate_age",
    description="Calculate someone's age from their date of birth, or your own.",
    parameters={"type": "object", "properties": {
        "dob":  {"type": "string", "description": "Date of birth: 'June 15 1995', '15/06/1995'"},
        "name": {"type": "string", "description": "Whose birthday (optional)"},
    }, "required": ["dob"]},
)
def calculate_age(dob: str, name: str = "") -> str:
    try:
        iso  = _parse_date(dob)
        born = datetime.fromisoformat(iso).date()
        today = datetime.today().date()
        age   = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        # Next birthday
        next_bday = born.replace(year=today.year)
        if next_bday < today:
            next_bday = born.replace(year=today.year + 1)
        days_to_bday = (next_bday - today).days
        who = f"{name} is" if name else "Age:"
        bday_msg = ("  (Happy birthday! 🎂)" if days_to_bday == 0
                    else f"  (birthday in {days_to_bday} days)")
        return f"{who} {age} years old{bday_msg}, sir."
    except ValueError as e:
        return str(e)
