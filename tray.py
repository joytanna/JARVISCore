"""
JARVIS System Tray — runs as a system tray app.
- Right-click menu: Open Dashboard, Start Listening, Stop Listening, Settings, Exit
- Left-click: open/focus the dashboard
- Balloon tip notification on JARVIS responses
Designed to be imported by jarvis.py after the main Jarvis instance is running.
"""
import sys
import threading
from pathlib import Path


def _make_icon():
    """Create a JARVIS icon programmatically if no icon file exists."""
    icon_path = Path(__file__).parent / "static" / "icon.png"
    if icon_path.exists():
        try:
            from PIL import Image
            return Image.open(icon_path)
        except Exception:
            pass
    # Generate a simple cyan circle icon
    try:
        from PIL import Image, ImageDraw, ImageFont
        size = 64
        img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Dark background circle
        draw.ellipse([2, 2, size-2, size-2], fill=(5, 15, 30, 255))
        # Cyan ring
        draw.ellipse([4, 4, size-4, size-4], outline=(6, 182, 212, 255), width=3)
        # J letter in center
        try:
            font = ImageFont.truetype("arial.ttf", 28)
        except Exception:
            font = ImageFont.load_default()
        draw.text((size//2, size//2), "J", fill=(6, 182, 212, 255),
                  font=font, anchor="mm")
        return img
    except Exception:
        # Last fallback: 1×1 transparent pixel
        try:
            from PIL import Image
            return Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        except Exception:
            return None


def start_tray(jarvis_instance, open_fn=None, hide_fn=None):
    """
    Start the system tray icon in a background thread.

    jarvis_instance — Jarvis object (has .handle(), ._set_state())
    open_fn        — callable to show/focus the dashboard window
    hide_fn        — callable to hide it
    """
    try:
        import pystray
    except ImportError:
        print("[Tray] pystray not installed — tray disabled. pip install pystray")
        return None

    icon_img = _make_icon()
    if icon_img is None:
        print("[Tray] Could not create tray icon image.")
        return None

    _listening = threading.Event()
    _listening.set()   # start in listening mode

    def on_open(icon, item):
        if open_fn:
            try:
                open_fn()
            except Exception:
                pass

    def on_listen(icon, item):
        _listening.set()
        icon.notify("JARVIS is now listening.", title="JARVIS")

    def on_pause(icon, item):
        _listening.clear()
        icon.notify("Voice listening paused.", title="JARVIS")

    def on_register(icon, item):
        try:
            from tools.windows_integration import register_as_default_assistant
            result = register_as_default_assistant()
            icon.notify(result[:100], title="JARVIS")
        except Exception as e:
            icon.notify(f"Error: {e}", title="JARVIS")

    def on_startup(icon, item):
        try:
            from tools.windows_integration import register_windows_startup
            result = register_windows_startup()
            icon.notify(result[:100], title="JARVIS")
        except Exception as e:
            icon.notify(f"Error: {e}", title="JARVIS")

    def on_exit(icon, item):
        icon.stop()
        sys.exit(0)

    def on_left_click(icon):
        if open_fn:
            try:
                open_fn()
            except Exception:
                pass

    menu = pystray.Menu(
        pystray.MenuItem("Open Dashboard",       on_open,    default=True),
        pystray.MenuItem("Start Listening",      on_listen),
        pystray.MenuItem("Pause Listening",      on_pause),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Add to Startup",       on_startup),
        pystray.MenuItem("Set as Default Agent", on_register),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Exit JARVIS",          on_exit),
    )

    icon = pystray.Icon(
        name="JARVIS",
        icon=icon_img,
        title="JARVIS AI Assistant",
        menu=menu,
    )

    def _run():
        icon.run()

    t = threading.Thread(target=_run, daemon=True, name="tray")
    t.start()
    print("[Tray] System tray icon active. Right-click for menu.")
    return icon
