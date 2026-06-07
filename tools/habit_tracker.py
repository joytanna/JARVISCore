"""
Habit Tracker — build streaks, beat yesterday.
Tracks daily habits with streak counting, completion rate, and motivational nudges.
Zero external dependencies — just stdlib JSON.
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path

import config
from tools.registry import register

_DIR  = config.MEMORY_DIR / "habits"
_DIR.mkdir(parents=True, exist_ok=True)
_FILE = _DIR / "habits.json"


def _load() -> dict:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text())
        except Exception:
            pass
    return {}          # {habit_name: {created, logs: ["YYYY-MM-DD", ...]}}


def _save(data: dict):
    _FILE.write_text(json.dumps(data, indent=2))


def _streak(logs: list) -> int:
    """Current consecutive-day streak ending today or yesterday."""
    today = date.today()
    streak = 0
    for i in range(0, 366):
        day = (today - timedelta(days=i)).isoformat()
        if day in logs:
            streak += 1
        else:
            if i == 0:
                # not done today yet — look from yesterday
                continue
            break
    return streak


def _longest_streak(logs: list) -> int:
    if not logs:
        return 0
    sorted_logs = sorted(logs)
    best = cur = 1
    for i in range(1, len(sorted_logs)):
        a = date.fromisoformat(sorted_logs[i - 1])
        b = date.fromisoformat(sorted_logs[i])
        if (b - a).days == 1:
            cur += 1
            best = max(best, cur)
        elif (b - a).days > 1:
            cur = 1
    return best


# ── Add / remove habit ────────────────────────────────────────────────────────
@register(
    name="add_habit",
    description="Create a new daily habit to track.",
    parameters={"type": "object", "properties": {
        "name": {"type": "string", "description": "Habit name, e.g. 'Morning run'"},
    }, "required": ["name"]},
)
def add_habit(name: str) -> str:
    data = _load()
    key  = name.lower().strip()
    if key in data:
        return f"Habit '{name}' already exists, sir."
    data[key] = {"display": name, "created": date.today().isoformat(), "logs": []}
    _save(data)
    return f"Habit '{name}' added. Mark it done each day with 'complete habit {name}', sir."


@register(
    name="remove_habit",
    description="Delete a habit and all its history.",
    parameters={"type": "object", "properties": {
        "name": {"type": "string"},
    }, "required": ["name"]},
)
def remove_habit(name: str) -> str:
    data = _load()
    key  = name.lower().strip()
    matches = [k for k in data if name.lower() in k]
    if not matches:
        return f"No habit matching '{name}', sir."
    for k in matches:
        del data[k]
    _save(data)
    return f"Habit '{name}' removed, sir."


# ── Mark complete ─────────────────────────────────────────────────────────────
@register(
    name="complete_habit",
    description="Mark a habit as done for today (or a specific date).",
    parameters={"type": "object", "properties": {
        "name": {"type": "string", "description": "Habit name"},
        "date": {"type": "string",  "description": "Date YYYY-MM-DD (default: today)"},
    }, "required": ["name"]},
)
def complete_habit(name: str, date: str = None) -> str:
    data  = _load()
    key   = next((k for k in data if name.lower() in k), None)
    if not key:
        return f"No habit matching '{name}'. Add it first with 'add habit {name}', sir."
    day   = date or datetime.today().date().isoformat()
    logs  = data[key]["logs"]
    if day in logs:
        streak = _streak(logs)
        return (f"'{data[key]['display']}' already marked done for {day}. "
                f"Current streak: {streak} day{'s' if streak!=1 else ''}, sir.")
    logs.append(day)
    logs.sort()
    _save(data)
    streak = _streak(logs)
    msgs   = {
        1: "Good start!",
        3: "3 days - building momentum!",
        7: "One week streak - impressive!",
        14: "Two weeks! Habit is forming!",
        21: "21 days - this is now a habit!",
        30: "30-day streak - phenomenal!",
        50: "50 days - extraordinary dedication!",
        100: "100 DAYS - legendary!",
    }
    bonus = f"  {msgs[streak]}" if streak in msgs else ""
    return (f"'{data[key]['display']}' — done for today! "
            f"Streak: {streak} day{'s' if streak!=1 else ''}.{bonus}, sir.")


# ── View habits ───────────────────────────────────────────────────────────────
@register(
    name="list_habits",
    description="Show all habits with current streaks and today's completion status.",
    parameters={"type": "object", "properties": {}},
)
def list_habits() -> str:
    data  = _load()
    if not data:
        return "No habits tracked yet. Add one with 'add habit [name]', sir."
    today = date.today().isoformat()
    lines = ["--- Your Habits ---"]
    for key, h in sorted(data.items()):
        logs      = h["logs"]
        done      = today in logs
        streak    = _streak(logs)
        done_30   = sum(1 for i in range(30)
                        if (date.today()-timedelta(days=i)).isoformat() in logs)
        pct_30    = int(done_30 / 30 * 100)
        status    = "[x]" if done else "[ ]"
        streak_s  = f"*{streak}d*" if streak >= 3 else f"{streak}d"
        lines.append(f"  {status} {h['display']:28} {streak_s:>6}  {pct_30}% last 30d")
    not_done = [h["display"] for k, h in data.items() if today not in h["logs"]]
    if not_done:
        lines.append(f"\nStill to do today: {', '.join(not_done)}")
    return "\n".join(lines)


@register(
    name="habit_stats",
    description="Show detailed statistics for a specific habit.",
    parameters={"type": "object", "properties": {
        "name": {"type": "string"},
    }, "required": ["name"]},
)
def habit_stats(name: str) -> str:
    data = _load()
    key  = next((k for k in data if name.lower() in k), None)
    if not key:
        return f"No habit matching '{name}', sir."
    h    = data[key]
    logs = h["logs"]
    if not logs:
        return f"'{h['display']}' has no completions yet, sir."
    total       = len(logs)
    created     = h.get("created", logs[0])
    days_since  = (date.today() - date.fromisoformat(created)).days + 1
    pct         = int(total / days_since * 100)
    cur_streak  = _streak(logs)
    best_streak = _longest_streak(logs)
    last_7      = sum(1 for i in range(7)
                      if (date.today()-timedelta(days=i)).isoformat() in logs)
    return (
        f"--- {h['display']} ---\n"
        f"  Total completions:  {total}\n"
        f"  Days tracked:       {days_since}\n"
        f"  Completion rate:    {pct}%\n"
        f"  Current streak:     {cur_streak} day{'s' if cur_streak!=1 else ''}\n"
        f"  Best streak:        {best_streak} day{'s' if best_streak!=1 else ''}\n"
        f"  Last 7 days:        {last_7}/7"
    )


@register(
    name="habits_today",
    description="Quick check: which habits are done today and which are pending.",
    parameters={"type": "object", "properties": {}},
)
def habits_today() -> str:
    data  = _load()
    if not data:
        return "No habits tracked yet, sir."
    today = date.today().isoformat()
    done  = [h["display"] for k, h in data.items() if today in h["logs"]]
    todo  = [h["display"] for k, h in data.items() if today not in h["logs"]]
    lines = [f"Today ({today}):"]
    if done:
        lines.append(f"  Done ({len(done)}): " + ", ".join(done))
    if todo:
        lines.append(f"  Still to do ({len(todo)}): " + ", ".join(todo))
    if not todo:
        lines.append("  All habits complete for today! Outstanding work, sir.")
    return "\n".join(lines)
