"""
Simple single-user auth: bcrypt password + JWT sessions.
Any device on the network can log in with the same password.
"""
import json
import time
from pathlib import Path

import bcrypt
import jwt

import config

_AUTH_FILE  = config.MEMORY_DIR / "auth.json"
_SECRET     = None  # lazy-loaded JWT secret
_ALGO       = "HS256"
_TTL        = 60 * 60 * 24 * 30   # 30 days


def _get_secret() -> str:
    global _SECRET
    if _SECRET:
        return _SECRET
    sec_file = config.MEMORY_DIR / ".jwt_secret"
    if sec_file.exists():
        _SECRET = sec_file.read_text().strip()
    else:
        import secrets
        _SECRET = secrets.token_hex(32)
        config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
        sec_file.write_text(_SECRET)
    return _SECRET


def _load() -> dict:
    if _AUTH_FILE.exists():
        try:
            return json.loads(_AUTH_FILE.read_text())
        except Exception:
            pass
    return {}


def _save(data: dict):
    config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    _AUTH_FILE.write_text(json.dumps(data, indent=2))


# ── Public API ────────────────────────────────────────────────────────────────

def is_setup_done() -> bool:
    d = _load()
    return bool(d.get("password_hash"))


def setup(name: str, password: str, phone: str = "", email: str = "") -> str:
    """Called once during setup wizard."""
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    _save({
        "name": name,
        "phone": phone,
        "email": email,
        "password_hash": pw_hash,
        "setup_ts": time.time(),
    })
    return _make_token()


def login(password: str) -> str | None:
    """Returns JWT token if password correct, else None."""
    d = _load()
    if not d.get("password_hash"):
        return None
    ok = bcrypt.checkpw(password.encode(), d["password_hash"].encode())
    return _make_token() if ok else None


def verify_token(token: str) -> bool:
    try:
        jwt.decode(token, _get_secret(), algorithms=[_ALGO])
        return True
    except Exception:
        return False


def get_user_info() -> dict:
    d = _load()
    return {k: v for k, v in d.items() if k != "password_hash"}


def _make_token() -> str:
    payload = {"iat": time.time(), "exp": time.time() + _TTL}
    return jwt.encode(payload, _get_secret(), algorithm=_ALGO)
