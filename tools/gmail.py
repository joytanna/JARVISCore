"""
Gmail integration — OAuth2 (no App Password) + IMAP/SMTP fallback.

══ OAuth2 setup (one-time, ~5 min) ══════════════════════════════
1. Go to https://console.cloud.google.com
2. Create a project (any name) → Enable Gmail API
3. Credentials → Create OAuth 2.0 Client ID → Desktop application
4. Download JSON → save as:
       C:\\JARVISCore\\memory\\google_credentials.json
5. Say "connect my Google account" — browser opens, you click Allow.
   Done. Token saved forever, refreshed automatically.
═════════════════════════════════════════════════════════════════
"""
import base64
import email
import imaplib
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import config
from tools.registry import register

_ADDR  = getattr(config, "GMAIL_ADDRESS", "")
_PASS  = getattr(config, "GMAIL_APP_PASSWORD", "")

_CREDS = config.MEMORY_DIR / "google_credentials.json"
_TOKEN = config.MEMORY_DIR / "google_token.json"

_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.compose",
    "https://www.googleapis.com/auth/gmail.readonly",
]

_svc_cache = None


# ── OAuth2 helpers ────────────────────────────────────────────────────────────

def _get_service(force_refresh: bool = False):
    """Return authenticated Gmail API service, or None if not available."""
    global _svc_cache
    if _svc_cache and not force_refresh:
        return _svc_cache
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        creds = None
        if _TOKEN.exists():
            creds = Credentials.from_authorized_user_file(str(_TOKEN), _SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                _TOKEN.write_text(creds.to_json())
            elif _CREDS.exists():
                flow = InstalledAppFlow.from_client_secrets_file(str(_CREDS), _SCOPES)
                creds = flow.run_local_server(port=0, open_browser=True)
                config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
                _TOKEN.write_text(creds.to_json())
            else:
                return None   # No credentials yet

        _svc_cache = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return _svc_cache
    except ImportError:
        return None
    except Exception as e:
        print(f"[Gmail OAuth] {e}")
        return None


def _oauth_ready() -> bool:
    return _TOKEN.exists() or _CREDS.exists()


def _imap():
    ctx = ssl.create_default_context()
    conn = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ctx)
    conn.login(_ADDR, _PASS)
    return conn


def _decode_part(part) -> str:
    raw = part.get_payload(decode=True)
    if not raw:
        return ""
    for enc in ("utf-8", "latin-1", "ascii"):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return ""


# ── Tools ─────────────────────────────────────────────────────────────────────

@register(
    name="setup_google_auth",
    description="Set up Google account OAuth2 so JARVIS can access Gmail without an App Password.",
    parameters={"type": "object", "properties": {}},
)
def setup_google_auth() -> str:
    if _TOKEN.exists():
        return "Google account is already connected via OAuth2, sir."
    if not _CREDS.exists():
        import webbrowser
        webbrowser.open("https://console.cloud.google.com/apis/credentials")
        return (
            f"I've opened Google Cloud Console, sir.\n\n"
            f"Steps:\n"
            f"1. Create a project → Enable Gmail API\n"
            f"2. Credentials → Create OAuth 2.0 Client ID → Desktop application\n"
            f"3. Download JSON → save as:\n"
            f"   {_CREDS}\n"
            f"4. Say 'connect Google account' again to complete."
        )
    svc = _get_service(force_refresh=True)
    if svc:
        return "Google account connected via OAuth2, sir. No password required going forward."
    return "OAuth2 setup failed. Ensure credentials.json is valid and try again, sir."


@register(
    name="read_emails",
    description="Read recent emails from Gmail inbox.",
    parameters={
        "type": "object",
        "properties": {
            "n":      {"type": "integer", "description": "Number of emails (default 5)"},
            "unread": {"type": "boolean", "description": "If true, show only unread emails"},
        },
    },
)
def read_emails(n: int = 5, unread: bool = False) -> str:
    # App-password IMAP is the primary path — no OAuth needed
    if _ADDR and _PASS:
        return _imap_read(n, unread)
    # OAuth fallback (requires setup_google_auth)
    svc = _get_service()
    if svc:
        return _api_read(svc, n, unread)
    return ("Gmail not configured, sir. "
            "Add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to .env, "
            "or say 'connect Google account' for OAuth.")


def _api_read(svc, n: int, unread: bool) -> str:
    try:
        query = "is:unread" if unread else ""
        res = svc.users().messages().list(
            userId="me", maxResults=n, labelIds=["INBOX"], q=query
        ).execute()
        msgs = res.get("messages", [])
        if not msgs:
            return "Inbox is empty, sir." if not unread else "No unread emails, sir."
        out = []
        for m in msgs:
            msg = svc.users().messages().get(
                userId="me", id=m["id"], format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            h = {x["name"]: x["value"] for x in msg["payload"]["headers"]}
            snippet = msg.get("snippet", "")[:220]
            out.append(
                f"From: {h.get('From','?')}\n"
                f"Subject: {h.get('Subject','(no subject)')}\n"
                f"{snippet}"
            )
        return "\n---\n".join(out)
    except Exception as e:
        return f"Gmail API error: {e}"


def _imap_read(n: int, unread: bool) -> str:
    try:
        conn = _imap()
        conn.select("INBOX")
        criteria = "UNSEEN" if unread else "ALL"
        _, ids = conn.search(None, criteria)
        id_list = ids[0].split()
        recent = id_list[-n:] if len(id_list) >= n else id_list
        results = []
        for eid in reversed(recent):
            _, data = conn.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            subj = msg.get("Subject", "(no subject)")
            frm  = msg.get("From", "?")
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = _decode_part(part)[:300]
                        break
            else:
                body = _decode_part(msg)[:300]
            results.append(f"From: {frm}\nSubject: {subj}\n{body.strip()}")
        conn.logout()
        return "\n---\n".join(results) if results else "No emails found, sir."
    except Exception as e:
        return f"Gmail IMAP error: {e}"


@register(
    name="send_email",
    description="Send an email via Gmail.",
    parameters={
        "type": "object",
        "properties": {
            "to":      {"type": "string"},
            "subject": {"type": "string"},
            "body":    {"type": "string"},
        },
        "required": ["to", "subject", "body"],
    },
)
def send_email(to: str, subject: str, body: str) -> str:
    # App-password SMTP is the primary path
    if _ADDR and _PASS:
        return _smtp_send(to, subject, body)
    # OAuth fallback
    svc = _get_service()
    if svc:
        return _api_send(svc, to, subject, body)
    return ("Gmail not configured, sir. "
            "Add GMAIL_ADDRESS and GMAIL_APP_PASSWORD to .env.")


def _api_send(svc, to: str, subject: str, body: str) -> str:
    try:
        msg = MIMEMultipart()
        msg["to"]      = to
        msg["from"]    = _ADDR
        msg["subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()
        return f"Email sent to {to}, sir."
    except Exception as e:
        return f"Send error: {e}"


def _smtp_send(to: str, subject: str, body: str) -> str:
    try:
        msg = MIMEMultipart()
        msg["From"]    = _ADDR
        msg["To"]      = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ctx) as srv:
            srv.login(_ADDR, _PASS)
            srv.sendmail(_ADDR, to, msg.as_string())
        return f"Email sent to {to}, sir."
    except Exception as e:
        return f"SMTP error: {e}"


@register(
    name="search_emails",
    description="Search Gmail inbox for emails matching a keyword, sender, or subject.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)
def search_emails(query: str) -> str:
    # IMAP search first (app password)
    if _ADDR and _PASS:
        try:
            conn = _imap()
            conn.select("INBOX")
            _, ids = conn.search(None, f'SUBJECT "{query}"')
            id_list = ids[0].split()
            if not id_list:
                _, ids = conn.search(None, f'TEXT "{query}"')
                id_list = ids[0].split()
            recent = id_list[-5:]
            results = []
            for eid in reversed(recent):
                _, data = conn.fetch(eid, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])
                results.append(
                    f"From: {msg.get('From','?')}  |  Subject: {msg.get('Subject','?')}"
                )
            conn.logout()
            return "\n".join(results) if results else f"No emails matching '{query}', sir."
        except Exception as e:
            return f"Gmail search error: {e}"
    svc = _get_service()
    if svc:
        try:
            res = svc.users().messages().list(
                userId="me", q=query, maxResults=5
            ).execute()
            msgs = res.get("messages", [])
            if not msgs:
                return f"No emails matching '{query}', sir."
            out = []
            for m in msgs:
                msg = svc.users().messages().get(
                    userId="me", id=m["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"],
                ).execute()
                h = {x["name"]: x["value"] for x in msg["payload"]["headers"]}
                out.append(
                    f"From: {h.get('From','?')}  |  "
                    f"Subject: {h.get('Subject','?')}  |  "
                    f"Date: {h.get('Date','?')}"
                )
            return "\n".join(out)
        except Exception as e:
            return f"Search error: {e}"

    return "Gmail not configured, sir."
    # dead code below — kept for reference
    try:
        conn = _imap()
        conn.select("INBOX")
        _, ids = conn.search(None, f'SUBJECT "{query}"')
        id_list = ids[0].split()
        if not id_list:
            _, ids = conn.search(None, f'TEXT "{query}"')
            id_list = ids[0].split()
        recent = id_list[-5:]
        results = []
        for eid in reversed(recent):
            _, data = conn.fetch(eid, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            results.append(
                f"From: {msg.get('From','?')}  |  Subject: {msg.get('Subject','?')}"
            )
        conn.logout()
        return "\n".join(results) if results else f"No emails matching '{query}', sir."
    except Exception as e:
        return f"Gmail search error: {e}"


@register(
    name="gmail_status",
    description="Check Gmail connection status and unread count.",
    parameters={"type": "object", "properties": {}},
)
def gmail_status() -> str:
    svc = _get_service()
    if svc:
        try:
            res = svc.users().messages().list(
                userId="me", labelIds=["INBOX", "UNREAD"], maxResults=1
            ).execute()
            count = res.get("resultSizeEstimate", 0)
            return f"Gmail connected via OAuth2. Approximately {count} unread messages, sir."
        except Exception as e:
            return f"Gmail API connected but status check failed: {e}"
    if _ADDR and _PASS:
        return "Gmail configured with App Password. OAuth2 not yet set up, sir."
    return "Gmail not configured. Say 'connect Google account' to set up OAuth2, sir."
