import os, socket

import config
from tools.registry import register


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


@register(
    name="show_remote_qr",
    description="Generate and display a QR code for controlling JARVIS from a phone on the local network",
    parameters={"type": "object", "properties": {}},
)
def show_remote_qr() -> str:
    ip = _local_ip()
    url = f"http://{ip}:{config.API_PORT}"
    qr_path = str(config.BASE_DIR / "remote_qr.png")
    try:
        import qrcode
    except ImportError:
        import subprocess, sys
        subprocess.run([sys.executable, "-m", "pip", "install", "qrcode[pil]"],
                       capture_output=True)
        try:
            import qrcode
        except ImportError:
            return f"Done. Remote URL: {url} — open this on your phone's browser."
    try:
        img = qrcode.make(url)
        img.save(qr_path)
        os.startfile(qr_path)
        return f"Done. QR code opened. Scan with your phone (same Wi-Fi). URL: {url}"
    except Exception as e:
        return f"Done. Remote URL: {url}"
