"""
Encrypted local password vault — tied to this device, no master password needed.
Encrypts with Fernet (cryptography library) if available, XOR otherwise.
"""
import difflib
import hashlib
import json
import os
import secrets
from pathlib import Path

import config
from tools.registry import register

_KEY_FILE  = config.MEMORY_DIR / ".vault_key"
_VAULT_FILE = config.MEMORY_DIR / "vault.enc"
_key: bytes = None


def _get_key() -> bytes:
    global _key
    if _key:
        return _key
    config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    if _KEY_FILE.exists():
        _key = bytes.fromhex(_KEY_FILE.read_text().strip())
    else:
        import socket
        # Combine machine identity + random salt for device-bound key
        salt = secrets.token_hex(24)
        seed = f"{socket.gethostname()}{os.getenv('COMPUTERNAME','')}{os.getenv('USERNAME','')}{salt}"
        _key = hashlib.sha256(seed.encode()).digest()
        _KEY_FILE.write_text(_key.hex())
    return _key


def _encrypt(plaintext: str) -> bytes:
    try:
        from cryptography.fernet import Fernet
        import base64
        key_b64 = base64.urlsafe_b64encode(_get_key())
        return Fernet(key_b64).encrypt(plaintext.encode())
    except ImportError:
        # XOR fallback (obfuscation only)
        key = _get_key()
        b = plaintext.encode()
        return bytes(b[i] ^ key[i % len(key)] for i in range(len(b)))


def _decrypt(data: bytes) -> str:
    try:
        from cryptography.fernet import Fernet
        import base64
        key_b64 = base64.urlsafe_b64encode(_get_key())
        return Fernet(key_b64).decrypt(data).decode()
    except ImportError:
        key = _get_key()
        return bytes(data[i] ^ key[i % len(key)] for i in range(len(data))).decode()


def _load() -> dict:
    if not _VAULT_FILE.exists():
        return {}
    try:
        raw = _VAULT_FILE.read_bytes()
        return json.loads(_decrypt(raw))
    except Exception:
        return {}


def _save(vault: dict):
    config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    _VAULT_FILE.write_bytes(_encrypt(json.dumps(vault)))


def _fuzzy_key(query: str, vault: dict) -> str | None:
    """Return best matching key from vault, or None."""
    q = query.lower()
    if q in vault:
        return q
    matches = difflib.get_close_matches(q, vault.keys(), n=1, cutoff=0.55)
    return matches[0] if matches else None


# ── Tools ─────────────────────────────────────────────────────────────────────

@register(
    name="store_password",
    description="Store a password, username or any credential in the encrypted local vault.",
    parameters={
        "type": "object",
        "properties": {
            "site":     {"type": "string", "description": "Website/service name"},
            "username": {"type": "string", "description": "Username or email"},
            "password": {"type": "string", "description": "Password or secret"},
            "notes":    {"type": "string", "description": "Optional extra notes"},
        },
        "required": ["site"],
    },
)
def store_password(site: str, username: str = "", password: str = "", notes: str = "") -> str:
    vault = _load()
    vault[site.lower()] = {
        "site": site, "username": username,
        "password": password, "notes": notes,
    }
    _save(vault)
    return f"Credentials for '{site}' stored securely in the vault, sir."


@register(
    name="get_password",
    description="Retrieve a stored password or credential from the vault.",
    parameters={
        "type": "object",
        "properties": {"site": {"type": "string"}},
        "required": ["site"],
    },
)
def get_password(site: str) -> str:
    vault = _load()
    key = _fuzzy_key(site, vault)
    if not key:
        return f"No credential found for '{site}', sir."
    e = vault[key]
    parts = [f"Site: {e['site']}"]
    if e.get("username"): parts.append(f"Username: {e['username']}")
    if e.get("password"): parts.append(f"Password: {e['password']}")
    if e.get("notes"):    parts.append(f"Notes: {e['notes']}")
    return "\n".join(parts)


@register(
    name="list_passwords",
    description="List all sites/services with stored passwords in the vault.",
    parameters={"type": "object", "properties": {}},
)
def list_passwords() -> str:
    vault = _load()
    if not vault:
        return "The vault is empty, sir."
    lines = [f"• {v['site']}" + (f"  ({v['username']})" if v.get('username') else "")
             for v in vault.values()]
    return f"Vault contains {len(vault)} entries:\n" + "\n".join(lines)


@register(
    name="delete_password",
    description="Remove a stored credential from the vault.",
    parameters={
        "type": "object",
        "properties": {"site": {"type": "string"}},
        "required": ["site"],
    },
)
def delete_password(site: str) -> str:
    vault = _load()
    key = _fuzzy_key(site, vault)
    if not key:
        return f"No entry found for '{site}', sir."
    removed = vault.pop(key)
    _save(vault)
    return f"Credentials for '{removed['site']}' deleted from vault, sir."


@register(
    name="update_password",
    description="Update the password or username for an existing vault entry.",
    parameters={
        "type": "object",
        "properties": {
            "site":     {"type": "string"},
            "username": {"type": "string"},
            "password": {"type": "string"},
            "notes":    {"type": "string"},
        },
        "required": ["site"],
    },
)
def update_password(site: str, username: str = None, password: str = None, notes: str = None) -> str:
    vault = _load()
    key = _fuzzy_key(site, vault)
    if not key:
        return f"No entry for '{site}' found. Use store_password to add it, sir."
    if username is not None: vault[key]["username"] = username
    if password is not None: vault[key]["password"] = password
    if notes    is not None: vault[key]["notes"]    = notes
    _save(vault)
    return f"Credentials for '{vault[key]['site']}' updated, sir."
