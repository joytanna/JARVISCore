"""
Proactive context awareness — monitors active window and open files.
Auto-starts in background on import.
"""
import ctypes
import re
import threading
import time
from pathlib import Path

import config
from tools.registry import register

_ctx = {"window": "", "file": "", "content": "", "ts": 0}
_lock = threading.Lock()
_running = False

# ── Window title helpers ──────────────────────────────────────────────────────

def _active_title() -> str:
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value
    except Exception:
        return ""


_EDITOR_RE = re.compile(
    r"^(.+?)\s*[-–—]\s*(?:Visual Studio Code|Code|Notepad\+\+|Sublime Text|"
    r"PyCharm|IntelliJ|Notepad|WordPad|Vim|Neovim|nano)\b",
    re.I,
)

def _filepath_from_title(title: str) -> str:
    """Extract a file path from an editor window title if possible."""
    m = _EDITOR_RE.match(title)
    if m:
        candidate = m.group(1).strip()
        p = Path(candidate)
        if p.exists() and p.is_file():
            return str(p)
        # Maybe relative — try common locations
        for base in [Path.home(), config.BASE_DIR]:
            full = base / candidate
            if full.exists():
                return str(full)
    return ""


# ── Watcher loop ─────────────────────────────────────────────────────────────

def _watch_loop():
    last_title = ""
    while _running:
        try:
            title = _active_title()
            if title and title != last_title:
                last_title = title
                filepath = _filepath_from_title(title)
                content = ""
                if filepath:
                    try:
                        content = Path(filepath).read_text(errors="replace")[:4000]
                    except Exception:
                        pass
                with _lock:
                    _ctx["window"] = title
                    _ctx["file"] = filepath
                    _ctx["content"] = content
                    _ctx["ts"] = time.time()
        except Exception:
            pass
        time.sleep(4)


def _start():
    global _running
    if _running:
        return
    _running = True
    threading.Thread(target=_watch_loop, daemon=True, name="ctx_watcher").start()


# ── Tool ─────────────────────────────────────────────────────────────────────

@register(
    name="get_context",
    description="Get what the user is currently working on: active window, open file, and content preview.",
    parameters={"type": "object", "properties": {}},
)
def get_context() -> str:
    with _lock:
        ctx = dict(_ctx)
    if not ctx["window"]:
        return "No active window detected, sir."
    parts = [f"Active: {ctx['window']}"]
    if ctx["file"]:
        parts.append(f"File: {ctx['file']}")
        if ctx["content"]:
            parts.append(f"Preview:\n{ctx['content'][:800]}")
    return "\n".join(parts)


@register(
    name="summarise_context",
    description="Summarise what the user is currently working on using AI.",
    parameters={"type": "object", "properties": {}},
)
def summarise_context() -> str:
    with _lock:
        ctx = dict(_ctx)
    if not ctx["window"]:
        return "Nothing notable on screen, sir."
    if not ctx["content"]:
        return f"You have '{ctx['window']}' active, sir. No readable file content."
    from brain.core import get_brain
    brain = get_brain()
    prompt = (
        f"Window: {ctx['window']}\nFile: {ctx['file']}\n\n"
        f"Content:\n{ctx['content'][:3000]}\n\n"
        "In 2-3 sentences, what is the user working on? Be concise."
    )
    return brain.quick(prompt, max_tokens=150)


# Auto-start on import
_start()
