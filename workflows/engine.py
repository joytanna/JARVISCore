import sqlite3, threading, time
from pathlib import Path

_DB = Path(__file__).parent.parent / "memory" / "jarvis.db"


def _conn():
    c = sqlite3.connect(str(_DB))
    c.execute("""CREATE TABLE IF NOT EXISTS workflows (
        name TEXT PRIMARY KEY, cron TEXT NOT NULL, command TEXT NOT NULL, enabled INTEGER DEFAULT 1
    )""")
    c.commit()
    return c


def _cron_match(field, value):
    if field == "*":
        return True
    if field.startswith("*/"):
        return value % int(field[2:]) == 0
    vals = set()
    for p in field.split(","):
        if "-" in p:
            a, b = p.split("-")
            vals.update(range(int(a), int(b) + 1))
        else:
            vals.add(int(p))
    return value in vals


def _cron_matches(cron: str, t: time.struct_time) -> bool:
    parts = cron.strip().split()
    if len(parts) != 5:
        return False
    mi, hr, dom, mon, dow = parts
    return (_cron_match(mi, t.tm_min) and _cron_match(hr, t.tm_hour)
            and _cron_match(dom, t.tm_mday) and _cron_match(mon, t.tm_mon)
            and _cron_match(dow, t.tm_wday))


_DEFAULTS = [
    ("morning_brief", "0 8 * * *",
     "Give me a morning briefing: date, day, motivational quote, and one world news headline."),
    ("evening_wrap", "0 20 * * *",
     "Give a brief evening wrap-up: top thing accomplished, one reminder for tomorrow."),
    ("system_health", "0 * * * *",
     "Run a silent system health check and alert only if CPU > 90% or RAM > 90%."),
]


class WorkflowEngine:
    def __init__(self, command_fn):
        self._fn = command_fn
        self._stop = threading.Event()
        self._last_run: dict = {}
        self._setup()

    def _setup(self):
        try:
            c = _conn()
            for name, cron, cmd in _DEFAULTS:
                c.execute("INSERT OR IGNORE INTO workflows (name, cron, command) VALUES (?,?,?)",
                          (name, cron, cmd))
            c.commit()
            c.close()
        except Exception:
            pass

    def _tick(self):
        while not self._stop.is_set():
            now = time.localtime()
            tick = time.strftime("%Y%m%d%H%M", now)
            try:
                c = _conn()
                rows = c.execute("SELECT name, cron, command FROM workflows WHERE enabled=1").fetchall()
                c.close()
                for name, cron, cmd in rows:
                    key = f"{name}:{tick}"
                    if key not in self._last_run and _cron_matches(cron, now):
                        self._last_run[key] = tick
                        threading.Thread(target=self._fn, args=(cmd,), daemon=True).start()
            except Exception:
                pass
            self._stop.wait(30)

    def start(self):
        threading.Thread(target=self._tick, daemon=True, name="workflows").start()
        print("[Workflows] Engine started.")

    def stop(self):
        self._stop.set()

    def add(self, name: str, cron: str, command: str) -> str:
        try:
            c = _conn()
            c.execute("INSERT OR REPLACE INTO workflows (name, cron, command, enabled) VALUES (?,?,?,1)",
                      (name, cron, command))
            c.commit()
            c.close()
            return f"Workflow {name!r} scheduled ({cron})."
        except Exception as e:
            return f"Error: {e}"

    def list_workflows(self) -> str:
        try:
            c = _conn()
            rows = c.execute("SELECT name, cron, command, enabled FROM workflows ORDER BY name").fetchall()
            c.close()
            return "\n".join(f"{'[ON]' if en else '[OFF]'} {n} ({cr}): {cmd[:60]}"
                             for n, cr, cmd, en in rows) or "No workflows configured."
        except Exception as e:
            return f"Error: {e}"


_engine = None


def get_engine(command_fn=None):
    global _engine
    if _engine is None and command_fn is not None:
        _engine = WorkflowEngine(command_fn)
        _engine.start()
    return _engine
