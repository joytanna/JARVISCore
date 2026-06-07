"""
Clipboard Transformer — Read clipboard, apply operations, write back.
One-command power-ups: UPPER, title, clean, trim, URL encode/decode,
extract emails/URLs/numbers, sort lines, deduplicate, JSON prettify.
"""
import json
import re
import urllib.parse

from tools.registry import register


def _read_clip() -> str:
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        except Exception:
            text = ""
        win32clipboard.CloseClipboard()
        return text or ""
    except Exception:
        return ""


def _write_clip(text: str) -> bool:
    try:
        import win32clipboard
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text)
        win32clipboard.CloseClipboard()
        return True
    except Exception:
        return False


def _preview(text: str, max_chars: int = 200) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"… [{len(text)} chars total]"


# ── Transform Clipboard ────────────────────────────────────────────────────────
_CLIP_OPS = {
    "upper":        str.upper,
    "lower":        str.lower,
    "title":        str.title,
    "strip":        str.strip,
    "trim_lines":   lambda s: "\n".join(l.strip() for l in s.splitlines()),
    "deduplicate":  lambda s: "\n".join(dict.fromkeys(s.splitlines())),
    "sort_lines":   lambda s: "\n".join(sorted(s.splitlines())),
    "reverse_lines":lambda s: "\n".join(reversed(s.splitlines())),
    "remove_blanks":lambda s: "\n".join(l for l in s.splitlines() if l.strip()),
    "urlencode":    urllib.parse.quote_plus,
    "urldecode":    urllib.parse.unquote_plus,
    "json_pretty":  lambda s: json.dumps(json.loads(s), indent=2, ensure_ascii=False),
    "json_compact": lambda s: json.dumps(json.loads(s), separators=(',', ':'), ensure_ascii=False),
    "count_lines":  lambda s: str(len(s.splitlines())),
    "count_words":  lambda s: str(len(s.split())),
    "count_chars":  lambda s: str(len(s)),
    "remove_spaces":lambda s: re.sub(r'\s+', '', s),
    "csv_to_lines": lambda s: "\n".join(re.split(r',\s*', s)),
    "lines_to_csv": lambda s: ", ".join(s.splitlines()),
    "slug":         lambda s: re.sub(r'[^a-z0-9]+', '-', s.lower().strip()).strip('-'),
}

@register(
    name="transform_clipboard",
    description=(
        "Read clipboard, apply a transformation, and write back. "
        "Operations: upper, lower, title, strip, trim_lines, deduplicate, sort_lines, "
        "reverse_lines, remove_blanks, urlencode, urldecode, json_pretty, json_compact, "
        "count_lines, count_words, count_chars, csv_to_lines, lines_to_csv, slug."
    ),
    parameters={"type": "object", "properties": {
        "operation": {"type": "string", "description": "Transformation to apply"},
    }, "required": ["operation"]},
)
def transform_clipboard(operation: str) -> str:
    op   = operation.lower().replace(" ", "_").replace("-", "_")
    text = _read_clip()
    if not text:
        return "Clipboard is empty, sir."
    if op not in _CLIP_OPS:
        opts = ", ".join(sorted(_CLIP_OPS.keys()))
        return f"Unknown operation '{operation}'. Available: {opts}, sir."
    try:
        result = _CLIP_OPS[op](text)
        # Count-only ops — don't write back
        if op.startswith("count_"):
            return f"Result: {result} (clipboard unchanged), sir."
        written = _write_clip(result)
        preview = _preview(result)
        if written:
            return f"Clipboard updated ({op}):\n{preview}"
        return f"Result ({op}) — clipboard write failed, here's the output:\n{preview}"
    except Exception as e:
        return f"Transform error ({op}): {e}"


# ── Extract from Clipboard ────────────────────────────────────────────────────
@register(
    name="extract_from_clipboard",
    description="Extract specific data from clipboard text: emails, URLs, phone numbers, or numbers.",
    parameters={"type": "object", "properties": {
        "what": {"type": "string",
                 "description": "What to extract: emails, urls, phones, numbers, hashtags, mentions"},
    }, "required": ["what"]},
)
def extract_from_clipboard(what: str) -> str:
    text = _read_clip()
    if not text:
        return "Clipboard is empty, sir."

    patterns = {
        "emails":   r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
        "urls":     r'https?://[^\s<>"{}|\\^`\[\]]+',
        "phones":   r'(?:\+?\d[\d\s\-\(\)]{7,}\d)',
        "numbers":  r'\b\d+(?:\.\d+)?\b',
        "hashtags": r'#\w+',
        "mentions": r'@\w+',
    }
    w = what.lower()
    if w not in patterns:
        return f"Unknown type '{what}'. Choose: emails, urls, phones, numbers, hashtags, mentions, sir."

    matches = list(dict.fromkeys(re.findall(patterns[w], text)))  # unique, ordered
    if not matches:
        return f"No {what} found in clipboard, sir."

    result = "\n".join(matches[:50])
    _write_clip(result)
    return (f"Found {len(matches)} {what} — copied to clipboard:\n"
            + "\n".join(matches[:15])
            + (f"\n... and {len(matches)-15} more." if len(matches) > 15 else ""))


# ── Paste as Plain Text ────────────────────────────────────────────────────────
@register(
    name="strip_clipboard_formatting",
    description="Remove all formatting from clipboard (convert rich text to plain text).",
    parameters={"type": "object", "properties": {}},
)
def strip_clipboard_formatting() -> str:
    text = _read_clip()
    if not text:
        return "Clipboard is empty, sir."
    # Remove common rich-text artifacts
    clean = re.sub(r'\r\n', '\n', text)
    clean = re.sub(r'\r', '\n', clean)
    clean = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', clean)
    _write_clip(clean)
    return f"Clipboard cleaned ({len(text)} → {len(clean)} chars), sir."


# ── Clipboard Stats ────────────────────────────────────────────────────────────
@register(
    name="clipboard_stats",
    description="Show word count, character count, line count and detected content type of current clipboard.",
    parameters={"type": "object", "properties": {}},
)
def clipboard_stats() -> str:
    text = _read_clip()
    if not text:
        return "Clipboard is empty, sir."
    words  = len(text.split())
    chars  = len(text)
    lines  = len(text.splitlines())
    # Guess content type
    if re.match(r'^\s*[\[{]', text):
        ctype = "JSON/array"
    elif re.search(r'https?://', text):
        ctype = "URL(s)"
    elif re.search(r'@.*\.', text):
        ctype = "email address(es)"
    elif text.count('\n') > 2:
        ctype = "multi-line text"
    elif re.match(r'^\s*\d+[\d\s,.]*$', text):
        ctype = "numbers"
    else:
        ctype = "plain text"
    return (f"Clipboard: {chars:,} chars, {words:,} words, {lines} lines\n"
            f"Detected: {ctype}\n"
            f"Preview: {_preview(text, 100)}")
