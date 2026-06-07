import json, urllib.request
from tools.registry import register


@register(name="stock_price", description="Get the current stock price for a ticker (e.g. AAPL).",
    parameters={"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]})
def stock_price(ticker: str) -> str:
    t = ticker.upper()
    try:
        import yfinance as yf
        info = yf.Ticker(t).fast_info
        return f"{t}: {info.last_price:.2f} {info.currency}"
    except Exception:
        pass
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{t}?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            meta = json.loads(r.read())["chart"]["result"][0]["meta"]
        price = meta.get("regularMarketPrice", meta.get("previousClose", "N/A"))
        return f"{t}: {price} {meta.get('currency', 'USD')}"
    except Exception as e:
        return f"Could not fetch {t}: {e}"


@register(name="crypto_price", description="Get the current price of a cryptocurrency.",
    parameters={"type": "object", "properties": {"coin": {"type": "string"}}, "required": ["coin"]})
def crypto_price(coin: str) -> str:
    slug = coin.lower().replace(" ", "-")
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={slug}&vs_currencies=usd"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            price = json.loads(r.read()).get(slug, {}).get("usd")
        return f"{coin.capitalize()}: ${price:,.2f} USD" if price else f"'{coin}' not found."
    except Exception as e:
        return f"Crypto error: {e}"


@register(name="fear_greed_index", description="Get the current Crypto Fear and Greed Index.",
    parameters={"type": "object", "properties": {}, "required": []})
def fear_greed_index() -> str:
    try:
        req = urllib.request.Request("https://api.alternative.me/fng/", headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.loads(r.read())["data"][0]
        return f"Fear & Greed Index: {d['value']} — {d['value_classification']}"
    except Exception as e:
        return f"Error: {e}"
