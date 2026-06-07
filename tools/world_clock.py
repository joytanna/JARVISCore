"""
World Clock & Timezone Tools — no extra dependencies.
Uses Python 3.9+ zoneinfo (stdlib). Falls back to UTC offset map for older Python.
"""
from datetime import datetime, timezone, timedelta
from tools.registry import register

# ── Timezone alias map ────────────────────────────────────────────────────────
# City / country → IANA timezone identifier
_ALIASES: dict = {
    # India
    "india": "Asia/Kolkata", "ist": "Asia/Kolkata", "mumbai": "Asia/Kolkata",
    "delhi": "Asia/Kolkata", "bangalore": "Asia/Kolkata", "kolkata": "Asia/Kolkata",
    "chennai": "Asia/Kolkata", "hyderabad": "Asia/Kolkata",
    # US
    "new york": "America/New_York", "ny": "America/New_York", "nyc": "America/New_York",
    "est": "America/New_York", "eastern": "America/New_York",
    "los angeles": "America/Los_Angeles", "la": "America/Los_Angeles", "pst": "America/Los_Angeles",
    "pacific": "America/Los_Angeles", "san francisco": "America/Los_Angeles",
    "chicago": "America/Chicago", "cst": "America/Chicago", "central": "America/Chicago",
    "denver": "America/Denver", "mst": "America/Denver",
    # Europe
    "london": "Europe/London", "gmt": "Europe/London", "uk": "Europe/London",
    "paris": "Europe/Paris", "cet": "Europe/Paris", "france": "Europe/Paris",
    "berlin": "Europe/Berlin", "germany": "Europe/Berlin",
    "amsterdam": "Europe/Amsterdam", "netherlands": "Europe/Amsterdam",
    "moscow": "Europe/Moscow", "russia": "Europe/Moscow",
    "rome": "Europe/Rome", "italy": "Europe/Rome",
    "madrid": "Europe/Madrid", "spain": "Europe/Madrid",
    "istanbul": "Europe/Istanbul", "turkey": "Europe/Istanbul",
    # Asia
    "tokyo": "Asia/Tokyo", "japan": "Asia/Tokyo", "jst": "Asia/Tokyo",
    "beijing": "Asia/Shanghai", "shanghai": "Asia/Shanghai", "china": "Asia/Shanghai",
    "cst china": "Asia/Shanghai",
    "singapore": "Asia/Singapore", "sgt": "Asia/Singapore",
    "dubai": "Asia/Dubai", "uae": "Asia/Dubai",
    "hong kong": "Asia/Hong_Kong", "hk": "Asia/Hong_Kong",
    "seoul": "Asia/Seoul", "korea": "Asia/Seoul",
    "bangkok": "Asia/Bangkok", "thailand": "Asia/Bangkok",
    "karachi": "Asia/Karachi", "pakistan": "Asia/Karachi", "pkt": "Asia/Karachi",
    "dhaka": "Asia/Dhaka", "bangladesh": "Asia/Dhaka",
    "kathmandu": "Asia/Kathmandu", "nepal": "Asia/Kathmandu",
    "colombo": "Asia/Colombo", "sri lanka": "Asia/Colombo",
    # Australia / Pacific
    "sydney": "Australia/Sydney", "australia": "Australia/Sydney", "aest": "Australia/Sydney",
    "melbourne": "Australia/Melbourne",
    "perth": "Australia/Perth",
    "auckland": "Pacific/Auckland", "new zealand": "Pacific/Auckland", "nzt": "Pacific/Auckland",
    # Americas
    "toronto": "America/Toronto", "canada": "America/Toronto",
    "vancouver": "America/Vancouver",
    "sao paulo": "America/Sao_Paulo", "brazil": "America/Sao_Paulo",
    "mexico city": "America/Mexico_City", "mexico": "America/Mexico_City",
    "buenos aires": "America/Argentina/Buenos_Aires", "argentina": "America/Argentina/Buenos_Aires",
    # Africa
    "cairo": "Africa/Cairo", "egypt": "Africa/Cairo",
    "johannesburg": "Africa/Johannesburg", "south africa": "Africa/Johannesburg",
    "nairobi": "Africa/Nairobi", "kenya": "Africa/Nairobi",
    "lagos": "Africa/Lagos", "nigeria": "Africa/Lagos",
    # UTC / Special
    "utc": "UTC", "gmt0": "UTC",
}

# Fallback UTC offsets (hours) when zoneinfo not available
_UTC_OFFSETS: dict = {
    "Asia/Kolkata": 5.5, "Asia/Tokyo": 9, "Asia/Shanghai": 8,
    "Asia/Singapore": 8, "Asia/Dubai": 4, "Asia/Hong_Kong": 8,
    "Asia/Seoul": 9, "Asia/Bangkok": 7, "Asia/Karachi": 5,
    "Asia/Dhaka": 6, "Asia/Kathmandu": 5.75, "Asia/Colombo": 5.5,
    "Europe/London": 0, "Europe/Paris": 1, "Europe/Berlin": 1,
    "Europe/Moscow": 3, "Europe/Istanbul": 3,
    "America/New_York": -5, "America/Los_Angeles": -8,
    "America/Chicago": -6, "America/Denver": -7,
    "Australia/Sydney": 10, "Australia/Perth": 8,
    "Pacific/Auckland": 12, "UTC": 0,
    "Africa/Cairo": 2, "Africa/Johannesburg": 2, "Africa/Nairobi": 3,
}


def _resolve_tz(name: str):
    """Return a datetime.timezone or zoneinfo.ZoneInfo for the given name."""
    key = name.lower().strip()
    iana = _ALIASES.get(key, key)  # use alias or treat as IANA directly
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(iana), iana
    except ImportError:
        pass
    except Exception:
        pass
    # fallback: use UTC offset map
    offset_h = _UTC_OFFSETS.get(iana)
    if offset_h is None:
        return None, iana
    return timezone(timedelta(hours=offset_h)), iana


def _fmt(dt: datetime) -> str:
    return dt.strftime("%I:%M %p, %a %d %b %Y")


# ── What time is it? ──────────────────────────────────────────────────────────
@register(
    name="world_time",
    description="Get the current time in any city or timezone worldwide.",
    parameters={"type": "object", "properties": {
        "location": {"type": "string",
                     "description": "City, country, or timezone e.g. 'Tokyo', 'India', 'UTC'"},
    }, "required": ["location"]},
)
def world_time(location: str) -> str:
    tz, iana = _resolve_tz(location)
    if tz is None:
        avail = ", ".join(sorted(set(_ALIASES.keys()))[:20])
        return (f"Unknown timezone '{location}', sir. "
                f"Try a city name. Examples: {avail}…")
    now = datetime.now(tz)
    return f"It's {_fmt(now)} in {location.title()} ({iana}), sir."


# ── Multiple cities at once ───────────────────────────────────────────────────
@register(
    name="world_clock",
    description="Show current time across multiple cities simultaneously.",
    parameters={"type": "object", "properties": {
        "cities": {"type": "string",
                   "description": "Comma-separated list of cities, e.g. 'London, Tokyo, New York, India'"},
    }, "required": ["cities"]},
)
def world_clock(cities: str) -> str:
    city_list = [c.strip() for c in cities.split(",") if c.strip()]
    if not city_list:
        # Default useful world clock
        city_list = ["India", "London", "New York", "Tokyo", "Sydney", "Dubai"]
    lines = [f"--- World Clock ({datetime.utcnow().strftime('%Y-%m-%d')} UTC) ---"]
    for city in city_list:
        tz, iana = _resolve_tz(city)
        if tz is None:
            lines.append(f"  {city:18} — unknown timezone")
            continue
        now = datetime.now(tz)
        lines.append(f"  {city.title():18} {now.strftime('%I:%M %p'):>10}  ({now.strftime('%a')})")
    return "\n".join(lines)


# ── Time zone converter ───────────────────────────────────────────────────────
@register(
    name="convert_timezone",
    description="Convert a specific time from one timezone to another.",
    parameters={"type": "object", "properties": {
        "time":      {"type": "string",  "description": "Time to convert, e.g. '3:30 PM' or '15:30'"},
        "from_tz":   {"type": "string",  "description": "Source timezone or city"},
        "to_tz":     {"type": "string",  "description": "Target timezone or city"},
    }, "required": ["time", "from_tz", "to_tz"]},
)
def convert_timezone(time: str, from_tz: str, to_tz: str) -> str:
    from_zone, from_iana = _resolve_tz(from_tz)
    to_zone,   to_iana   = _resolve_tz(to_tz)
    if from_zone is None:
        return f"Unknown timezone '{from_tz}', sir."
    if to_zone is None:
        return f"Unknown timezone '{to_tz}', sir."
    # Parse time string
    today = datetime.now(from_zone).date()
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M", "%I %p", "%H"):
        try:
            t = datetime.strptime(time.upper().strip(), fmt)
            dt_from = datetime(today.year, today.month, today.day,
                               t.hour, t.minute, tzinfo=from_zone)
            dt_to = dt_from.astimezone(to_zone)
            diff  = int((dt_to.utcoffset() - dt_from.utcoffset()).total_seconds() / 3600)
            diff_str = (f"+{diff}h" if diff > 0 else f"{diff}h") if diff != 0 else "same offset"
            return (f"{time} in {from_tz.title()} = "
                    f"{dt_to.strftime('%I:%M %p')} in {to_tz.title()} "
                    f"({diff_str}), sir.")
        except ValueError:
            continue
    return f"Couldn't parse time '{time}'. Try '3:30 PM' or '15:30', sir."


# ── How long until event? ─────────────────────────────────────────────────────
@register(
    name="time_until_city",
    description="How many hours until midnight (or a given hour) in another timezone — useful for deadlines.",
    parameters={"type": "object", "properties": {
        "city":        {"type": "string",  "description": "Target city/timezone"},
        "target_hour": {"type": "integer", "description": "Target hour 0-23 (default 0 = midnight)"},
    }, "required": ["city"]},
)
def time_until_city(city: str, target_hour: int = 0) -> str:
    tz, iana = _resolve_tz(city)
    if tz is None:
        return f"Unknown timezone '{city}', sir."
    now = datetime.now(tz)
    target = now.replace(hour=target_hour % 24, minute=0, second=0, microsecond=0)
    if target <= now:
        target = target.replace(day=target.day + 1) if False else \
                 datetime(now.year, now.month, now.day + 1,
                          target_hour % 24, 0, 0, tzinfo=tz)
    delta = target - now
    h, rem = divmod(int(delta.total_seconds()), 3600)
    m = rem // 60
    label = "midnight" if target_hour == 0 else f"{target_hour:02d}:00"
    return (f"{h}h {m}m until {label} in {city.title()} "
            f"(currently {now.strftime('%I:%M %p')} there), sir.")
