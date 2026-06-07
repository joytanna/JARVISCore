import datetime, json, socket, urllib.parse, urllib.request

import config
from tools.registry import register

_MY_PHONE = getattr(config, "MY_PHONE", "7666639083")
_FAST2SMS_KEY = getattr(config, "FAST2SMS_KEY", "")


@register(
    name="send_whatsapp",
    description="Send a WhatsApp message to a phone number (defaults to owner's number)",
    parameters={
        "type": "object",
        "properties": {
            "message": {"type": "string"},
            "number": {"type": "string", "description": "Phone number with country code e.g. +917666639083"},
        },
        "required": ["message"],
    },
)
def send_whatsapp(message: str, number: str = None) -> str:
    target = number or f"+91{_MY_PHONE}"
    if not target.startswith("+"):
        target = f"+91{target}"
    try:
        import pywhatkit as pwk
        now    = datetime.datetime.now()
        hour   = now.hour
        minute = now.minute + 2
        if minute >= 60:
            hour   = (hour + 1) % 24
            minute -= 60
        pwk.sendwhatmsg(target, message, hour, minute,
                        wait_time=15, tab_close=True, close_time=3)
        return f"WhatsApp message scheduled to {target} at {hour:02d}:{minute:02d}, sir."
    except ImportError:
        # Fallback: open wa.me link in browser
        try:
            import webbrowser, urllib.parse
            text_enc = urllib.parse.quote(message)
            num_clean = target.replace("+", "").replace(" ", "")
            url = f"https://wa.me/{num_clean}?text={text_enc}"
            webbrowser.open(url)
            return (f"Opened WhatsApp Web link for {target}, sir. "
                    f"Click Send in the browser. "
                    f"(Install pywhatkit for fully automatic sending.)")
        except Exception as e:
            return f"WhatsApp error: {e}"
    except Exception as e:
        return f"WhatsApp error: {e}"


@register(
    name="get_phone_remote_url",
    description="Get the URL and QR code to control JARVIS from your phone.",
    parameters={"type": "object", "properties": {}},
)
def get_phone_remote_url() -> str:
    """Return the LAN URL for the JARVIS phone remote page."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except Exception:
        ip = "127.0.0.1"
    port = getattr(config, "API_PORT", 8100)
    url  = f"http://{ip}:{port}/remote"
    qr   = f"https://api.qrserver.com/v1/create-qr-code/?data={urllib.parse.quote(url)}&size=200x200"
    return (
        f"Phone Remote URL: {url}\n"
        f"QR Code: {qr}\n\n"
        f"Instructions:\n"
        f"  1. Connect your phone to the same Wi-Fi as this PC\n"
        f"  2. Scan the QR code or type the URL into your phone's browser\n"
        f"  3. Type or speak commands — no app needed\n\n"
        f"If you can't connect: Windows Firewall may be blocking port {port}.\n"
        f"Run as Admin: netsh advfirewall firewall add rule name=\"JARVIS\" "
        f"dir=in action=allow protocol=TCP localport={port}"
    )


@register(
    name="send_sms",
    description="Send an SMS via Fast2SMS (India only)",
    parameters={
        "type": "object",
        "properties": {
            "number": {"type": "string", "description": "10-digit Indian mobile number"},
            "message": {"type": "string"},
        },
        "required": ["number", "message"],
    },
)
def send_sms(number: str, message: str) -> str:
    if not _FAST2SMS_KEY:
        return "Fast2SMS API key not configured, sir. Set FAST2SMS_KEY in .env."
    try:
        params = urllib.parse.urlencode({
            "authorization": _FAST2SMS_KEY,
            "message": message,
            "language": "english",
            "route": "q",
            "numbers": number,
        })
        req = urllib.request.Request(
            "https://www.fast2sms.com/dev/bulkV2",
            data=params.encode(),
            headers={"cache-control": "no-cache"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            resp = json.loads(r.read())
        if resp.get("return"):
            return f"SMS sent to {number}, sir."
        return f"SMS failed: {resp.get('message', resp)}"
    except Exception as e:
        return f"SMS error: {e}"
