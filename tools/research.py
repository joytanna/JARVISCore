import json, re, urllib.request, urllib.parse
from tools.registry import register


def _strip_html(html: str) -> str:
    return re.sub(r"<[^>]+>", "", html).strip()


@register(name="web_search", description="Search the web using DuckDuckGo.",
    parameters={"type": "object", "properties": {"query": {"type": "string"}, "n": {"type": "integer", "default": 5}}, "required": ["query"]})
def web_search(query: str, n: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = [f"- {r['title']}\n  {r['body'][:200]}" for r in ddgs.text(query, max_results=n)]
        return "\n\n".join(results) if results else "No results."
    except Exception:
        pass
    try:
        q = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={q}&format=json&no_redirect=1&no_html=1"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        abstract = data.get("AbstractText", "")
        if abstract:
            return abstract
        related = [t.get("Text", "") for t in data.get("RelatedTopics", [])[:5] if isinstance(t, dict)]
        return "\n".join(related) if related else "No results."
    except Exception as e:
        return f"Search failed: {e}"


@register(name="wikipedia", description="Look up a topic on Wikipedia.",
    parameters={"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]})
def wikipedia(topic: str) -> str:
    try:
        slug = urllib.parse.quote(topic.strip().replace(" ", "_"))
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read()).get("extract", "Not found.")[:1500]
    except Exception as e:
        return f"Wikipedia error: {e}"


@register(name="fetch_url", description="Fetch and return the text content of a URL.",
    parameters={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]})
def fetch_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return _strip_html(r.read().decode("utf-8", errors="replace"))[:3000]
    except Exception as e:
        return f"Error: {e}"


@register(name="news_headlines", description="Get recent news headlines on a topic.",
    parameters={"type": "object", "properties": {"topic": {"type": "string"}}, "required": ["topic"]})
def news_headlines(topic: str) -> str:
    return web_search(f"{topic} news today", n=6)
