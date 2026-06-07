"""
Import contacts from Windows Phone Link (Your Phone app) or system Contacts.
Falls back through multiple sources until it finds data.
"""
import json
import os
import sqlite3
from pathlib import Path

import config
from tools.registry import register

_CONTACTS_FILE = config.MEMORY_DIR / "contacts.json"

# Phone Link stores data under the YourPhone package LocalState
_PHONE_LINK_ROOTS = [
    Path(os.environ.get("LOCALAPPDATA", "")) /
        "Packages" / "Microsoft.YourPhone_8wekyb3d8bbwe" / "LocalState",
    Path(os.environ.get("LOCALAPPDATA", "")) /
        "Packages" / "MicrosoftCorporationII.YourPhone_8wekyb3d8bbwe" / "LocalState",
]

def _load_existing() -> dict:
    if _CONTACTS_FILE.exists():
        try:
            return json.loads(_CONTACTS_FILE.read_text())
        except Exception:
            pass
    return {}

def _save(contacts: dict):
    config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    _CONTACTS_FILE.write_text(json.dumps(contacts, indent=2))

def _find_phone_link_db() -> Path | None:
    """Search common Phone Link database locations."""
    for root in _PHONE_LINK_ROOTS:
        if not root.exists():
            continue
        # Try known filenames
        for name in ("ContactStore.db", "contacts_db", "contacts.db",
                     "phone_contacts.db", "YourPhoneContacts.db"):
            p = root / name
            if p.exists():
                return p
        # Glob for any .db file
        dbs = list(root.glob("*.db"))
        for db in dbs:
            if "contact" in db.name.lower():
                return db
        # Return first .db found
        if dbs:
            return dbs[0]
    return None

def _read_db(db_path: Path) -> list[dict]:
    """Try to extract contacts from a SQLite database."""
    contacts = []
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        # Discover tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0].lower() for r in cursor.fetchall()]

        # Look for contacts table
        for t in tables:
            if "contact" not in t:
                continue
            try:
                cursor.execute(f"PRAGMA table_info({t})")
                cols = [r[1].lower() for r in cursor.fetchall()]
                # Find name and phone columns
                name_col  = next((c for c in cols if "name" in c and "display" in c), None) or \
                            next((c for c in cols if "name" in c), None)
                phone_col = next((c for c in cols if "phone" in c or "number" in c), None)
                if name_col and phone_col:
                    cursor.execute(f"SELECT {name_col}, {phone_col} FROM {t} LIMIT 500")
                    for row in cursor.fetchall():
                        if row[0] and row[1]:
                            contacts.append({"name": str(row[0]), "phone": str(row[1])})
            except Exception:
                continue
        conn.close()
    except Exception:
        pass
    return contacts

def _read_windows_contacts() -> list[dict]:
    """Read .contact files from Windows Contacts folder."""
    contacts = []
    folder = Path.home() / "Contacts"
    if not folder.exists():
        return []
    import xml.etree.ElementTree as ET
    for cf in folder.glob("*.contact"):
        try:
            tree = ET.parse(str(cf))
            root = tree.getroot()
            ns = {"c": "http://schemas.microsoft.com/Contact"}
            # Try to get display name
            fn  = root.find(".//c:FormattedName/c:Value", ns)
            ph  = root.find(".//c:Phone/c:Number",        ns)
            em  = root.find(".//c:Email/c:Address",       ns)
            name = fn.text.strip() if fn is not None else cf.stem
            phone = ph.text.strip() if ph is not None else ""
            email = em.text.strip() if em is not None else ""
            if name:
                contacts.append({"name": name, "phone": phone, "email": email})
        except Exception:
            continue
    return contacts

@register(
    name="import_phone_contacts",
    description="Import contacts from Windows Phone Link or system Contacts folder.",
    parameters={"type": "object", "properties": {}},
)
def import_from_phone_link() -> str:
    imported = []

    # 1. Try Phone Link SQLite
    db = _find_phone_link_db()
    if db:
        imported = _read_db(db)
        source = f"Phone Link ({db.name})"

    # 2. Fallback: Windows Contacts folder
    if not imported:
        imported = _read_windows_contacts()
        source = "Windows Contacts folder"

    if not imported:
        # Open Phone Link app so user can sync
        try:
            import subprocess
            subprocess.Popen(["explorer", "ms-yourphone:"], shell=True)
        except Exception:
            pass
        return (
            "No Phone Link contacts found, sir.\n"
            "I've opened the Phone Link app — sync your contacts there, "
            "then say 'import contacts' again."
        )

    # Merge with existing contacts
    existing = _load_existing()
    new_count = 0
    for c in imported:
        key = c["name"].lower().replace(" ", "_")
        if key not in existing:
            existing[key] = c
            new_count += 1
        else:
            # Update phone if changed
            if c.get("phone") and not existing[key].get("phone"):
                existing[key]["phone"] = c["phone"]

    _save(existing)
    return (
        f"Imported {new_count} new contacts from {source}, sir. "
        f"Total contacts: {len(existing)}."
    )
