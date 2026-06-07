"""
Communication Tools — WhatsApp, Email templates, SMS scheduling, Telegram.
"""
import json
import time
from datetime import datetime
from pathlib import Path

import config
from tools.registry import register

_DIR = config.MEMORY_DIR / "communication"
_DIR.mkdir(parents=True, exist_ok=True)
_TEMPLATES_FILE = _DIR / "email_templates.json"
_SCHEDULED_SMS  = _DIR / "scheduled_sms.json"


# ── WhatsApp ───────────────────────────────────────────────────────────────────
@register(
    name="send_whatsapp",
    description="Send a WhatsApp message to a phone number.",
    parameters={"type":"object","properties":{
        "phone":  {"type":"string","description":"Phone number with country code, e.g. +919876543210"},
        "message":{"type":"string","description":"Message text"},
    },"required":["phone","message"]},
)
def send_whatsapp(phone: str, message: str) -> str:
    try:
        import pywhatkit as kit
        # Remove spaces and ensure + prefix
        phone = phone.replace(" ","").replace("-","")
        if not phone.startswith("+"): phone = "+" + phone
        # Send instantly (1 min delay, close after 10s)
        kit.sendwhatmsg_instantly(phone, message, wait_time=10, tab_close=True)
        return f"WhatsApp message sent to {phone}, sir."
    except ImportError:
        return "pywhatkit not installed. Run: pip install pywhatkit, sir."
    except Exception as e:
        return f"WhatsApp error: {e}"


@register(
    name="schedule_whatsapp",
    description="Schedule a WhatsApp message to be sent at a specific time.",
    parameters={"type":"object","properties":{
        "phone":  {"type":"string","description":"Phone number with country code"},
        "message":{"type":"string","description":"Message text"},
        "hour":   {"type":"integer","description":"Hour to send (24h format)"},
        "minute": {"type":"integer","description":"Minute to send"},
    },"required":["phone","message","hour","minute"]},
)
def schedule_whatsapp(phone: str, message: str, hour: int, minute: int) -> str:
    try:
        import pywhatkit as kit
        phone = phone.replace(" ","").replace("-","")
        if not phone.startswith("+"): phone = "+" + phone
        kit.sendwhatmsg(phone, message, hour, minute, wait_time=10, tab_close=True)
        return (f"WhatsApp scheduled for {hour:02d}:{minute:02d} to {phone}, sir.")
    except ImportError:
        return "pywhatkit not installed. Run: pip install pywhatkit, sir."
    except Exception as e:
        return f"WhatsApp schedule error: {e}"


@register(
    name="send_whatsapp_to_contact",
    description="Send a WhatsApp message to a saved contact by name.",
    parameters={"type":"object","properties":{
        "name":   {"type":"string","description":"Contact name"},
        "message":{"type":"string","description":"Message text"},
    },"required":["name","message"]},
)
def send_whatsapp_to_contact(name: str, message: str) -> str:
    contacts_file = config.MEMORY_DIR / "contacts.json"
    if not contacts_file.exists():
        return "No contacts found. Import contacts first, sir."
    try:
        contacts = json.loads(contacts_file.read_text())
        q        = name.lower()
        match    = next((c for c in contacts if q in (c.get("name","")).lower()), None)
        if not match:
            return f"No contact named '{name}' found, sir."
        phone = match.get("phone","")
        if not phone:
            return f"No phone number for '{name}', sir."
        return send_whatsapp(phone, message)
    except Exception as e:
        return f"Contact lookup error: {e}"


# ── Email Templates ────────────────────────────────────────────────────────────
def _load_templates() -> list:
    if _TEMPLATES_FILE.exists():
        try: return json.loads(_TEMPLATES_FILE.read_text())
        except Exception: pass
    return []

def _save_templates(data: list):
    _TEMPLATES_FILE.write_text(json.dumps(data, indent=2))


@register(
    name="save_email_template",
    description="Save a reusable email template.",
    parameters={"type":"object","properties":{
        "name":   {"type":"string","description":"Template name, e.g. 'meeting-request'"},
        "subject":{"type":"string"},
        "body":   {"type":"string","description":"Email body. Use {name}, {date} as placeholders."},
    },"required":["name","subject","body"]},
)
def save_email_template(name: str, subject: str, body: str) -> str:
    templates = _load_templates()
    templates = [t for t in templates if t["name"].lower() != name.lower()]
    templates.append({"name": name, "subject": subject, "body": body,
                      "saved": datetime.now().isoformat()})
    _save_templates(templates)
    return f"Template '{name}' saved, sir."


@register(
    name="list_email_templates",
    description="List all saved email templates.",
    parameters={"type":"object","properties":{}},
)
def list_email_templates() -> str:
    templates = _load_templates()
    if not templates:
        return "No email templates saved, sir."
    return "\n".join(f"• {t['name']}  —  {t['subject']}" for t in templates)


@register(
    name="use_email_template",
    description="Send an email using a saved template.",
    parameters={"type":"object","properties":{
        "template_name":{"type":"string","description":"Template name"},
        "to":           {"type":"string","description":"Recipient email"},
        "variables":    {"type":"string","description":"JSON string of variables to fill in, e.g. {\"name\":\"John\"}"},
    },"required":["template_name","to"]},
)
def use_email_template(template_name: str, to: str, variables: str = "{}") -> str:
    templates = _load_templates()
    q = template_name.lower()
    tmpl = next((t for t in templates if q in t["name"].lower()), None)
    if not tmpl:
        return f"No template named '{template_name}', sir."
    try:
        vars_dict = json.loads(variables) if variables else {}
    except Exception:
        vars_dict = {}
    vars_dict.setdefault("date", datetime.now().strftime("%B %d, %Y"))
    subject = tmpl["subject"].format(**vars_dict)
    body    = tmpl["body"].format(**vars_dict)
    try:
        from tools.gmail import send_email
        return send_email(to=to, subject=subject, body=body)
    except Exception as e:
        return f"Could not send email: {e}"


@register(
    name="delete_email_template",
    description="Delete a saved email template.",
    parameters={"type":"object","properties":{"name":{"type":"string"}},"required":["name"]},
)
def delete_email_template(name: str) -> str:
    templates = _load_templates()
    q = name.lower()
    before = len(templates)
    templates = [t for t in templates if q not in t["name"].lower()]
    _save_templates(templates)
    removed = before - len(templates)
    return f"Removed {removed} template(s), sir."


# ── Telegram Bot ───────────────────────────────────────────────────────────────
_TG_TOKEN_FILE = _DIR / ".telegram_token"
_TG_CHAT_FILE  = _DIR / ".telegram_chat_id"

@register(
    name="setup_telegram",
    description="Set up Telegram bot integration. Provide bot token and chat ID.",
    parameters={"type":"object","properties":{
        "bot_token":{"type":"string","description":"Token from @BotFather"},
        "chat_id":  {"type":"string","description":"Your chat ID (message @userinfobot to get it)"},
    },"required":["bot_token","chat_id"]},
)
def setup_telegram(bot_token: str, chat_id: str) -> str:
    _DIR.mkdir(parents=True, exist_ok=True)
    _TG_TOKEN_FILE.write_text(bot_token.strip())
    _TG_CHAT_FILE.write_text(chat_id.strip())
    return "Telegram bot configured, sir. I can now send messages via Telegram."


@register(
    name="send_telegram",
    description="Send a message via Telegram bot.",
    parameters={"type":"object","properties":{
        "message":{"type":"string"},
        "chat_id":{"type":"string","description":"Override chat ID (optional)"},
    },"required":["message"]},
)
def send_telegram(message: str, chat_id: str = "") -> str:
    token = _TG_TOKEN_FILE.read_text().strip() if _TG_TOKEN_FILE.exists() else ""
    cid   = chat_id or (_TG_CHAT_FILE.read_text().strip() if _TG_CHAT_FILE.exists() else "")
    if not token or not cid:
        return "Telegram not configured. Use setup_telegram first, sir."
    try:
        import urllib.parse, urllib.request
        params = urllib.parse.urlencode({"chat_id": cid, "text": message,
                                          "parse_mode": "Markdown"})
        url    = f"https://api.telegram.org/bot{token}/sendMessage?{params}"
        with urllib.request.urlopen(url, timeout=8) as r:
            resp = json.loads(r.read())
        if resp.get("ok"):
            return "Telegram message sent, sir."
        return f"Telegram error: {resp.get('description','unknown')}"
    except Exception as e:
        return f"Telegram send error: {e}"


@register(
    name="send_telegram_photo",
    description="Send a photo/image via Telegram bot.",
    parameters={"type":"object","properties":{
        "image_path":{"type":"string","description":"Path to the image file"},
        "caption":   {"type":"string","description":"Image caption (optional)"},
    },"required":["image_path"]},
)
def send_telegram_photo(image_path: str, caption: str = "") -> str:
    token = _TG_TOKEN_FILE.read_text().strip() if _TG_TOKEN_FILE.exists() else ""
    cid   = _TG_CHAT_FILE.read_text().strip() if _TG_CHAT_FILE.exists() else ""
    if not token or not cid:
        return "Telegram not configured, sir."
    try:
        import urllib.request, urllib.parse
        url  = f"https://api.telegram.org/bot{token}/sendPhoto"
        path = Path(image_path)
        if not path.exists():
            return f"File not found: {image_path}"
        # Use multipart upload
        boundary = "----JARVISBoundary"
        body  = (f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{cid}\r\n'
                 f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
                 f"--{boundary}\r\n"
                 f'Content-Disposition: form-data; name="photo"; filename="{path.name}"\r\n'
                 f"Content-Type: image/jpeg\r\n\r\n").encode() + path.read_bytes() + \
                f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(url, data=body,
              headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
        return "Photo sent via Telegram, sir." if resp.get("ok") else f"Error: {resp}"
    except Exception as e:
        return f"Telegram photo error: {e}"
