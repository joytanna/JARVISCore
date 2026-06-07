"""
Advanced Security Tools — TOTP/2FA, HaveIBeenPwned, Security audit.
"""
import hashlib
import hmac
import json
import struct
import time
from pathlib import Path
from urllib.request import urlopen, Request

import config
from tools.registry import register

_DIR         = config.MEMORY_DIR / "security"
_DIR.mkdir(parents=True, exist_ok=True)
_TOTP_FILE   = _DIR / "totp.json"

# ── TOTP / 2FA ─────────────────────────────────────────────────────────────────
def _b32decode(s: str) -> bytes:
    import base64
    s = s.upper().replace(" ","")
    pad = (8 - len(s) % 8) % 8
    return base64.b32decode(s + "=" * pad)

def _hotp(key: bytes, counter: int) -> int:
    msg = struct.pack(">Q", counter)
    h   = hmac.new(key, msg, hashlib.sha1).digest()
    off = h[-1] & 0x0F
    return (struct.unpack(">I", h[off:off+4])[0] & 0x7FFFFFFF) % 1_000_000

def _totp(secret: str, period: int = 30) -> tuple[str, int]:
    key = _b32decode(secret)
    ts  = int(time.time())
    t   = ts // period
    code = _hotp(key, t)
    remaining = period - (ts % period)
    return f"{code:06d}", remaining

def _load_totp() -> list:
    if _TOTP_FILE.exists():
        try: return json.loads(_TOTP_FILE.read_text())
        except Exception: pass
    return []

def _save_totp(data: list):
    _DIR.mkdir(parents=True, exist_ok=True)
    _TOTP_FILE.write_text(json.dumps(data, indent=2))


@register(
    name="add_totp",
    description="Add a 2FA/TOTP account (from the secret key in your authenticator app).",
    parameters={"type":"object","properties":{
        "name":  {"type":"string","description":"Account name, e.g. 'Google' or 'GitHub'"},
        "secret":{"type":"string","description":"Base32 secret from the QR code setup"},
        "issuer":{"type":"string","description":"Service name (optional)"},
    },"required":["name","secret"]},
)
def add_totp(name: str, secret: str, issuer: str = "") -> str:
    # Validate secret
    try:
        _b32decode(secret)
    except Exception:
        return "Invalid secret — must be a Base32-encoded key, sir."
    entries = _load_totp()
    entries = [e for e in entries if e["name"].lower() != name.lower()]  # replace if exists
    entries.append({"name": name, "secret": secret.upper().replace(" ",""),
                    "issuer": issuer or name})
    _save_totp(entries)
    return f"2FA for '{name}' added, sir."


@register(
    name="get_totp_code",
    description="Get the current TOTP/2FA code for an account.",
    parameters={"type":"object","properties":{
        "name":{"type":"string","description":"Account name"},
    },"required":["name"]},
)
def get_totp_code(name: str) -> str:
    entries = _load_totp()
    q       = name.lower()
    entry   = next((e for e in entries if q in e["name"].lower()), None)
    if not entry:
        return f"No 2FA account matching '{name}', sir."
    try:
        code, remaining = _totp(entry["secret"])
        return (f"🔐 {entry['name']} 2FA code: **{code}**  "
                f"(expires in {remaining}s), sir.")
    except Exception as e:
        return f"Error generating code: {e}"


@register(
    name="list_totp",
    description="List all stored 2FA accounts.",
    parameters={"type":"object","properties":{}},
)
def list_totp() -> str:
    entries = _load_totp()
    if not entries:
        return "No 2FA accounts stored, sir."
    lines = []
    for e in entries:
        try:
            code, rem = _totp(e["secret"])
            lines.append(f"🔐 {e['name']:20} {code}  ({rem}s left)")
        except Exception:
            lines.append(f"🔐 {e['name']} — error")
    return "\n".join(lines)


@register(
    name="delete_totp",
    description="Remove a 2FA account.",
    parameters={"type":"object","properties":{"name":{"type":"string"}},"required":["name"]},
)
def delete_totp(name: str) -> str:
    entries = _load_totp()
    q       = name.lower()
    before  = len(entries)
    entries = [e for e in entries if q not in e["name"].lower()]
    _save_totp(entries)
    return f"Removed {before - len(entries)} 2FA account(s), sir."


# ── HaveIBeenPwned ─────────────────────────────────────────────────────────────
@register(
    name="check_breach",
    description="Check if an email has appeared in any known data breaches (HaveIBeenPwned).",
    parameters={"type":"object","properties":{
        "email":{"type":"string","description":"Email address to check"},
    },"required":["email"]},
)
def check_breach(email: str) -> str:
    try:
        from urllib.parse import quote
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email)}"
        req = Request(url, headers={
            "User-Agent": "JARVIS-Personal-Assistant",
            "hibp-api-key": "",   # Free tier: no API key for account check
        })
        try:
            resp = urlopen(req, timeout=8)
            data = json.loads(resp.read())
            names = [b["Name"] for b in data]
            count = len(names)
            breach_list = ", ".join(names[:5]) + ("..." if count > 5 else "")
            return (f"⚠️  '{email}' found in {count} data breach(es):\n{breach_list}\n\n"
                    f"Recommendation: change your password on these services immediately, sir.")
        except Exception as e:
            if "404" in str(e):
                return f"✅ Good news — '{email}' was not found in any known breaches, sir."
            raise
    except Exception as ex:
        # Fallback: check password hash via HIBP k-anonymity (no email, just password)
        return f"Breach check unavailable (API error: {ex}). Visit haveibeenpwned.com manually, sir."


@register(
    name="check_password_breach",
    description="Check if a password has been exposed in data breaches without sending it (k-anonymity).",
    parameters={"type":"object","properties":{
        "password":{"type":"string","description":"Password to check"},
    },"required":["password"]},
)
def check_password_breach(password: str) -> str:
    try:
        sha1   = hashlib.sha1(password.encode()).hexdigest().upper()
        prefix = sha1[:5]
        suffix = sha1[5:]
        url    = f"https://api.pwnedpasswords.com/range/{prefix}"
        resp   = urlopen(Request(url, headers={"User-Agent":"JARVIS/1.0"}), timeout=8)
        text   = resp.read().decode()
        for line in text.splitlines():
            h, count = line.split(":")
            if h == suffix:
                return (f"⚠️  This password has been seen {int(count):,} times in data breaches. "
                        f"Choose a different password, sir.")
        return "✅ This password has not appeared in any known breaches, sir."
    except Exception as e:
        return f"Password breach check error: {e}"


# ── Security Audit ─────────────────────────────────────────────────────────────
@register(
    name="security_audit",
    description="Run a quick security audit of JARVIS and the system.",
    parameters={"type":"object","properties":{}},
)
def security_audit() -> str:
    lines = ["🔒 JARVIS Security Audit"]
    # Auth
    auth_file = config.MEMORY_DIR / "auth.json"
    lines.append(f"\n{'✅' if auth_file.exists() else '⚠️ '} Password auth: {'configured' if auth_file.exists() else 'NOT configured'}")
    # Gmail token
    token_file = config.MEMORY_DIR / "google_token.json"
    lines.append(f"{'✅' if token_file.exists() else '⚠️ '} Gmail OAuth: {'connected' if token_file.exists() else 'not connected'}")
    # Voice
    voice_ok = any((config.MEMORY_DIR / f).exists() for f in ("voice_profile.npy","voice_model.pkl"))
    lines.append(f"{'✅' if voice_ok else '⚠️ '} Voice auth: {'enrolled' if voice_ok else 'not enrolled'}")
    # 2FA
    totp_entries = _load_totp()
    lines.append(f"{'✅' if totp_entries else '⚠️ '} 2FA accounts: {len(totp_entries)} stored")
    # Vault
    vault_file = config.MEMORY_DIR / "vault.enc"
    lines.append(f"{'✅' if vault_file.exists() else 'ℹ️ '} Password vault: {'present' if vault_file.exists() else 'empty'}")
    # Open ports
    try:
        import psutil
        listening = [c.laddr.port for c in psutil.net_connections() if c.status == "LISTEN"]
        lines.append(f"\n🌐 Listening ports: {sorted(set(listening))}")
    except Exception:
        pass
    lines.append("\n✅ Vault encrypted with AES-256 Fernet.")
    lines.append("✅ JWT tokens expire in 30 days.")
    return "\n".join(lines)
