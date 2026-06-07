"""
pywebview-based UI wrapper.
Loads the app from http://localhost:{API_PORT}/app so the same HTML
is served both in the native window and from any browser on the LAN.
"""
import json
import threading
import time
from pathlib import Path

import webview
import config

_FALLBACK_HTML = Path(__file__).parent / "app.html"


# ── JS API exposed to the browser ─────────────────────────────────────────────
class JsApi:
    def __init__(self):
        self._command_fn = None   # callable(text)
        self._window     = None   # set after create_window

    def send_command(self, text: str):
        if self._command_fn and text.strip():
            threading.Thread(target=self._command_fn,
                             args=(text.strip(),), daemon=True).start()

    def get_status(self) -> dict:
        out = {"cpu": None, "ram": None,
               "voice_enrolled": False, "gmail_connected": False}
        try:
            import psutil
            out["cpu"] = round(psutil.cpu_percent(interval=None), 1)
            out["ram"] = round(psutil.virtual_memory().percent, 1)
        except ImportError:
            pass
        try:
            out["gmail_connected"] = (config.MEMORY_DIR / "google_token.json").exists()
        except Exception:
            pass
        try:
            out["voice_enrolled"] = any((config.MEMORY_DIR / f).exists()
                                        for f in ("voice_profile.npy", "voice_model.pkl"))
        except Exception:
            pass
        return out

    def get_remote_info(self) -> dict:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]; s.close()
        except Exception:
            ip = "127.0.0.1"
        url = f"http://{ip}:{config.API_PORT}/remote"
        return {"url": url, "ip": ip}

    def enroll_voice(self) -> str:
        try:
            from tools.voice_tools import enroll_voice
            return enroll_voice()
        except Exception as e:
            return f"Enrolment error: {e}"

    def import_contacts(self) -> str:
        try:
            from tools.contacts_import import import_phone_contacts
            return import_phone_contacts()
        except Exception as e:
            return f"Import error: {e}"

    def push_to_devices(self, message: str):
        try:
            from jarvis import _push_to_remotes
            _push_to_remotes({"type": "push", "text": message})
        except Exception:
            pass

    def pick_file(self):
        if self._window:
            paths = self._window.create_file_dialog(webview.OPEN_DIALOG)
            if paths and self._command_fn:
                threading.Thread(target=self._command_fn,
                                 args=(f"summarise file {paths[0]}",),
                                 daemon=True).start()

    def hide_window(self):
        if self._window:
            self._window.hide()


# ── WebUI public class ────────────────────────────────────────────────────────
class WebUI:
    def __init__(self, on_input):
        self._api             = JsApi()
        self._api._command_fn = on_input
        self._window          = None

    def _js(self, code: str):
        if self._window:
            try: self._window.evaluate_js(code)
            except Exception: pass

    def set_state(self, state: str):
        self._js(f"window.setState && window.setState('{state}')")

    def add_message(self, text: str, tag: str = "jarvis"):
        self._js(f"window.addMessage && window.addMessage({json.dumps(text)}, '{tag}')")

    def append_log(self, text: str, log_type: str = "info"):
        self._js(f"window.appendLog && window.appendLog({json.dumps(text)}, '{log_type}')")

    def update_devices(self, devices: list):
        self._js(f"window.updateDevices && window.updateDevices({json.dumps(devices)})")

    def show(self):
        if self._window: self._window.show()

    def hide(self):
        if self._window: self._window.hide()

    def run(self, root=None):
        """Block main thread on the webview event loop."""
        # Wait up to 3 s for the FastAPI server to start, then load from URL
        server_url = f"http://127.0.0.1:{config.API_PORT}/app"

        def _wait_and_open():
            """Delay loading until API is up, then navigate."""
            import urllib.request
            for _ in range(30):
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{config.API_PORT}/health",
                                           timeout=0.5)
                    break
                except Exception:
                    time.sleep(0.2)

        self._window = webview.create_window(
            title            = "JARVIS // Personal AI OS",
            url              = str(_FALLBACK_HTML),   # shown instantly
            js_api           = self._api,
            width            = 1440,
            height           = 880,
            resizable        = True,
            min_size         = (960, 600),
            background_color = "#05070c",
        )
        self._api._window = self._window

        def _on_loaded():
            # Once the window is ready, switch to the server URL
            _wait_and_open()
            try:
                self._window.load_url(server_url)
            except Exception:
                pass   # stay on local file if server not available

        threading.Thread(target=_on_loaded, daemon=True).start()

        try:
            webview.start(gui="edgechromium", debug=False)
        except Exception:
            webview.start(debug=False)
