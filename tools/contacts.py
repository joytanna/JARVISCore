import difflib, json, os, subprocess, sys
from pathlib import Path

import config
from tools.registry import register

_FILE = config.MEMORY_DIR / "contacts.json"


def _load() -> dict:
    if _FILE.exists():
        try:
            return json.loads(_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(contacts: dict):
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(contacts, indent=2, ensure_ascii=False), encoding="utf-8")


def _fuzzy(name: str, contacts: dict) -> str | None:
    """Return best-matching contact name, or None."""
    keys = list(contacts.keys())
    matches = difflib.get_close_matches(name.lower(),
                                        [k.lower() for k in keys],
                                        n=1, cutoff=0.5)
    if not matches:
        return None
    idx = [k.lower() for k in keys].index(matches[0])
    return keys[idx]


@register(
    name="add_contact",
    description="Save a contact with name, phone number, and optional email",
    parameters={
        "type": "object",
        "properties": {
            "name":  {"type": "string"},
            "phone": {"type": "string", "description": "Phone number with country code e.g. +917666639083"},
            "email": {"type": "string"},
        },
        "required": ["name", "phone"],
    },
)
def add_contact(name: str, phone: str, email: str = None) -> str:
    contacts = _load()
    contacts[name] = {"phone": phone, "email": email}
    _save(contacts)
    return f"Contact saved: {name} — {phone}"


@register(
    name="find_contact",
    description="Look up a contact by name",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def find_contact(name: str) -> str:
    contacts = _load()
    key = _fuzzy(name, contacts)
    if not key:
        return f"No contact found matching '{name}'."
    c = contacts[key]
    parts = [f"{key}: {c['phone']}"]
    if c.get("email"):
        parts.append(c["email"])
    return " | ".join(parts)


@register(
    name="list_contacts",
    description="List all saved contacts",
    parameters={"type": "object", "properties": {}},
)
def list_contacts() -> str:
    contacts = _load()
    if not contacts:
        return "No contacts saved yet."
    lines = [f"{n}: {d['phone']}" + (f" | {d['email']}" if d.get("email") else "")
             for n, d in contacts.items()]
    return "\n".join(lines)


@register(
    name="call_contact",
    description="Call a contact by name using the system's default calling app (Phone Link, Skype, etc.)",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def call_contact(name: str) -> str:
    contacts = _load()
    key = _fuzzy(name, contacts)
    if not key:
        return f"No contact found matching '{name}'. Add them first with add_contact."
    phone = contacts[key]["phone"]
    # Normalise — strip spaces/dashes for tel: URI
    clean = "".join(c for c in phone if c in "+0123456789")
    try:
        os.startfile(f"tel:{clean}")
        return f"Calling {key} ({clean}) via system dialer."
    except Exception:
        pass
    try:
        subprocess.Popen(f'start "" "tel:{clean}"', shell=True)
        return f"Calling {key} ({clean})."
    except Exception as e:
        return f"Could not open dialer: {e}. Number: {clean}"


@register(
    name="delete_contact",
    description="Remove a contact by name",
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
def delete_contact(name: str) -> str:
    contacts = _load()
    key = _fuzzy(name, contacts)
    if not key:
        return f"No contact found matching '{name}'."
    del contacts[key]
    _save(contacts)
    return f"Deleted contact: {key}"
