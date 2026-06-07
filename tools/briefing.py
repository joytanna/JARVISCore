"""Daily briefing — weather + news + email count in one spoken summary."""
import datetime
from tools.registry import register


@register(
    name="daily_briefing",
    description="Deliver a morning briefing: date, weather, top news, and unread email count",
    parameters={"type": "object", "properties": {}},
)
def daily_briefing() -> str:
    now   = datetime.datetime.now()
    parts = [f"Good {'morning' if now.hour < 12 else 'afternoon' if now.hour < 17 else 'evening'}, sir. "
             f"It's {now.strftime('%A, %d %B %Y')}."]

    # Weather
    try:
        from tools.weather import get_weather
        parts.append(get_weather())
    except Exception as e:
        parts.append(f"Weather unavailable: {e}")

    # News
    try:
        from tools.research import news_headlines
        headlines = news_headlines()
        # Just first 3 lines
        lines = [l for l in headlines.splitlines() if l.strip()][:3]
        parts.append("Top headlines: " + " | ".join(lines))
    except Exception as e:
        parts.append(f"News unavailable: {e}")

    # Email count
    try:
        import imaplib, ssl, config
        if config.GMAIL_ADDRESS and config.GMAIL_APP_PASSWORD:
            ctx  = ssl.create_default_context()
            conn = imaplib.IMAP4_SSL("imap.gmail.com", 993, ssl_context=ctx)
            conn.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            conn.select("INBOX")
            _, ids = conn.search(None, "UNSEEN")
            count = len(ids[0].split()) if ids[0] else 0
            conn.logout()
            parts.append(f"You have {count} unread email{'s' if count != 1 else ''} in your inbox.")
    except Exception:
        pass

    return "\n".join(parts)
