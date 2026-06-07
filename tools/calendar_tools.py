"""
Google Calendar integration — uses same OAuth2 token as Gmail.
Falls back to local event store if OAuth not configured.
"""
import json
import re
import time
from datetime import datetime, timedelta
from pathlib import Path

import config
from tools.registry import register

_LOCAL_CAL = config.MEMORY_DIR / "calendar.json"
_TOKEN     = config.MEMORY_DIR / "google_token.json"
_CREDS     = config.MEMORY_DIR / "google_credentials.json"
_SCOPES    = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _get_cal_service():
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
                creds = flow.run_local_server(port=0)
                _TOKEN.write_text(creds.to_json())
            else:
                return None
        return build("calendar", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        return None


def _load_local() -> list:
    if _LOCAL_CAL.exists():
        try:
            return json.loads(_LOCAL_CAL.read_text())
        except Exception:
            pass
    return []


def _save_local(events: list):
    config.MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    _LOCAL_CAL.write_text(json.dumps(events, indent=2))


def _parse_dt(text: str) -> str:
    """Parse human time like 'tomorrow 3pm', 'in 2 hours'. Returns ISO string."""
    now  = datetime.now()
    text = text.lower().strip()

    if "tomorrow" in text:
        base = now + timedelta(days=1)
    elif "next week" in text:
        base = now + timedelta(weeks=1)
    else:
        base = now

    # Extract time
    m = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
    if m:
        hr = int(m.group(1)); mn = int(m.group(2) or 0)
        if m.group(3) == 'pm' and hr != 12: hr += 12
        if m.group(3) == 'am' and hr == 12: hr = 0
        base = base.replace(hour=hr, minute=mn, second=0, microsecond=0)
    else:
        # Relative: "in 2 hours"
        h_match = re.search(r'in\s+(\d+)\s+hour', text)
        m_match = re.search(r'in\s+(\d+)\s+min',  text)
        if h_match: base = now + timedelta(hours=int(h_match.group(1)))
        if m_match: base = now + timedelta(minutes=int(m_match.group(1)))

    return base.isoformat()


@register(
    name="list_events",
    description="List upcoming calendar events (next 7 days by default).",
    parameters={
        "type": "object",
        "properties": {"days": {"type": "integer", "description": "Days ahead to look (default 7)"}},
    },
)
def list_events(days: int = 7) -> str:
    svc = _get_cal_service()
    if svc:
        try:
            now    = datetime.utcnow().isoformat() + "Z"
            end    = (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"
            result = svc.events().list(
                calendarId="primary", timeMin=now, timeMax=end,
                maxResults=15, singleEvents=True, orderBy="startTime",
            ).execute()
            evs = result.get("items", [])
            if not evs:
                return "No upcoming events, sir."
            lines = []
            for e in evs:
                start = e["start"].get("dateTime", e["start"].get("date", ""))
                try:
                    dt = datetime.fromisoformat(start.replace("Z",""))
                    ds = dt.strftime("%a %b %d, %H:%M")
                except Exception:
                    ds = start
                lines.append(f"• {e.get('summary','(no title)')}  —  {ds}")
            return "\n".join(lines)
        except Exception as e:
            return f"Calendar API error: {e}"

    # Local fallback
    evs = _load_local()
    now = time.time()
    upcoming = [e for e in evs if e.get("ts", 0) >= now][:10]
    if not upcoming:
        return "No upcoming events in local calendar, sir."
    return "\n".join(
        f"• {e['title']}  —  {datetime.fromtimestamp(e['ts']).strftime('%a %b %d %H:%M')}"
        for e in upcoming
    )


@register(
    name="create_event",
    description="Create a calendar event or meeting.",
    parameters={
        "type": "object",
        "properties": {
            "title":       {"type": "string"},
            "when":        {"type": "string", "description": "e.g. 'tomorrow 3pm', 'Monday 10am'"},
            "duration_min":{"type": "integer", "description": "Duration in minutes (default 60)"},
            "description": {"type": "string"},
            "location":    {"type": "string"},
        },
        "required": ["title", "when"],
    },
)
def create_event(title: str, when: str, duration_min: int = 60,
                 description: str = "", location: str = "") -> str:
    start_iso = _parse_dt(when)
    start_dt  = datetime.fromisoformat(start_iso)
    end_dt    = start_dt + timedelta(minutes=duration_min)

    svc = _get_cal_service()
    if svc:
        try:
            body = {
                "summary": title,
                "description": description,
                "location": location,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Kolkata"},
                "end":   {"dateTime": end_dt.isoformat(),   "timeZone": "Asia/Kolkata"},
            }
            e = svc.events().insert(calendarId="primary", body=body).execute()
            return (f"Event '{title}' created on Google Calendar for "
                    f"{start_dt.strftime('%a %b %d at %H:%M')}, sir.")
        except Exception as ex:
            return f"Calendar API error: {ex}"

    # Local fallback
    evs = _load_local()
    evs.append({"title": title, "ts": start_dt.timestamp(),
                "duration": duration_min, "description": description})
    evs.sort(key=lambda x: x["ts"])
    _save_local(evs)
    return (f"Event '{title}' saved locally for "
            f"{start_dt.strftime('%a %b %d at %H:%M')}, sir.")


@register(
    name="delete_event",
    description="Delete a calendar event by title.",
    parameters={
        "type": "object",
        "properties": {"title": {"type": "string"}},
        "required": ["title"],
    },
)
def delete_event(title: str) -> str:
    # Local only (Google API deletion requires event ID)
    evs = _load_local()
    q   = title.lower()
    before = len(evs)
    evs = [e for e in evs if q not in e.get("title","").lower()]
    _save_local(evs)
    removed = before - len(evs)
    return f"Removed {removed} event(s) matching '{title}', sir." if removed else f"No event found matching '{title}', sir."


@register(
    name="find_free_time",
    description="Find free time slots in the next few days.",
    parameters={
        "type": "object",
        "properties": {
            "duration_min": {"type": "integer", "description": "How long a slot you need (minutes)"},
            "days":         {"type": "integer",  "description": "How many days to look ahead"},
        },
    },
)
def find_free_time(duration_min: int = 60, days: int = 3) -> str:
    # Simple: show times outside of existing events
    evs_text = list_events(days)
    from brain.core import get_brain
    prompt = (
        f"Given these events:\n{evs_text}\n\n"
        f"Find {duration_min}-minute free slots in the next {days} days during working hours "
        f"(9am–7pm). List 3 options."
    )
    return get_brain().quick(prompt, max_tokens=200)
