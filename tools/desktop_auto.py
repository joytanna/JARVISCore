"""
Desktop automation — mouse clicks, keyboard input, hotkeys, drag, scroll.
Requires: pip install pyautogui
Move mouse to top-left corner (0,0) to abort any running automation (failsafe).
"""
import time
from pathlib import Path

import config
from tools.registry import register

_SAVE_DIR = config.MEMORY_DIR / "screenshots"


def _pg():
    """Return pyautogui, raising a clear error if not installed."""
    try:
        import pyautogui
        pyautogui.FAILSAFE = True   # Top-left corner = emergency stop
        pyautogui.PAUSE = 0.08
        return pyautogui
    except ImportError:
        raise RuntimeError(
            "pyautogui not installed. Run: pip install pyautogui"
        )


@register(
    name="click_at",
    description="Click the mouse at specific screen coordinates.",
    parameters={
        "type": "object",
        "properties": {
            "x":       {"type": "integer"},
            "y":       {"type": "integer"},
            "button":  {"type": "string",  "description": "left, right, or middle (default: left)"},
            "clicks":  {"type": "integer", "description": "Number of clicks (default: 1)"},
        },
        "required": ["x", "y"],
    },
)
def click_at(x: int, y: int, button: str = "left", clicks: int = 1) -> str:
    _pg().click(x, y, button=button, clicks=clicks, interval=0.1)
    return f"Clicked {button}×{clicks} at ({x}, {y}), sir."


@register(
    name="move_mouse",
    description="Move the mouse cursor to screen coordinates.",
    parameters={
        "type": "object",
        "properties": {
            "x": {"type": "integer"},
            "y": {"type": "integer"},
        },
        "required": ["x", "y"],
    },
)
def move_mouse(x: int, y: int) -> str:
    _pg().moveTo(x, y, duration=0.25)
    return f"Mouse moved to ({x}, {y}), sir."


@register(
    name="type_text",
    description="Type text using the keyboard, as if physically typed.",
    parameters={
        "type": "object",
        "properties": {
            "text":     {"type": "string"},
            "interval": {"type": "number", "description": "Seconds between keystrokes (default 0.02)"},
        },
        "required": ["text"],
    },
)
def type_text(text: str, interval: float = 0.02) -> str:
    pg = _pg()
    # pyautogui.typewrite only handles ASCII; use pyperclip+paste for unicode
    try:
        import pyperclip
        prev = pyperclip.paste()
        pyperclip.copy(text)
        pg.hotkey("ctrl", "v")
        time.sleep(0.1)
        # Restore clipboard
        pyperclip.copy(prev)
    except ImportError:
        pg.typewrite(text, interval=interval)
    preview = text[:40] + ("…" if len(text) > 40 else "")
    return f"Typed: {preview}"


@register(
    name="press_hotkey",
    description="Press a keyboard shortcut. Examples: 'ctrl+c', 'alt+tab', 'win+d', 'ctrl+shift+t'.",
    parameters={
        "type": "object",
        "properties": {
            "keys": {"type": "string", "description": "Keys joined by +, e.g. 'ctrl+c'"},
        },
        "required": ["keys"],
    },
)
def press_hotkey(keys: str) -> str:
    parts = [k.strip() for k in keys.split("+")]
    _pg().hotkey(*parts)
    return f"Hotkey '{keys}' pressed, sir."


@register(
    name="scroll_at",
    description="Scroll the mouse wheel at given coordinates.",
    parameters={
        "type": "object",
        "properties": {
            "x":      {"type": "integer"},
            "y":      {"type": "integer"},
            "amount": {"type": "integer", "description": "Positive=scroll up, negative=scroll down (default: 3)"},
        },
        "required": ["x", "y"],
    },
)
def scroll_at(x: int, y: int, amount: int = 3) -> str:
    _pg().scroll(amount, x=x, y=y)
    direction = "up" if amount > 0 else "down"
    return f"Scrolled {direction} {abs(amount)} units at ({x},{y}), sir."


@register(
    name="drag_mouse",
    description="Click and drag the mouse from one point to another.",
    parameters={
        "type": "object",
        "properties": {
            "from_x":   {"type": "integer"},
            "from_y":   {"type": "integer"},
            "to_x":     {"type": "integer"},
            "to_y":     {"type": "integer"},
            "duration": {"type": "number", "description": "Seconds for drag (default 0.5)"},
        },
        "required": ["from_x", "from_y", "to_x", "to_y"],
    },
)
def drag_mouse(from_x: int, from_y: int, to_x: int, to_y: int, duration: float = 0.5) -> str:
    _pg().moveTo(from_x, from_y, duration=0.2)
    _pg().dragTo(to_x, to_y, duration=duration, button="left")
    return f"Dragged ({from_x},{from_y}) → ({to_x},{to_y}), sir."


@register(
    name="get_mouse_position",
    description="Get the current mouse cursor coordinates on screen.",
    parameters={"type": "object", "properties": {}},
)
def get_mouse_position() -> str:
    pos = _pg().position()
    return f"Mouse is at ({pos.x}, {pos.y}), sir."


@register(
    name="take_automation_screenshot",
    description="Take a screenshot of the current screen and open it.",
    parameters={
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "Optional filename (auto-generated if omitted)"},
        },
    },
)
def take_automation_screenshot(filename: str = None) -> str:
    _SAVE_DIR.mkdir(parents=True, exist_ok=True)
    if not filename:
        filename = f"auto_{int(time.time())}.png"
    path = _SAVE_DIR / filename
    _pg().screenshot(str(path))
    import os
    os.startfile(str(path))
    return f"Screenshot saved as {filename}, sir."


@register(
    name="focus_window",
    description="Bring a specific application window to the foreground by partial title match.",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Partial window title to search for"},
        },
        "required": ["title"],
    },
)
def focus_window(title: str) -> str:
    try:
        import pygetwindow as gw
        matches = gw.getWindowsWithTitle(title)
        if not matches:
            # Partial match
            all_wins = gw.getAllTitles()
            matches = [gw.getWindowsWithTitle(t)[0] for t in all_wins
                       if title.lower() in t.lower() and t.strip()]
        if not matches:
            return f"No window matching '{title}' found, sir."
        matches[0].activate()
        return f"Focused '{matches[0].title}', sir."
    except ImportError:
        return run_shell_helper(f'powershell -command "(Get-Process | Where-Object {{$_.MainWindowTitle -like \'*{title}*\'}} | Select-Object -First 1).MainWindowHandle | ForEach-Object {{[void][System.Runtime.InteropServices.Marshal]::ShowWindowAsync($_, 5)}}"')
    except Exception as e:
        return f"Focus error: {e}"


def run_shell_helper(cmd: str) -> str:
    import subprocess
    try:
        subprocess.run(cmd, shell=True, timeout=5)
        return "Done, sir."
    except Exception as e:
        return f"Error: {e}"
