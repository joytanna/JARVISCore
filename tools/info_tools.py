"""
Information Tools — Crypto, RSS, Wikipedia, Dictionary, Unit/Currency converter.
"""
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode, quote_plus
from urllib.request import urlopen, Request

import config
from tools.registry import register

_CACHE_DIR = config.MEMORY_DIR / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _http_get(url: str, timeout: int = 8) -> str:
    req = Request(url, headers={"User-Agent": "JARVIS/1.0"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ── Crypto ─────────────────────────────────────────────────────────────────────
@register(
    name="get_crypto_price",
    description="Get the current price and 24h change for a cryptocurrency.",
    parameters={"type":"object","properties":{
        "coin":{"type":"string","description":"Coin name or symbol, e.g. bitcoin, ETH, DOGE"},
    },"required":["coin"]},
)
def get_crypto_price(coin: str) -> str:
    slug_map = {
        "btc":"bitcoin","eth":"ethereum","bnb":"binancecoin","sol":"solana",
        "ada":"cardano","doge":"dogecoin","xrp":"ripple","dot":"polkadot",
        "matic":"matic-network","avax":"avalanche-2","shib":"shiba-inu",
        "ltc":"litecoin","trx":"tron","atom":"cosmos","link":"chainlink",
    }
    symbol = coin.strip().lower()
    slug   = slug_map.get(symbol, symbol)
    try:
        url  = f"https://api.coingecko.com/api/v3/simple/price?ids={slug}&vs_currencies=usd,inr&include_24hr_change=true"
        data = json.loads(_http_get(url))
        if not data:
            return f"Coin '{coin}' not found, sir."
        d     = next(iter(data.values()))
        usd   = d.get("usd", 0)
        inr   = d.get("inr", 0)
        chg   = d.get("usd_24h_change", 0)
        arrow = "▲" if chg >= 0 else "▼"
        return (f"{coin.upper()}: ${usd:,.4f} / ₹{inr:,.2f}  "
                f"{arrow} {abs(chg):.2f}% (24h), sir.")
    except Exception as e:
        return f"Could not fetch crypto price: {e}"


@register(
    name="get_crypto_portfolio",
    description="Get the total USD value of a crypto portfolio.",
    parameters={"type":"object","properties":{
        "holdings":{"type":"string","description":"JSON string like '{\"bitcoin\":0.5,\"ethereum\":2}'"},
    },"required":["holdings"]},
)
def get_crypto_portfolio(holdings: str) -> str:
    try:
        h = json.loads(holdings)
        ids = ",".join(h.keys())
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd"
        prices = json.loads(_http_get(url))
        total  = 0.0
        lines  = []
        for coin, qty in h.items():
            p = prices.get(coin, {}).get("usd", 0)
            val = p * qty
            total += val
            lines.append(f"  {coin}: {qty} × ${p:,.2f} = ${val:,.2f}")
        return "Portfolio:\n" + "\n".join(lines) + f"\n\nTotal: ${total:,.2f}, sir."
    except Exception as e:
        return f"Portfolio error: {e}"


# ── RSS / News Feeds ───────────────────────────────────────────────────────────
@register(
    name="get_rss_feed",
    description="Fetch and summarise the latest headlines from an RSS feed URL or preset topic.",
    parameters={"type":"object","properties":{
        "source":{"type":"string","description":"URL or preset: tech, world, india, science, sports, business"},
        "count": {"type":"integer","description":"Number of items (default 8)"},
    },"required":["source"]},
)
def get_rss_feed(source: str, count: int = 8) -> str:
    presets = {
        "tech":     "https://feeds.feedburner.com/TechCrunch",
        "world":    "http://feeds.bbci.co.uk/news/world/rss.xml",
        "india":    "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        "science":  "https://www.sciencedaily.com/rss/top.xml",
        "sports":   "http://feeds.bbci.co.uk/sport/rss.xml",
        "business": "http://feeds.bbci.co.uk/news/business/rss.xml",
        "ai":       "https://feeds.feedburner.com/nvidiablog",
    }
    url = presets.get(source.lower(), source)
    try:
        xml = _http_get(url)
        titles   = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", xml, re.S)
        descs    = re.findall(r"<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>", xml, re.S)
        items    = [t.strip() for t in titles if t.strip() and "<" not in t]
        # Skip feed title (first item)
        if items and items[0].lower() in source.lower():
            items = items[1:]
        items = items[:count]
        if not items:
            return "No items found in feed, sir."
        return f"📰 Latest from {source}:\n" + "\n".join(f"• {i}" for i in items)
    except Exception as e:
        return f"RSS error: {e}"


# ── Wikipedia ──────────────────────────────────────────────────────────────────
@register(
    name="search_wikipedia",
    description="Search Wikipedia and return a concise summary.",
    parameters={"type":"object","properties":{
        "query":{"type":"string"},
        "sentences":{"type":"integer","description":"Number of sentences (default 4)"},
    },"required":["query"]},
)
def search_wikipedia(query: str, sentences: int = 4) -> str:
    try:
        q   = quote_plus(query)
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{q}"
        d   = json.loads(_http_get(url))
        if d.get("type") == "disambiguation":
            return f"'{query}' is ambiguous on Wikipedia. Try being more specific, sir."
        extract = d.get("extract","")
        if not extract:
            return f"No Wikipedia article found for '{query}', sir."
        # Return first N sentences
        sents = re.split(r"(?<=[.!?])\s+", extract)
        return " ".join(sents[:sentences]) + f"\n\n[Source: en.wikipedia.org/wiki/{d.get('title','')}]"
    except Exception as e:
        return f"Wikipedia error: {e}"


# ── Dictionary ─────────────────────────────────────────────────────────────────
@register(
    name="define_word",
    description="Get the definition, pronunciation and examples of a word.",
    parameters={"type":"object","properties":{"word":{"type":"string"}},"required":["word"]},
)
def define_word(word: str) -> str:
    try:
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote_plus(word.lower())}"
        data = json.loads(_http_get(url))
        if isinstance(data, dict) and "title" in data:
            return f"No definition found for '{word}', sir."
        entry    = data[0]
        phonetic = entry.get("phonetic","")
        lines    = [f"📖 {word.title()}  {phonetic}"]
        for meaning in entry.get("meanings", [])[:3]:
            pos  = meaning.get("partOfSpeech","")
            defs = meaning.get("definitions",[])
            if defs:
                d = defs[0]
                lines.append(f"\n{pos}: {d['definition']}")
                if d.get("example"):
                    lines.append(f'  e.g. "{d["example"]}"')
        return "\n".join(lines)
    except Exception as e:
        return f"Dictionary error: {e}"


# ── Unit & Currency Converter ──────────────────────────────────────────────────
_UNIT_FACTORS = {
    # length
    "mm":1e-3,"cm":1e-2,"m":1.0,"km":1e3,"in":0.0254,"ft":0.3048,
    "yd":0.9144,"mi":1609.344,
    # weight
    "mg":1e-6,"g":1e-3,"kg":1.0,"ton":1000.0,"lb":0.453592,"oz":0.0283495,
    # area
    "cm2":1e-4,"m2":1.0,"km2":1e6,"ha":1e4,"acre":4046.86,"ft2":0.092903,
    # volume
    "ml":1e-3,"l":1.0,"m3":1000.0,"gal":3.78541,"fl_oz":0.0295735,"cup":0.236588,
    # time
    "s":1.0,"min":60.0,"hr":3600.0,"day":86400.0,"week":604800.0,
    # data
    "b":1,"kb":1024,"mb":1048576,"gb":1073741824,"tb":1099511627776,
    # speed
    "mps":1.0,"kph":0.277778,"mph":0.44704,"knot":0.514444,
}
_TEMP_UNITS = {"c","f","k"}

@register(
    name="convert_units",
    description="Convert between units of measurement.",
    parameters={"type":"object","properties":{
        "value":    {"type":"number"},
        "from_unit":{"type":"string","description":"e.g. km, lb, L, mph, C"},
        "to_unit":  {"type":"string","description":"e.g. mi, kg, gal, kph, F"},
    },"required":["value","from_unit","to_unit"]},
)
def convert_units(value: float, from_unit: str, to_unit: str) -> str:
    f, t = from_unit.lower(), to_unit.lower()
    # Temperature special case
    if f in _TEMP_UNITS or t in _TEMP_UNITS:
        if f == "c" and t == "f": r = value*9/5+32
        elif f == "f" and t == "c": r = (value-32)*5/9
        elif f == "c" and t == "k": r = value+273.15
        elif f == "k" and t == "c": r = value-273.15
        elif f == "f" and t == "k": r = (value-32)*5/9+273.15
        elif f == "k" and t == "f": r = (value-273.15)*9/5+32
        else: return f"Unknown temperature conversion {from_unit}→{to_unit}, sir."
        return f"{value} {from_unit.upper()} = {r:.4g} {to_unit.upper()}, sir."
    if f not in _UNIT_FACTORS: return f"Unknown unit '{from_unit}', sir."
    if t not in _UNIT_FACTORS: return f"Unknown unit '{to_unit}', sir."
    result = value * _UNIT_FACTORS[f] / _UNIT_FACTORS[t]
    return f"{value} {from_unit} = {result:.6g} {to_unit}, sir."


@register(
    name="convert_currency",
    description="Convert between currencies using live exchange rates.",
    parameters={"type":"object","properties":{
        "amount":   {"type":"number"},
        "from_curr":{"type":"string","description":"3-letter currency code e.g. USD"},
        "to_curr":  {"type":"string","description":"3-letter currency code e.g. INR"},
    },"required":["amount","from_curr","to_curr"]},
)
def convert_currency(amount: float, from_curr: str, to_curr: str) -> str:
    try:
        fc, tc = from_curr.upper(), to_curr.upper()
        url    = f"https://api.exchangerate-api.com/v4/latest/{fc}"
        data   = json.loads(_http_get(url))
        rate   = data["rates"].get(tc)
        if rate is None:
            return f"Currency '{to_curr}' not found, sir."
        result = amount * rate
        return f"{amount} {fc} = {result:,.4f} {tc}  (rate: {rate:.4f}), sir."
    except Exception as e:
        # Fallback: static rough rates
        return f"Currency conversion error: {e}"


# ── Thesaurus / Synonyms ───────────────────────────────────────────────────────
@register(
    name="get_synonyms",
    description="Get synonyms and antonyms for a word.",
    parameters={"type":"object","properties":{"word":{"type":"string"}},"required":["word"]},
)
def get_synonyms(word: str) -> str:
    try:
        url  = f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote_plus(word.lower())}"
        data = json.loads(_http_get(url))
        if isinstance(data, dict): return f"No synonyms found for '{word}', sir."
        syns, ants = [], []
        for meaning in data[0].get("meanings",[]):
            syns.extend(meaning.get("synonyms",[]))
            ants.extend(meaning.get("antonyms",[]))
        res = f"📚 {word.title()}"
        if syns: res += f"\nSynonyms: {', '.join(syns[:10])}"
        if ants: res += f"\nAntonyms: {', '.join(ants[:10])}"
        return res if (syns or ants) else f"No synonyms found for '{word}', sir."
    except Exception as e:
        return f"Thesaurus error: {e}"
