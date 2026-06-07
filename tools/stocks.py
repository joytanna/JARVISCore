"""
Stock Price Tracker — Uses Yahoo Finance public API (no API key required).
Supports price lookup, simple portfolio valuation, and price alerts.
"""
import json
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen, Request

import config
from tools.registry import register

_DIR       = config.MEMORY_DIR / "stocks"
_DIR.mkdir(parents=True, exist_ok=True)
_ALERT_FILE = _DIR / "alerts.json"
_WATCH_FILE = _DIR / "watchlist.json"


def _yf_fetch(symbol: str) -> dict:
    """Fetch latest quote from Yahoo Finance chart API — no key needed."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.upper()}"
           f"?interval=1d&range=1d")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req, timeout=8) as r:
        return json.loads(r.read())


def _get_price(symbol: str) -> tuple[float, float, str]:
    """Returns (price, change_pct, currency)."""
    data   = _yf_fetch(symbol)
    meta   = data["chart"]["result"][0]["meta"]
    price  = meta.get("regularMarketPrice", 0)
    prev   = meta.get("chartPreviousClose", price)
    change = ((price - prev) / prev * 100) if prev else 0
    curr   = meta.get("currency", "USD")
    return price, change, curr


# ── Get Stock Price ────────────────────────────────────────────────────────────
@register(
    name="get_stock_price",
    description="Get the current stock price and % change for any ticker symbol (e.g. AAPL, TSLA, RELIANCE.NS).",
    parameters={"type": "object", "properties": {
        "symbol": {"type": "string", "description": "Ticker symbol, e.g. AAPL, GOOGL, TSLA, RELIANCE.NS"},
    }, "required": ["symbol"]},
)
def get_stock_price(symbol: str) -> str:
    try:
        price, change, curr = _get_price(symbol.upper())
        arrow = "▲" if change >= 0 else "▼"
        sign  = "+" if change >= 0 else ""
        return (f"{symbol.upper()}: {curr} {price:,.4f}  "
                f"{arrow} {sign}{change:.2f}% today, sir.")
    except Exception as e:
        return f"Could not fetch '{symbol}': {e}"


# ── Stock Info ─────────────────────────────────────────────────────────────────
@register(
    name="get_stock_info",
    description="Get detailed information for a stock: price, volume, 52-week range, market cap.",
    parameters={"type": "object", "properties": {
        "symbol": {"type": "string"},
    }, "required": ["symbol"]},
)
def get_stock_info(symbol: str) -> str:
    try:
        data = _yf_fetch(symbol.upper())
        meta = data["chart"]["result"][0]["meta"]
        price   = meta.get("regularMarketPrice", 0)
        prev    = meta.get("chartPreviousClose", price)
        change  = ((price - prev) / prev * 100) if prev else 0
        curr    = meta.get("currency", "USD")
        vol     = meta.get("regularMarketVolume", 0)
        lo52    = meta.get("fiftyTwoWeekLow",  0)
        hi52    = meta.get("fiftyTwoWeekHigh", 0)
        exch    = meta.get("exchangeName", "")
        name    = meta.get("longName", symbol.upper())

        arrow = "▲" if change >= 0 else "▼"
        return (
            f"--- {name} ({symbol.upper()}) ---\n"
            f"Price:        {curr} {price:,.4f}  {arrow} {change:+.2f}%\n"
            f"Prev close:   {curr} {prev:,.4f}\n"
            f"Volume:       {vol:,}\n"
            f"52-wk range:  {lo52:.2f} – {hi52:.2f}\n"
            f"Exchange:     {exch}, sir."
        )
    except Exception as e:
        return f"Could not fetch info for '{symbol}': {e}"


# ── Watchlist ──────────────────────────────────────────────────────────────────
def _load_watchlist() -> list:
    if _WATCH_FILE.exists():
        try: return json.loads(_WATCH_FILE.read_text())
        except: pass
    return []

def _save_watchlist(data: list):
    _WATCH_FILE.write_text(json.dumps(data, indent=2))


@register(
    name="add_to_watchlist",
    description="Add a stock symbol to your personal watchlist.",
    parameters={"type": "object", "properties": {
        "symbol": {"type": "string"},
    }, "required": ["symbol"]},
)
def add_to_watchlist(symbol: str) -> str:
    sym = symbol.upper()
    wl  = _load_watchlist()
    if sym in wl:
        return f"'{sym}' is already on your watchlist, sir."
    wl.append(sym)
    _save_watchlist(wl)
    return f"'{sym}' added to watchlist, sir."


@register(
    name="get_watchlist",
    description="Show current prices for all stocks on your watchlist.",
    parameters={"type": "object", "properties": {}},
)
def get_watchlist() -> str:
    wl = _load_watchlist()
    if not wl:
        return "Your watchlist is empty. Use add_to_watchlist to add symbols, sir."
    lines = ["--- Watchlist ---"]
    for sym in wl:
        try:
            price, change, curr = _get_price(sym)
            arrow = "▲" if change >= 0 else "▼"
            lines.append(f"  {sym:12} {curr} {price:>12,.2f}  {arrow} {change:+.2f}%")
        except Exception as e:
            lines.append(f"  {sym:12} Error: {e}")
    return "\n".join(lines)


@register(
    name="remove_from_watchlist",
    description="Remove a stock from your watchlist.",
    parameters={"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
)
def remove_from_watchlist(symbol: str) -> str:
    sym = symbol.upper()
    wl  = _load_watchlist()
    if sym not in wl:
        return f"'{sym}' is not in your watchlist, sir."
    wl.remove(sym)
    _save_watchlist(wl)
    return f"'{sym}' removed from watchlist, sir."


# ── Price Alert ────────────────────────────────────────────────────────────────
def _load_alerts() -> list:
    if _ALERT_FILE.exists():
        try: return json.loads(_ALERT_FILE.read_text())
        except: pass
    return []

def _save_alerts(data: list):
    _ALERT_FILE.write_text(json.dumps(data, indent=2))


@register(
    name="set_stock_alert",
    description="Set a price alert for a stock. JARVIS will notify when the price crosses the threshold.",
    parameters={"type": "object", "properties": {
        "symbol":      {"type": "string",  "description": "Ticker symbol"},
        "target_price":{"type": "number",  "description": "Alert when price reaches this value"},
        "direction":   {"type": "string",  "description": "'above' or 'below' (default: above)"},
    }, "required": ["symbol", "target_price"]},
)
def set_stock_alert(symbol: str, target_price: float, direction: str = "above") -> str:
    alerts = _load_alerts()
    alerts.append({
        "symbol":    symbol.upper(),
        "target":    target_price,
        "direction": direction.lower(),
        "created":   datetime.now().isoformat(),
        "fired":     False,
    })
    _save_alerts(alerts)
    return (f"Alert set: notify when {symbol.upper()} goes {direction} "
            f"{target_price:,.2f}, sir.")


def _alert_watcher():
    """Check price alerts every 5 minutes — low overhead."""
    while True:
        time.sleep(300)
        alerts  = _load_alerts()
        changed = False
        for a in alerts:
            if a.get('fired'):
                continue
            try:
                price, _, curr = _get_price(a['symbol'])
                hit = (a['direction'] == 'above' and price >= a['target']) or \
                      (a['direction'] == 'below' and price <= a['target'])
                if hit:
                    a['fired'] = True
                    changed    = True
                    msg = (f"{a['symbol']} is now {curr} {price:.2f} — "
                           f"{a['direction']} your target of {a['target']:.2f}.")
                    try:
                        from jarvis import _push_to_remotes
                        _push_to_remotes({"type": "push", "text": f"📈 {msg}"})
                    except Exception:
                        pass
                    try:
                        from voice.speaker import speak
                        speak(f"Stock alert: {msg}, sir.")
                    except Exception:
                        pass
            except Exception:
                pass
        if changed:
            _save_alerts(alerts)


threading.Thread(target=_alert_watcher, daemon=True, name="stock-alert").start()
