"""
Productivity Suite — Pomodoro, To-do, Habits, Journal, Shopping List.
All data stored as JSON in memory/productivity/.
"""
import json
import threading
import time
from datetime import datetime, date
from pathlib import Path

import config
from tools.registry import register

_DIR = config.MEMORY_DIR / "productivity"
_DIR.mkdir(parents=True, exist_ok=True)

_TODO_FILE     = _DIR / "todos.json"
_HABITS_FILE   = _DIR / "habits.json"
_JOURNAL_FILE  = _DIR / "journal.json"
_SHOPPING_FILE = _DIR / "shopping.json"

# ── Helpers ────────────────────────────────────────────────────────────────────
def _load(path: Path) -> list:
    if path.exists():
        try: return json.loads(path.read_text())
        except Exception: pass
    return []

def _save(path: Path, data):
    _DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))

# ── Pomodoro ───────────────────────────────────────────────────────────────────
_pomo_thread  = None
_pomo_end_ts  = 0.0
_pomo_running = False
_pomo_label   = ""

@register(
    name="start_pomodoro",
    description="Start a Pomodoro focus timer. Notifies when done.",
    parameters={"type":"object","properties":{
        "minutes":{"type":"integer","description":"Focus duration in minutes (default 25)"},
        "task":   {"type":"string", "description":"What you're working on"},
    }},
)
def start_pomodoro(minutes: int = 25, task: str = "Focus session") -> str:
    global _pomo_thread, _pomo_end_ts, _pomo_running, _pomo_label
    if _pomo_running:
        rem = max(0, int(_pomo_end_ts - time.time()))
        return f"Pomodoro already running — {rem//60}m {rem%60}s left on '{_pomo_label}', sir."
    _pomo_running = True
    _pomo_label   = task
    _pomo_end_ts  = time.time() + minutes * 60

    def _run():
        global _pomo_running
        time.sleep(minutes * 60)
        _pomo_running = False
        try:
            from voice.speaker import speak
            speak(f"Pomodoro complete! {minutes} minutes on {task}. Time for a break, sir.")
        except Exception:
            pass
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0,
                f"✅ {minutes}-minute focus session on '{task}' complete!\nTake a 5-minute break.",
                "JARVIS — Pomodoro", 0x40)
        except Exception:
            pass

    _pomo_thread = threading.Thread(target=_run, daemon=True)
    _pomo_thread.start()
    return f"Pomodoro started — {minutes} minutes on '{task}'. I'll notify you when done, sir."


@register(
    name="stop_pomodoro",
    description="Stop the current Pomodoro timer.",
    parameters={"type":"object","properties":{}},
)
def stop_pomodoro() -> str:
    global _pomo_running
    if not _pomo_running:
        return "No Pomodoro running, sir."
    _pomo_running = False
    return "Pomodoro stopped, sir."


@register(
    name="pomodoro_status",
    description="Check current Pomodoro timer status.",
    parameters={"type":"object","properties":{}},
)
def pomodoro_status() -> str:
    if not _pomo_running:
        return "No Pomodoro currently running, sir."
    rem = max(0, int(_pomo_end_ts - time.time()))
    return f"Pomodoro running — '{_pomo_label}' — {rem//60}m {rem%60}s remaining, sir."


# ── To-do List ─────────────────────────────────────────────────────────────────
@register(
    name="create_todo",
    description="Add a task to the to-do list.",
    parameters={"type":"object","properties":{
        "title":   {"type":"string"},
        "priority":{"type":"string","description":"low / medium / high (default medium)"},
        "due":     {"type":"string","description":"Due date, e.g. 'tomorrow', '2025-06-01'"},
    },"required":["title"]},
)
def create_todo(title: str, priority: str = "medium", due: str = "") -> str:
    todos = _load(_TODO_FILE)
    todos.append({"title": title, "priority": priority, "due": due,
                  "done": False, "created": datetime.now().isoformat()})
    _save(_TODO_FILE, todos)
    return f"Task added: '{title}' [{priority}]{' due '+due if due else ''}, sir."


@register(
    name="list_todos",
    description="List all to-do tasks.",
    parameters={"type":"object","properties":{
        "status":{"type":"string","description":"all / pending / done (default pending)"},
    }},
)
def list_todos(status: str = "pending") -> str:
    todos = _load(_TODO_FILE)
    if status == "done":
        items = [t for t in todos if t.get("done")]
    elif status == "all":
        items = todos
    else:
        items = [t for t in todos if not t.get("done")]
    if not items:
        return f"No {status} tasks, sir."
    pri_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    lines = []
    for t in items:
        icon = "✅" if t.get("done") else pri_icon.get(t.get("priority","medium"),"🟡")
        due  = f"  (due {t['due']})" if t.get("due") else ""
        lines.append(f"{icon} {t['title']}{due}")
    return "\n".join(lines)


@register(
    name="complete_todo",
    description="Mark a to-do task as done.",
    parameters={"type":"object","properties":{"title":{"type":"string"}},"required":["title"]},
)
def complete_todo(title: str) -> str:
    todos = _load(_TODO_FILE)
    q = title.lower()
    found = False
    for t in todos:
        if q in t["title"].lower():
            t["done"] = True; t["completed_at"] = datetime.now().isoformat()
            found = True
    if found:
        _save(_TODO_FILE, todos)
        return f"Task '{title}' marked as done, sir."
    return f"No task matching '{title}', sir."


@register(
    name="delete_todo",
    description="Delete a to-do task.",
    parameters={"type":"object","properties":{"title":{"type":"string"}},"required":["title"]},
)
def delete_todo(title: str) -> str:
    todos = _load(_TODO_FILE)
    q = title.lower()
    before = len(todos)
    todos = [t for t in todos if q not in t["title"].lower()]
    _save(_TODO_FILE, todos)
    removed = before - len(todos)
    return f"Removed {removed} task(s) matching '{title}', sir."


# ── Habit Tracker ──────────────────────────────────────────────────────────────
@register(
    name="log_habit",
    description="Log a habit for today (e.g. exercise, water intake, reading).",
    parameters={"type":"object","properties":{
        "habit": {"type":"string","description":"Habit name"},
        "value": {"type":"string","description":"Value or note (default 'done')"},
    },"required":["habit"]},
)
def log_habit(habit: str, value: str = "done") -> str:
    habits = _load(_HABITS_FILE)
    today  = date.today().isoformat()
    # Find or create habit entry for today
    entry  = next((h for h in habits if h["habit"].lower() == habit.lower()
                   and h["date"] == today), None)
    if entry:
        entry["value"] = value
    else:
        habits.append({"habit": habit, "date": today, "value": value,
                       "ts": datetime.now().isoformat()})
    _save(_HABITS_FILE, habits)
    return f"Habit '{habit}' logged as '{value}' for today, sir."


@register(
    name="list_habits",
    description="Show habit log for today or the past N days.",
    parameters={"type":"object","properties":{
        "days":{"type":"integer","description":"Days to look back (default 7)"},
    }},
)
def list_habits(days: int = 7) -> str:
    habits = _load(_HABITS_FILE)
    from datetime import timedelta
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    recent = [h for h in habits if h.get("date","") >= cutoff]
    if not recent:
        return f"No habits logged in the last {days} days, sir."
    # Group by habit name
    by_name: dict = {}
    for h in recent:
        by_name.setdefault(h["habit"], []).append(f"{h['date']}: {h['value']}")
    lines = []
    for name, entries in by_name.items():
        lines.append(f"📋 {name}")
        lines.extend(f"   {e}" for e in entries[-7:])
    return "\n".join(lines)


@register(
    name="habit_streak",
    description="Get the current streak for a habit.",
    parameters={"type":"object","properties":{"habit":{"type":"string"}},"required":["habit"]},
)
def habit_streak(habit: str) -> str:
    from datetime import timedelta
    habits = _load(_HABITS_FILE)
    q      = habit.lower()
    entries= sorted(
        [h for h in habits if h["habit"].lower() == q],
        key=lambda x: x["date"], reverse=True
    )
    if not entries:
        return f"No logs for '{habit}', sir."
    streak  = 0
    check   = date.today()
    for e in entries:
        if e["date"] == check.isoformat():
            streak += 1
            check  -= timedelta(days=1)
        elif e["date"] < check.isoformat():
            break
    return f"Current streak for '{habit}': {streak} day{'s' if streak!=1 else ''}, sir."


# ── Daily Journal ──────────────────────────────────────────────────────────────
@register(
    name="journal_entry",
    description="Write a journal entry for today with optional mood.",
    parameters={"type":"object","properties":{
        "content":{"type":"string","description":"Journal entry text"},
        "mood":   {"type":"string","description":"Mood: happy/sad/anxious/calm/excited/tired (optional)"},
    },"required":["content"]},
)
def journal_entry(content: str, mood: str = "") -> str:
    journal = _load(_JOURNAL_FILE)
    today   = date.today().isoformat()
    entry   = next((j for j in journal if j["date"] == today), None)
    if entry:
        entry["content"] += f"\n\n---\n{content}"
        if mood: entry["mood"] = mood
    else:
        journal.append({"date": today, "content": content, "mood": mood,
                        "ts": datetime.now().isoformat()})
    _save(_JOURNAL_FILE, journal)
    return f"Journal entry saved for {today}{' — mood: '+mood if mood else ''}, sir."


@register(
    name="read_journal",
    description="Read journal entries for a specific date or recent days.",
    parameters={"type":"object","properties":{
        "date":{"type":"string","description":"Date like '2025-06-01' or 'today' (default today)"},
        "days":{"type":"integer","description":"Number of recent days to show (overrides date)"},
    }},
)
def read_journal(date: str = "today", days: int = 0) -> str:
    from datetime import timedelta as td
    journal = _load(_JOURNAL_FILE)
    if days > 0:
        from datetime import timedelta
        cutoff = (datetime.today() - timedelta(days=days)).date().isoformat()
        entries = [j for j in journal if j.get("date","") >= cutoff]
    else:
        target = datetime.today().date().isoformat() if date in ("today","") else date
        entries = [j for j in journal if j.get("date") == target]
    if not entries:
        return f"No journal entries found, sir."
    return "\n\n".join(
        f"📔 {e['date']}{' ['+e['mood']+']' if e.get('mood') else ''}\n{e['content']}"
        for e in entries
    )


# ── Shopping List ──────────────────────────────────────────────────────────────
@register(
    name="add_shopping",
    description="Add an item to the shopping list.",
    parameters={"type":"object","properties":{
        "item":     {"type":"string"},
        "quantity": {"type":"string","description":"Amount, e.g. '2 kg', '1 box'"},
        "category": {"type":"string","description":"Category: groceries/household/etc."},
    },"required":["item"]},
)
def add_shopping(item: str, quantity: str = "1", category: str = "general") -> str:
    shop = _load(_SHOPPING_FILE)
    shop.append({"item": item, "quantity": quantity, "category": category,
                 "done": False, "added": datetime.now().isoformat()})
    _save(_SHOPPING_FILE, shop)
    return f"Added '{quantity} {item}' to shopping list, sir."


@register(
    name="list_shopping",
    description="Show the current shopping list.",
    parameters={"type":"object","properties":{"show_done":{"type":"boolean"}}},
)
def list_shopping(show_done: bool = False) -> str:
    shop  = _load(_SHOPPING_FILE)
    items = shop if show_done else [s for s in shop if not s.get("done")]
    if not items:
        return "Shopping list is empty, sir."
    by_cat: dict = {}
    for s in items:
        by_cat.setdefault(s.get("category","general"), []).append(s)
    lines = []
    for cat, entries in by_cat.items():
        lines.append(f"\n🛒 {cat.title()}")
        for e in entries:
            tick = "✅" if e.get("done") else "□"
            lines.append(f"  {tick} {e['quantity']}x {e['item']}")
    return "\n".join(lines).strip()


@register(
    name="check_shopping",
    description="Mark a shopping item as purchased.",
    parameters={"type":"object","properties":{"item":{"type":"string"}},"required":["item"]},
)
def check_shopping(item: str) -> str:
    shop = _load(_SHOPPING_FILE)
    q = item.lower(); found = False
    for s in shop:
        if q in s["item"].lower(): s["done"] = True; found = True
    if found:
        _save(_SHOPPING_FILE, shop)
        return f"'{item}' marked as purchased, sir."
    return f"'{item}' not found in shopping list, sir."


@register(
    name="clear_shopping",
    description="Clear purchased items or the entire shopping list.",
    parameters={"type":"object","properties":{
        "all":{"type":"boolean","description":"If true, clears everything"},
    }},
)
def clear_shopping(all: bool = False) -> str:
    shop = _load(_SHOPPING_FILE)
    if all:
        _save(_SHOPPING_FILE, [])
        return "Shopping list cleared, sir."
    shop = [s for s in shop if not s.get("done")]
    _save(_SHOPPING_FILE, shop)
    return "Purchased items removed from shopping list, sir."
