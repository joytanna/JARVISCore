"""
Advanced System Tools — Clipboard history, disk cleanup, battery,
password generator, network info, system health, scheduled tasks.
"""
import json
import os
import platform
import random
import re
import shutil
import string
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

import config
from tools.registry import register

_DIR = config.MEMORY_DIR / "system"
_DIR.mkdir(parents=True, exist_ok=True)
_CLIPBOARD_FILE   = _DIR / "clipboard_history.json"
_SCHEDULE_FILE    = _DIR / "scheduled_tasks.json"

# ── Clipboard History ──────────────────────────────────────────────────────────
_clipboard_history: list = []

def _poll_clipboard():
    """Background thread: poll clipboard every 2s and record changes."""
    last = ""
    while True:
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            except Exception:
                text = ""
            win32clipboard.CloseClipboard()
            if text and text != last and len(text) < 5000:
                last = text
                _clipboard_history.append({
                    "text": text[:500],
                    "ts":   datetime.now().isoformat(),
                })
                if len(_clipboard_history) > 50:
                    _clipboard_history.pop(0)
        except Exception:
            pass
        time.sleep(2)

try:
    threading.Thread(target=_poll_clipboard, daemon=True, name="clipboard-watcher").start()
except Exception:
    pass

@register(
    name="get_clipboard_history",
    description="Show recent clipboard history.",
    parameters={"type":"object","properties":{
        "n":{"type":"integer","description":"Number of recent items (default 10)"},
    }},
)
def get_clipboard_history(n: int = 10) -> str:
    items = _clipboard_history[-n:] if _clipboard_history else []
    if not items:
        return "Clipboard history is empty, sir."
    lines = []
    for i, c in enumerate(reversed(items), 1):
        ts   = datetime.fromisoformat(c["ts"]).strftime("%H:%M:%S")
        text = c["text"].replace("\n"," ")[:100]
        lines.append(f"{i}. [{ts}] {text}")
    return "\n".join(lines)


@register(
    name="clear_clipboard_history",
    description="Clear the clipboard history.",
    parameters={"type":"object","properties":{}},
)
def clear_clipboard_history() -> str:
    _clipboard_history.clear()
    return "Clipboard history cleared, sir."


# ── Disk Cleanup ───────────────────────────────────────────────────────────────
@register(
    name="clean_temp_files",
    description="Delete temporary files to free disk space.",
    parameters={"type":"object","properties":{
        "dry_run":{"type":"boolean","description":"If true, only report what would be deleted"},
    }},
)
def clean_temp_files(dry_run: bool = False) -> str:
    targets = [
        Path(tempfile.gettempdir()),
        Path(os.environ.get("LOCALAPPDATA","")) / "Temp",
        Path(os.environ.get("WINDIR","C:\\Windows")) / "Temp",
    ]
    total_freed = 0
    removed     = 0
    errors      = 0
    for folder in targets:
        if not folder.exists():
            continue
        try:
            entries = list(folder.iterdir())
        except PermissionError:
            errors += 1
            continue
        for f in entries:
            try:
                if f.is_file():
                    size = f.stat().st_size
                    if not dry_run:
                        f.unlink(missing_ok=True)
                    total_freed += size
                    removed     += 1
                elif f.is_dir():
                    size = sum(x.stat().st_size for x in f.rglob("*") if x.is_file())
                    if not dry_run:
                        shutil.rmtree(f, ignore_errors=True)
                    total_freed += size
                    removed     += 1
            except Exception:
                errors += 1
    freed_mb = total_freed / (1024 * 1024)
    prefix   = "Would free" if dry_run else "Freed"
    return (f"{'Dry run: ' if dry_run else ''}{prefix} {freed_mb:.1f} MB by removing "
            f"{removed} file/folder(s). {errors} skipped (in use), sir.")


@register(
    name="get_disk_info",
    description="Show disk usage for all drives.",
    parameters={"type":"object","properties":{}},
)
def get_disk_info() -> str:
    try:
        import psutil
        lines = []
        for part in psutil.disk_partitions(all=False):
            try:
                usage = psutil.disk_usage(part.mountpoint)
                pct   = usage.percent
                bar   = "█" * int(pct/5) + "░" * (20 - int(pct/5))
                lines.append(
                    f"{part.mountpoint}  [{bar}] {pct:.0f}%  "
                    f"{usage.used/(1<<30):.1f}/{usage.total/(1<<30):.1f} GB"
                )
            except Exception:
                pass
        return "\n".join(lines) if lines else "No drives found, sir."
    except ImportError:
        result = subprocess.run("wmic logicaldisk get DeviceID,Size,FreeSpace",
                                capture_output=True, text=True, shell=True)
        return result.stdout.strip()


# ── Battery ────────────────────────────────────────────────────────────────────
@register(
    name="get_battery_status",
    description="Get laptop battery percentage and charging status.",
    parameters={"type":"object","properties":{}},
)
def get_battery_status() -> str:
    try:
        import psutil
        b = psutil.sensors_battery()
        if b is None:
            return "No battery detected (desktop system), sir."
        pct     = b.percent
        plugged = getattr(b, 'power_plugged', None)
        if plugged is None:
            plugged = getattr(b, 'plugged', False)
        plug    = "Charging" if plugged else "On battery"
        secsleft = getattr(b, 'secsleft', -1) or -1
        if secsleft > 0 and not plugged:
            m, s = divmod(secsleft, 60)
            h, m = divmod(m, 60)
            time_str = f"  ~{h}h {m}m remaining" if h else f"  ~{m}m remaining"
        else:
            time_str = ""
        icon = "+" if pct > 50 else "~" if pct > 20 else "!"
        return f"[{icon}] Battery: {pct:.0f}%  {plug}{time_str}, sir."
    except Exception:
        return "Battery status unavailable, sir."


# ── Password Generator ─────────────────────────────────────────────────────────
@register(
    name="generate_password",
    description="Generate a secure random password.",
    parameters={"type":"object","properties":{
        "length":    {"type":"integer","description":"Length (default 16)"},
        "uppercase": {"type":"boolean","description":"Include uppercase letters"},
        "numbers":   {"type":"boolean","description":"Include numbers"},
        "symbols":   {"type":"boolean","description":"Include symbols"},
        "memorable": {"type":"boolean","description":"Generate a memorable passphrase instead"},
    }},
)
def generate_password(length: int = 16, uppercase: bool = True,
                       numbers: bool = True, symbols: bool = True,
                       memorable: bool = False) -> str:
    if memorable:
        # Generate a word-based passphrase
        words  = ["apple","brave","cloud","delta","eagle","flame","grace","hotel",
                  "ivory","jumbo","kappa","laser","mango","novel","orbit","pixel",
                  "quest","ridge","sigma","titan","ultra","vivid","whale","xenon",
                  "yacht","zebra"]
        phrase = "-".join(random.choices(words, k=4))
        num    = random.randint(10, 99)
        return f"Passphrase: {phrase}-{num}  (strength: strong), sir."
    chars = string.ascii_lowercase
    if uppercase: chars += string.ascii_uppercase
    if numbers:   chars += string.digits
    if symbols:   chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"
    pw = "".join(random.SystemRandom().choice(chars) for _ in range(length))
    # Strength estimate
    entropy_bits = len(chars) ** length
    strength = "very strong" if length >= 16 else "strong" if length >= 12 else "moderate"
    return f"Password: {pw}\nStrength: {strength} ({length} chars), sir."


# ── Network Info ───────────────────────────────────────────────────────────────
@register(
    name="get_network_info",
    description="Show local IP, external IP, and network interface stats.",
    parameters={"type":"object","properties":{}},
)
def get_network_info() -> str:
    lines = []
    try:
        import socket
        hostname  = socket.gethostname()
        local_ip  = socket.gethostbyname(hostname)
        lines.append(f"🖥  Hostname: {hostname}")
        lines.append(f"🏠 Local IP: {local_ip}")
    except Exception:
        pass
    try:
        from urllib.request import urlopen
        ext_ip = urlopen("https://api.ipify.org", timeout=4).read().decode().strip()
        lines.append(f"🌐 External IP: {ext_ip}")
    except Exception:
        lines.append("🌐 External IP: (could not retrieve)")
    try:
        import psutil
        stats = psutil.net_io_counters()
        lines.append(f"📤 Sent:     {stats.bytes_sent/(1<<20):.1f} MB")
        lines.append(f"📥 Received: {stats.bytes_recv/(1<<20):.1f} MB")
    except Exception:
        pass
    return "\n".join(lines) if lines else "Network info unavailable, sir."


@register(
    name="ping_host",
    description="Ping a hostname or IP to check connectivity.",
    parameters={"type":"object","properties":{
        "host":{"type":"string","description":"Hostname or IP to ping"},
        "count":{"type":"integer","description":"Number of pings (default 4)"},
    },"required":["host"]},
)
def ping_host(host: str, count: int = 4) -> str:
    try:
        flag = "-n" if platform.system() == "Windows" else "-c"
        result = subprocess.run(
            ["ping", flag, str(count), host],
            capture_output=True, text=True, timeout=15
        )
        out = result.stdout.strip()
        # Extract average RTT
        m = re.search(r"Average = (\d+)ms|avg[^=]*= [\d.]+/([\d.]+)", out)
        avg = m.group(1) or m.group(2) if m else "?"
        lines = [l for l in out.splitlines() if l.strip()]
        return "\n".join(lines[-4:]) + f"\n\nAverage RTT: {avg}ms, sir."
    except subprocess.TimeoutExpired:
        return f"{host} is not responding (timeout), sir."
    except Exception as e:
        return f"Ping error: {e}"


# ── System Health ──────────────────────────────────────────────────────────────
@register(
    name="system_health_report",
    description="Get a comprehensive system health report: CPU, RAM, disk, battery, network.",
    parameters={"type":"object","properties":{}},
)
def system_health_report() -> str:
    lines = [f"🖥  System Health Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    try:
        import psutil
        cpu   = psutil.cpu_percent(interval=0.5)
        ram   = psutil.virtual_memory()
        lines.append(f"\nCPU:    {cpu:.1f}% ({psutil.cpu_count()} cores)")
        lines.append(f"RAM:    {ram.percent:.1f}%  ({ram.used/(1<<30):.1f}/{ram.total/(1<<30):.1f} GB)")
        disk  = psutil.disk_usage("C:\\")
        lines.append(f"C:\\ Disk: {disk.percent:.1f}%  ({disk.used/(1<<30):.1f}/{disk.total/(1<<30):.1f} GB)")
        bat   = psutil.sensors_battery()
        if bat:
            plugged = getattr(bat, 'power_plugged', None)
            if plugged is None:
                plugged = getattr(bat, 'plugged', False)
            lines.append(f"Battery: {bat.percent:.0f}%  {'Charging' if plugged else 'Discharging'}")
        # Top 5 processes by CPU
        procs = sorted(psutil.process_iter(["pid","name","cpu_percent"]),
                       key=lambda p: p.info.get("cpu_percent",0), reverse=True)[:5]
        lines.append("\nTop processes:")
        for p in procs:
            lines.append(f"  {p.info['name'][:20]:20} {p.info['cpu_percent']:.1f}% CPU")
    except ImportError:
        lines.append("psutil not installed.")
    return "\n".join(lines)


# ── Scheduled Tasks ────────────────────────────────────────────────────────────
_sched_tasks: list = []
_sched_lock  = threading.Lock()

def _load_sched():
    if _SCHEDULE_FILE.exists():
        try: return json.loads(_SCHEDULE_FILE.read_text())
        except: pass
    return []

def _save_sched(tasks):
    _SCHEDULE_FILE.write_text(json.dumps(tasks, indent=2))

def _sched_worker():
    """Background scheduler — runs every 30 seconds."""
    while True:
        now = time.time()
        with _sched_lock:
            tasks = _load_sched()
            changed = False
            for t in tasks:
                if t.get("done") or t.get("ts", 0) > now:
                    continue
                # Execute
                try:
                    from jarvis import _push_to_remotes
                    _push_to_remotes({"type": "push", "text": f"⏰ Reminder: {t['task']}"})
                except Exception:
                    pass
                try:
                    from voice.speaker import speak
                    speak(f"Reminder: {t['task']}")
                except Exception:
                    pass
                t["done"] = True
                changed   = True
            if changed:
                _save_sched(tasks)
        time.sleep(30)

threading.Thread(target=_sched_worker, daemon=True, name="scheduler").start()

@register(
    name="schedule_task",
    description="Schedule a reminder or command to run at a specific time.",
    parameters={"type":"object","properties":{
        "task":{"type":"string","description":"What to remind/do"},
        "when":{"type":"string","description":"e.g. 'in 30 minutes', 'tomorrow 9am', '2025-06-15 14:00'"},
    },"required":["task","when"]},
)
def schedule_task(task: str, when: str) -> str:
    from datetime import timedelta
    now  = datetime.now()
    text = when.lower().strip()
    # Parse
    if "in" in text:
        m_hr  = re.search(r"(\d+)\s*hour", text)
        m_min = re.search(r"(\d+)\s*min",  text)
        m_sec = re.search(r"(\d+)\s*sec",  text)
        delta = timedelta(
            hours  =int(m_hr.group(1))  if m_hr  else 0,
            minutes=int(m_min.group(1)) if m_min else 0,
            seconds=int(m_sec.group(1)) if m_sec else 0,
        )
        run_at = (now + delta).timestamp()
    elif "tomorrow" in text:
        base = now + timedelta(days=1)
        m_t  = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
        if m_t:
            hr = int(m_t.group(1)); mn = int(m_t.group(2) or 0)
            if m_t.group(3)=="pm" and hr!=12: hr+=12
            base = base.replace(hour=hr,minute=mn,second=0,microsecond=0)
        run_at = base.timestamp()
    else:
        try:
            run_at = datetime.fromisoformat(text.replace(" ","T",1)).timestamp()
        except Exception:
            run_at = (now + timedelta(hours=1)).timestamp()
    tasks = _load_sched()
    tasks.append({"task": task, "ts": run_at, "done": False,
                  "created": now.isoformat()})
    with _sched_lock:
        _save_sched(tasks)
    run_dt = datetime.fromtimestamp(run_at)
    return f"Task '{task}' scheduled for {run_dt.strftime('%a %b %d at %H:%M')}, sir."


@register(
    name="list_scheduled_tasks",
    description="List all pending scheduled tasks.",
    parameters={"type":"object","properties":{}},
)
def list_scheduled_tasks() -> str:
    tasks   = _load_sched()
    pending = [t for t in tasks if not t.get("done")]
    if not pending:
        return "No pending scheduled tasks, sir."
    lines = []
    for t in sorted(pending, key=lambda x: x.get("ts",0)):
        dt = datetime.fromtimestamp(t["ts"]).strftime("%a %b %d %H:%M")
        lines.append(f"⏰ [{dt}] {t['task']}")
    return "\n".join(lines)


@register(
    name="cancel_scheduled_task",
    description="Cancel a scheduled task by keyword.",
    parameters={"type":"object","properties":{"keyword":{"type":"string"}},"required":["keyword"]},
)
def cancel_scheduled_task(keyword: str) -> str:
    tasks  = _load_sched()
    q      = keyword.lower()
    before = len([t for t in tasks if not t.get("done")])
    for t in tasks:
        if q in t["task"].lower(): t["done"] = True
    with _sched_lock:
        _save_sched(tasks)
    after = len([t for t in tasks if not t.get("done")])
    removed = before - after
    return f"Cancelled {removed} task(s) matching '{keyword}', sir."
