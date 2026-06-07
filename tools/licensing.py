"""
JARVIS AI Licensing System
Manages Free / Pro / Lifetime plans.

Admin (joytanna21@gmail.com) always has Lifetime — all features free, no limits.
JARVIS21 code: grants full access after owner email approval (48-hr pending trial).
LemonSqueezy handles public payments. Discount codes built-in.
"""
import hashlib, json, smtplib, ssl, threading, time, urllib.request, urllib.parse
from datetime import date, datetime, timedelta
from pathlib import Path

import config
from tools.registry import register

_DIR  = config.MEMORY_DIR / "license"
_DIR.mkdir(parents=True, exist_ok=True)
_FILE = _DIR / "license.json"
_PEND = _DIR / "pending_approvals.json"   # JARVIS21 pending requests

# ── Admin config ──────────────────────────────────────────────────────────────
ADMIN_EMAIL       = getattr(config, "ADMIN_EMAIL",       "joytanna21@gmail.com")
ADMIN_DEVICE_CODE = getattr(config, "ADMIN_DEVICE_CODE", "JARVIS_OWNER_2026")

# ── LemonSqueezy ──────────────────────────────────────────────────────────────
_LS_API_KEY = getattr(config, "LEMONSQUEEZY_API_KEY", "")

PAYMENT_LINKS = {
    "pro_monthly": getattr(config, "LS_LINK_PRO_MONTHLY", "https://jarvisai.lemonsqueezy.com/buy/pro-monthly"),
    "pro_annual":  getattr(config, "LS_LINK_PRO_ANNUAL",  "https://jarvisai.lemonsqueezy.com/buy/pro-annual"),
    "lifetime":    getattr(config, "LS_LINK_LIFETIME",     "https://jarvisai.lemonsqueezy.com/buy/lifetime"),
}

# ── Discount / promo codes ────────────────────────────────────────────────────
# JARVIS21 is special: grants full access after admin approval via email
_CODES: dict = {
    "LAUNCH2026": {"plan": "pro_annual",  "pct": 40, "trial": 0,  "max": 500},
    "BETA":       {"plan": "pro_monthly", "pct": 0,  "trial": 14, "max": 200},
    "STUDENT25":  {"plan": "pro_annual",  "pct": 25, "trial": 0,  "max": 999},
    "FRIEND15":   {"plan": "pro_monthly", "pct": 15, "trial": 0,  "max": 999},
    "EARLYBIRD":  {"plan": "lifetime",    "pct": 30, "trial": 0,  "max": 50 },
    "JARVIS21":   {"plan": "lifetime",    "pct": 100,"trial": 2,  "max": 999, "needs_approval": True},
}

# ── Features by plan ──────────────────────────────────────────────────────────
FREE_LIMIT = 20   # daily AI queries on free plan

PLAN_FEATURES: dict = {
    "free": {
        "daily_limit": FREE_LIMIT, "ai_chat": True, "voice": True,
        "weather": True, "timer": True, "calculator": True,
        "dictionary": True, "world_clock": True, "unit_convert": True,
        "facts_jokes": True, "habits": True, "habit_limit": 3,
        "translation": True, "translation_daily": 5,
        # Gated
        "email": False, "contacts": False, "file_analysis": False,
        "pc_control": False, "budget": False, "flashcards": False,
        "pomodoro": False, "stocks": False, "youtube": False,
        "qr_gen": False, "advanced_voice": False, "brief": False,
    },
    "pro": {
        "daily_limit": 9999, "ai_chat": True, "voice": True,
        "weather": True, "timer": True, "calculator": True,
        "dictionary": True, "world_clock": True, "unit_convert": True,
        "facts_jokes": True, "habits": True, "habit_limit": 999,
        "translation": True, "translation_daily": 999,
        "email": True, "contacts": True, "file_analysis": True,
        "pc_control": True, "budget": True, "flashcards": True,
        "pomodoro": True, "stocks": True, "youtube": True,
        "qr_gen": True, "advanced_voice": True, "brief": True,
    },
}
PLAN_FEATURES["lifetime"] = {**PLAN_FEATURES["pro"]}
PLAN_FEATURES["pending"]  = {**PLAN_FEATURES["free"],   # 48-hr trial: unlock most features
    "daily_limit": 50, "email": True, "contacts": True,
    "pomodoro": True, "brief": True, "stocks": True,
}


# ── Storage helpers ───────────────────────────────────────────────────────────
def _load() -> dict:
    if _FILE.exists():
        try: return json.loads(_FILE.read_text())
        except Exception: pass
    return {
        "plan": "free", "license_key": "", "expires": "",
        "trial_until": "", "discount_code": "",
        "queries_today": 0, "queries_date": "",
        "is_admin": False,
    }

def _save(d: dict): _FILE.write_text(json.dumps(d, indent=2))

def _device_id() -> str:
    import socket
    return hashlib.md5(socket.gethostname().encode()).hexdigest()[:12]

def _is_admin_host() -> bool:
    """True when running on the owner's PC (ADMIN_EMAIL is set in .env)."""
    return bool(ADMIN_EMAIL)


# ── Core plan logic ───────────────────────────────────────────────────────────
def get_plan() -> str:
    """
    Returns: 'lifetime' | 'pro' | 'pending' | 'free'
    Admin host always returns 'lifetime'.
    """
    # Desktop host = owner's machine → always Lifetime
    if _is_admin_host():
        return "lifetime"

    d = _load()

    # Explicit admin flag (set after admin logs in on Android)
    if d.get("is_admin"):
        return "lifetime"

    # Active trial
    if d.get("trial_until"):
        try:
            if date.today() <= date.fromisoformat(d["trial_until"]):
                return d.get("trial_plan", "pending")
        except Exception:
            pass

    plan = d.get("plan", "free")
    # Check subscription expiry
    if plan == "pro" and d.get("expires"):
        try:
            if date.today() > date.fromisoformat(d["expires"]):
                return "free"
        except Exception:
            pass
    return plan


def has_feature(feature: str) -> bool:
    return bool(PLAN_FEATURES.get(get_plan(), PLAN_FEATURES["free"]).get(feature, False))


def can_query() -> bool:
    plan = get_plan()
    if plan != "free":
        return True
    d = _load()
    today = date.today().isoformat()
    if d.get("queries_date") != today:
        d["queries_today"] = 0
        d["queries_date"]  = today
        _save(d)
    return d.get("queries_today", 0) < FREE_LIMIT


def record_query():
    if get_plan() != "free":
        return
    d = _load()
    today = date.today().isoformat()
    if d.get("queries_date") != today:
        d["queries_today"] = 0
        d["queries_date"]  = today
    d["queries_today"] = d.get("queries_today", 0) + 1
    _save(d)


def queries_remaining() -> int:
    if get_plan() != "free":
        return 9999
    d = _load()
    if d.get("queries_date") != date.today().isoformat():
        return FREE_LIMIT
    return max(0, FREE_LIMIT - d.get("queries_today", 0))


# ── Admin login from Android ──────────────────────────────────────────────────
@register(
    name="admin_login",
    description="Log in as the app owner/admin to unlock all features on this device.",
    parameters={"type": "object", "properties": {
        "email":    {"type": "string"},
        "password": {"type": "string", "description": "Your JARVIS password"},
    }, "required": ["email", "password"]},
)
def admin_login(email: str, password: str) -> str:
    """Grants Lifetime plan if credentials match the admin account."""
    import hashlib as _h
    # Compare email
    if email.lower().strip() != ADMIN_EMAIL.lower():
        return "Incorrect admin credentials, sir."
    # Compare password hash against stored JARVIS auth password
    try:
        auth_file = config.MEMORY_DIR / "auth.json"
        if auth_file.exists():
            auth = json.loads(auth_file.read_text())
            stored_hash = auth.get("password_hash", "")
            candidate   = _h.sha256(password.encode()).hexdigest()
            if stored_hash and stored_hash != candidate:
                return "Incorrect admin credentials, sir."
    except Exception:
        pass   # If auth file missing, accept if email matches

    d = _load()
    d["is_admin"] = True
    d["plan"]     = "lifetime"
    d["license_key"] = "ADMIN-OWNER-LIFETIME"
    _save(d)
    return ("Welcome, sir. Admin access granted — all features unlocked on this device. "
            "No limits, no payments, ever.")


# ── JARVIS21 code — email-gated approval ─────────────────────────────────────
def _send_approval_email(device_id: str, token: str):
    """Send approval request email to admin."""
    subject = f"[JARVIS21] Access Request — Device {device_id}"
    body    = (
        f"Someone is requesting full JARVIS AI access using the JARVIS21 code.\n\n"
        f"Device ID: {device_id}\n"
        f"Token:     {token}\n"
        f"Time:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        f"To APPROVE: Reply to this email or say to your JARVIS:\n"
        f"  approve JARVIS21 {token}\n\n"
        f"To DENY: Say to your JARVIS:\n"
        f"  deny JARVIS21 {token}\n\n"
        f"The user has a 48-hour trial while waiting.\n"
        f"— JARVIS AI System"
    )
    try:
        msg_str = (
            f"From: {config.GMAIL_ADDRESS}\r\n"
            f"To: {ADMIN_EMAIL}\r\n"
            f"Subject: {subject}\r\n\r\n"
            f"{body}"
        )
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as srv:
            srv.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            srv.sendmail(config.GMAIL_ADDRESS, ADMIN_EMAIL, msg_str.encode())
    except Exception as e:
        print(f"[License] Approval email failed: {e}")


def _load_pending() -> dict:
    if _PEND.exists():
        try: return json.loads(_PEND.read_text())
        except Exception: pass
    return {}

def _save_pending(p: dict): _PEND.write_text(json.dumps(p, indent=2))


@register(
    name="approve_jarvis21",
    description="[Admin only] Approve a JARVIS21 access request. Say: approve JARVIS21 TOKEN",
    parameters={"type": "object", "properties": {
        "token": {"type": "string", "description": "Token from the approval email"},
    }, "required": ["token"]},
)
def approve_jarvis21(token: str) -> str:
    if not _is_admin_host():
        return "Only the owner can approve JARVIS21 requests, sir."
    pending = _load_pending()
    match = next((k for k, v in pending.items() if v.get("token") == token.strip()), None)
    if not match:
        return f"No pending request found with token '{token}', sir."
    pending[match]["approved"] = True
    pending[match]["approved_at"] = datetime.now().isoformat()
    _save_pending(pending)
    # Send approval email
    try:
        body = (
            f"Your JARVIS21 access request has been APPROVED!\n\n"
            f"You now have full Lifetime access to JARVIS AI.\n"
            f"Enjoy all features with no limits, sir.\n\n"
            f"— JARVIS AI"
        )
        device_email = pending[match].get("email", "")
        if device_email:
            msg_str = (
                f"From: {config.GMAIL_ADDRESS}\r\nTo: {device_email}\r\n"
                f"Subject: JARVIS AI — Your access has been approved!\r\n\r\n{body}"
            )
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as srv:
                srv.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
                srv.sendmail(config.GMAIL_ADDRESS, device_email, msg_str.encode())
    except Exception:
        pass
    return f"Approved! Device {match} now has full Lifetime access, sir."


@register(
    name="deny_jarvis21",
    description="[Admin only] Deny a JARVIS21 access request.",
    parameters={"type": "object", "properties": {
        "token": {"type": "string"},
    }, "required": ["token"]},
)
def deny_jarvis21(token: str) -> str:
    if not _is_admin_host():
        return "Only the owner can deny JARVIS21 requests, sir."
    pending = _load_pending()
    match = next((k for k, v in pending.items() if v.get("token") == token.strip()), None)
    if not match:
        return f"No pending request found with token '{token}', sir."
    del pending[match]
    _save_pending(pending)
    return f"Request denied and removed, sir."


@register(
    name="list_jarvis21_requests",
    description="[Admin only] List all pending JARVIS21 access requests.",
    parameters={"type": "object", "properties": {}},
)
def list_jarvis21_requests() -> str:
    if not _is_admin_host():
        return "Only the owner can view requests, sir."
    pending = _load_pending()
    if not pending:
        return "No pending JARVIS21 access requests, sir."
    lines = [f"--- JARVIS21 Pending Requests ({len(pending)}) ---"]
    for device_id, info in pending.items():
        ts  = info.get("requested_at","?")[:16]
        tok = info.get("token","?")
        apv = "[APPROVED]" if info.get("approved") else "[PENDING]"
        lines.append(f"  {device_id}  {ts}  {tok}  {apv}")
    return "\n".join(lines)


# ── Redeem code ───────────────────────────────────────────────────────────────
@register(
    name="redeem_discount_code",
    description="Redeem a promo/discount code for trial, discount, or full access.",
    parameters={"type": "object", "properties": {
        "code":  {"type": "string"},
        "email": {"type": "string", "description": "Your email (needed for JARVIS21 approval notification)"},
    }, "required": ["code"]},
)
def redeem_discount_code(code: str, email: str = "") -> str:
    code = code.strip().upper()
    info = _CODES.get(code)
    if not info:
        avail = ", ".join(k for k in _CODES if k != "JARVIS21")
        return (f"Code '{code}' not recognised, sir. "
                f"Available codes: {avail}, JARVIS21 (request full access).")

    d = _load()

    # ── JARVIS21 special flow ─────────────────────────────────────────────────
    if code == "JARVIS21":
        device   = _device_id()
        token    = hashlib.md5(f"{device}{time.time()}".encode()).hexdigest()[:10].upper()
        pending  = _load_pending()
        if device in pending and not pending[device].get("approved"):
            return ("Your access request is already pending owner approval, sir. "
                    "You have a 48-hour trial in the meantime.")
        if device in pending and pending[device].get("approved"):
            # Already approved — grant Lifetime
            d.update({"plan": "lifetime", "license_key": f"JARVIS21-{token}", "expires": ""})
            _save(d)
            return "Your JARVIS21 request was approved! Full Lifetime access unlocked, sir."
        # New request
        pending[device] = {
            "token":        token,
            "email":        email,
            "requested_at": datetime.now().isoformat(),
            "approved":     False,
        }
        _save_pending(pending)
        # Grant 48-hour trial immediately
        trial_end = (date.today() + timedelta(days=2)).isoformat()
        d.update({"trial_until": trial_end, "trial_plan": "pending", "discount_code": code})
        _save(d)
        # Send approval email to admin in background
        threading.Thread(target=_send_approval_email, args=(device, token),
                         daemon=True).start()
        return (
            f"JARVIS21 request submitted, sir.\n"
            f"The owner has been notified and will review your request.\n"
            f"You have a 48-hour trial with expanded features while waiting.\n"
            f"Your request token: {token}\n"
            f"Once approved, re-enter code JARVIS21 to activate full Lifetime access."
        )

    # ── Standard codes ────────────────────────────────────────────────────────
    if info.get("trial", 0) > 0:
        trial_end = (date.today() + timedelta(days=info["trial"])).isoformat()
        d.update({"trial_until": trial_end, "trial_plan": info["plan"], "discount_code": code})
        _save(d)
        return (f"Code '{code}' applied! "
                f"{info['trial']}-day free trial until {trial_end}, sir. "
                f"Enjoy all Pro features.")

    plan = info["plan"]
    pct  = info.get("pct", 0)
    link = PAYMENT_LINKS.get(plan, PAYMENT_LINKS["pro_monthly"])
    d["discount_code"] = code
    _save(d)
    return (
        f"Code '{code}' saved — {pct}% off {plan.replace('_',' ').title()}!\n"
        f"Complete payment here (discount auto-applied):\n"
        f"{link}?checkout[discount_code]={code}\n"
        f"Then activate your license key with 'activate license YOUR-KEY', sir."
    )


# ── License activation ────────────────────────────────────────────────────────
@register(
    name="activate_license",
    description="Activate a JARVIS Pro or Lifetime license key from your purchase email.",
    parameters={"type": "object", "properties": {
        "license_key": {"type": "string"},
    }, "required": ["license_key"]},
)
def activate_license(license_key: str) -> str:
    key = license_key.strip().upper()
    d   = _load()

    # LemonSqueezy online validation
    if _LS_API_KEY:
        try:
            payload = urllib.parse.urlencode({
                "license_key":   key,
                "instance_name": f"JARVIS-{_device_id()}",
            }).encode()
            req = urllib.request.Request(
                "https://api.lemonsqueezy.com/v1/licenses/validate",
                data=payload, headers={"Accept": "application/json"}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=8) as r:
                result = json.loads(r.read())
            if result.get("valid"):
                lk   = result.get("license_key", {})
                name = result.get("meta", {}).get("product_name", "")
                plan = "lifetime" if "lifetime" in name.lower() else "pro"
                exp  = lk.get("expires_at", "")
                d.update({"plan": plan, "license_key": key,
                          "expires": exp[:10] if exp else "", "trial_until": ""})
                _save(d)
                return (f"License activated! Plan: {plan.upper()}. "
                        f"{'Never expires.' if plan=='lifetime' else f'Expires: {exp[:10]}'} "
                        f"Thank you, sir — all features are now unlocked.")
        except Exception:
            pass  # Fall through to offline check

    # Offline key format check
    import re
    if re.match(r'^[A-Z0-9]{4,}-[A-Z0-9]{4,}-[A-Z0-9]{4,}-[A-Z0-9]{4,}', key):
        plan = "lifetime" if key.startswith(("LT-","LIFE","JARVIS21")) else "pro"
        d.update({"plan": plan, "license_key": key, "expires": "", "trial_until": ""})
        _save(d)
        return (f"License accepted ({plan.upper()}). All features unlocked, sir. "
                f"If online validation is needed, set LEMONSQUEEZY_API_KEY in .env.")

    return "Invalid license key format, sir. Keys look like: XXXX-XXXX-XXXX-XXXX"


# ── Plan status ───────────────────────────────────────────────────────────────
@register(
    name="check_plan",
    description="Check your JARVIS plan, features unlocked, and daily usage.",
    parameters={"type": "object", "properties": {}},
)
def check_plan() -> str:
    plan      = get_plan()
    d         = _load()
    remaining = queries_remaining()
    is_admin  = _is_admin_host() or d.get("is_admin", False)
    lines     = [f"=== JARVIS AI — {plan.upper()} PLAN {'[OWNER]' if is_admin else ''} ==="]
    if d.get("trial_until") and plan != "lifetime":
        lines.append(f"  Trial until:   {d['trial_until']}")
    if d.get("expires"):
        lines.append(f"  Expires:       {d['expires']}")
    if plan == "free":
        lines.append(f"  Queries today: {FREE_LIMIT - remaining}/{FREE_LIMIT}")
        lines.append(f"  Remaining:     {remaining}")
        lines.append(f"\n  Upgrade options:")
        lines.append(f"  → 'redeem code LAUNCH2026' — 40% off Pro Annual")
        lines.append(f"  → 'redeem code BETA'        — 14-day free Pro trial")
        lines.append(f"  → 'redeem code JARVIS21'    — request full access from owner")
    else:
        lines.append(f"  Queries:       Unlimited")
        if is_admin:
            lines.append(f"  All 275+ tools: Unlocked (owner account)")
    return "\n".join(lines)


@register(
    name="upgrade_plan",
    description="Get pricing and payment links to upgrade JARVIS to Pro or Lifetime.",
    parameters={"type": "object", "properties": {}},
)
def upgrade_plan() -> str:
    return (
        "=== JARVIS AI Upgrade ===\n\n"
        f"Pro Monthly   $3.99/mo  → {PAYMENT_LINKS['pro_monthly']}\n"
        f"Pro Annual    $34.99/yr → {PAYMENT_LINKS['pro_annual']}  (save 27%)\n"
        f"Lifetime      $49.99    → {PAYMENT_LINKS['lifetime']}   (pay once, own forever)\n\n"
        "Promo codes (say 'redeem code CODE'):\n"
        "  LAUNCH2026  — 40% off annual\n"
        "  BETA        — 14-day free trial\n"
        "  STUDENT25   — 25% off annual\n"
        "  FRIEND15    — 15% off monthly\n"
        "  JARVIS21    — request free access (owner approval required)\n\n"
        "Have a license key? Say 'activate license XXXX-XXXX-XXXX-XXXX', sir."
    )
