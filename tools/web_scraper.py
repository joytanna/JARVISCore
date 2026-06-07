"""
Web Scraper & Data Extractor — scrape URLs, extract tables,
summarise any webpage, monitor pages for changes.
"""
import hashlib
import json
import re
import time
import threading
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote_plus
from urllib.request import urlopen, Request

import config
from tools.registry import register

_DIR          = config.MEMORY_DIR / "scraper"
_DIR.mkdir(parents=True, exist_ok=True)
_MONITOR_FILE = _DIR / "monitors.json"


def _fetch(url: str, timeout: int = 10) -> str:
    if not url.startswith("http"):
        url = "https://" + url
    req = Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"),
        "Accept": "text/html,application/xhtml+xml,*/*",
        "Accept-Language": "en-US,en;q=0.9",
    })
    with urlopen(req, timeout=timeout) as r:
        charset = r.headers.get_content_charset() or "utf-8"
        return r.read().decode(charset, errors="replace")


def _strip_html(html: str) -> str:
    # Remove scripts, styles, nav, footer, ads
    html = re.sub(r"<(script|style|nav|footer|header|aside|noscript)[^>]*>.*?</\1>",
                  "", html, flags=re.S | re.I)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", " ", html)
    # Collapse whitespace
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ── Scrape URL ─────────────────────────────────────────────────────────────────
@register(
    name="scrape_url",
    description="Fetch and extract readable text content from any URL.",
    parameters={"type":"object","properties":{
        "url":       {"type":"string","description":"Full URL to scrape"},
        "max_chars": {"type":"integer","description":"Maximum characters to return (default 3000)"},
    },"required":["url"]},
)
def scrape_url(url: str, max_chars: int = 3000) -> str:
    try:
        html = _fetch(url)
        text = _strip_html(html)
        if len(text) > max_chars:
            text = text[:max_chars] + f"…\n[Truncated at {max_chars} chars. {len(text)} total]"
        return f"📄 Content from {url}:\n\n{text}"
    except Exception as e:
        return f"Could not scrape '{url}': {e}"


# ── Summarise URL ──────────────────────────────────────────────────────────────
@register(
    name="summarize_url",
    description="Fetch a URL and get an AI summary of its content.",
    parameters={"type":"object","properties":{
        "url":{"type":"string","description":"URL to summarise"},
    },"required":["url"]},
)
def summarize_url(url: str) -> str:
    try:
        html  = _fetch(url)
        text  = _strip_html(html)[:6000]
        from brain.core import get_brain
        prompt = f"Summarise this web page content in 3-5 bullet points:\n\n{text}"
        return get_brain().quick(prompt, max_tokens=400)
    except Exception as e:
        return f"Could not summarise '{url}': {e}"


# ── Extract Tables ─────────────────────────────────────────────────────────────
@register(
    name="extract_table",
    description="Extract HTML tables from a URL as readable text.",
    parameters={"type":"object","properties":{
        "url":         {"type":"string"},
        "table_index": {"type":"integer","description":"Which table (0=first, default 0)"},
    },"required":["url"]},
)
def extract_table(url: str, table_index: int = 0) -> str:
    try:
        html   = _fetch(url)
        tables = re.findall(r"<table[^>]*>(.*?)</table>", html, re.S | re.I)
        if not tables:
            return f"No tables found on {url}, sir."
        if table_index >= len(tables):
            return f"Only {len(tables)} table(s) found. Index {table_index} out of range, sir."
        table = tables[table_index]
        rows  = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S | re.I)
        lines = []
        for row in rows:
            cells = re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", row, re.S | re.I)
            vals  = [_strip_html(c).strip() for c in cells]
            lines.append(" | ".join(vals))
        return f"Table {table_index} from {url}:\n" + "\n".join(lines[:50])
    except Exception as e:
        return f"Table extraction error: {e}"


# ── Extract Links ──────────────────────────────────────────────────────────────
@register(
    name="extract_links",
    description="Get all links from a webpage.",
    parameters={"type":"object","properties":{
        "url":{"type":"string"},
        "filter":{"type":"string","description":"Keyword to filter links (optional)"},
        "max":   {"type":"integer","description":"Max links to return (default 20)"},
    },"required":["url"]},
)
def extract_links(url: str, filter: str = "", max: int = 20) -> str:
    try:
        html  = _fetch(url)
        hrefs = re.findall(r'href=["\']([^"\']+)["\']', html, re.I)
        base  = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        links = []
        for h in hrefs:
            if h.startswith("//"):    h = "https:" + h
            elif h.startswith("/"):   h = base + h
            elif not h.startswith("http"): continue
            if filter and filter.lower() not in h.lower(): continue
            if h not in links: links.append(h)
        links = links[:max]
        if not links:
            return f"No links found{' matching '+filter if filter else ''} on {url}, sir."
        return "\n".join(f"• {l}" for l in links)
    except Exception as e:
        return f"Link extraction error: {e}"


# ── Page Monitor ───────────────────────────────────────────────────────────────
def _load_monitors() -> list:
    if _MONITOR_FILE.exists():
        try: return json.loads(_MONITOR_FILE.read_text())
        except Exception: pass
    return []

def _save_monitors(m: list):
    _MONITOR_FILE.write_text(json.dumps(m, indent=2))

def _monitor_worker():
    """Check monitored pages every 5 minutes for changes."""
    while True:
        time.sleep(300)
        monitors = _load_monitors()
        changed  = False
        for m in monitors:
            if m.get("paused"): continue
            try:
                html = _fetch(m["url"])
                text = _strip_html(html)[:5000]
                h    = hashlib.md5(text.encode()).hexdigest()
                if m.get("last_hash") and h != m["last_hash"]:
                    # Page changed — notify
                    kw = m.get("keyword","")
                    if not kw or kw.lower() in text.lower():
                        m["changed"]   = True
                        m["change_ts"] = datetime.now().isoformat()
                        try:
                            from jarvis import _push_to_remotes
                            _push_to_remotes({"type":"push",
                                              "text":f"🔔 Page changed: {m['url']}"})
                        except Exception:
                            pass
                        try:
                            from voice.speaker import speak
                            speak(f"Page change detected: {m.get('name','monitored page')}")
                        except Exception:
                            pass
                m["last_hash"] = h
                changed = True
            except Exception:
                pass
        if changed:
            _save_monitors(monitors)

threading.Thread(target=_monitor_worker, daemon=True, name="page-monitor").start()

@register(
    name="monitor_page",
    description="Start monitoring a URL for changes. JARVIS will notify when it changes.",
    parameters={"type":"object","properties":{
        "url":     {"type":"string","description":"URL to watch"},
        "name":    {"type":"string","description":"Friendly name for this monitor"},
        "keyword": {"type":"string","description":"Only alert if this keyword appears in the change"},
    },"required":["url"]},
)
def monitor_page(url: str, name: str = "", keyword: str = "") -> str:
    monitors = _load_monitors()
    monitors = [m for m in monitors if m["url"] != url]  # remove if already watching
    monitors.append({
        "url": url, "name": name or url,
        "keyword": keyword, "last_hash": "",
        "started": datetime.now().isoformat(),
        "changed": False, "paused": False,
    })
    _save_monitors(monitors)
    return f"Now monitoring '{name or url}'. Will notify on any change, sir."


@register(
    name="list_monitors",
    description="List all actively monitored web pages.",
    parameters={"type":"object","properties":{}},
)
def list_monitors() -> str:
    monitors = _load_monitors()
    if not monitors:
        return "No pages being monitored, sir."
    lines = []
    for m in monitors:
        status = "⚠️  CHANGED" if m.get("changed") else "✅ Unchanged"
        paused = " (paused)" if m.get("paused") else ""
        lines.append(f"• {m['name']}{paused}  —  {status}  —  {m['url']}")
    return "\n".join(lines)


@register(
    name="stop_monitoring",
    description="Stop monitoring a page.",
    parameters={"type":"object","properties":{"name":{"type":"string"}},"required":["name"]},
)
def stop_monitoring(name: str) -> str:
    monitors = _load_monitors()
    q = name.lower()
    before = len(monitors)
    monitors = [m for m in monitors if q not in m["name"].lower() and q not in m["url"].lower()]
    _save_monitors(monitors)
    removed = before - len(monitors)
    return f"Removed {removed} monitor(s), sir." if removed else f"No monitor found for '{name}', sir."


# ── Search DuckDuckGo ──────────────────────────────────────────────────────────
@register(
    name="web_search",
    description="Search the web and return top results.",
    parameters={"type":"object","properties":{
        "query":{"type":"string"},
        "max_results":{"type":"integer","description":"Max results (default 5)"},
    },"required":["query"]},
)
def web_search(query: str, max_results: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return f"No results for '{query}', sir."
        lines = []
        for r in results:
            lines.append(f"• {r.get('title','')}\n  {r.get('href','')}\n  {r.get('body','')[:200]}")
        return "\n\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"
