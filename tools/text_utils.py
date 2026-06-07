"""
Text Utilities — diff, hash, word count, transforms, QR codes, colour conversion.
All operations are pure stdlib or use free public APIs already whitelisted in CSP.
"""
import base64
import colorsys
import difflib
import hashlib
import re
import urllib.parse
from pathlib import Path
from urllib.request import urlopen, Request

import config
from tools.registry import register

_QR_DIR = config.MEMORY_DIR / "qrcodes"
_QR_DIR.mkdir(parents=True, exist_ok=True)


# ── Word / Text Count ──────────────────────────────────────────────────────────
@register(
    name="word_count",
    description="Count words, characters, sentences and estimated reading time in a block of text.",
    parameters={"type": "object", "properties": {
        "text": {"type": "string", "description": "Text to analyse"},
    }, "required": ["text"]},
)
def word_count(text: str) -> str:
    words = len(text.split())
    chars = len(text)
    chars_no_space = len(text.replace(" ", "").replace("\n", ""))
    sentences = len(re.findall(r'[.!?]+', text)) or 1
    paragraphs = len([p for p in text.split("\n\n") if p.strip()])
    read_min   = max(1, words // 200)
    return (f"Words:       {words:,}\n"
            f"Characters:  {chars:,}  ({chars_no_space:,} without spaces)\n"
            f"Sentences:   {sentences}\n"
            f"Paragraphs:  {paragraphs}\n"
            f"Reading time: ~{read_min} min, sir.")


# ── Text Diff ─────────────────────────────────────────────────────────────────
@register(
    name="text_diff",
    description="Compare two blocks of text and show what changed.",
    parameters={"type": "object", "properties": {
        "text1": {"type": "string", "description": "Original text"},
        "text2": {"type": "string", "description": "New/modified text"},
    }, "required": ["text1", "text2"]},
)
def text_diff(text1: str, text2: str) -> str:
    lines1 = text1.splitlines(keepends=True)
    lines2 = text2.splitlines(keepends=True)
    diff   = list(difflib.unified_diff(lines1, lines2,
                                       fromfile="original", tofile="modified",
                                       lineterm=""))
    if not diff:
        return "No differences found — texts are identical, sir."
    # Summarise
    added   = sum(1 for l in diff if l.startswith('+') and not l.startswith('+++'))
    removed = sum(1 for l in diff if l.startswith('-') and not l.startswith('---'))
    preview = "\n".join(diff[:40])
    summary = f"[+{added} lines added, -{removed} lines removed]\n"
    return summary + preview + ("\n...(truncated)" if len(diff) > 40 else "")


# ── Hash ───────────────────────────────────────────────────────────────────────
@register(
    name="hash_text",
    description="Calculate the MD5, SHA-1, SHA-256 or SHA-512 hash of any text.",
    parameters={"type": "object", "properties": {
        "text":      {"type": "string", "description": "Text to hash"},
        "algorithm": {"type": "string", "description": "md5 / sha1 / sha256 / sha512 (default sha256)"},
    }, "required": ["text"]},
)
def hash_text(text: str, algorithm: str = "sha256") -> str:
    algo = algorithm.lower().replace("-", "")
    funcs = {"md5": hashlib.md5, "sha1": hashlib.sha1,
             "sha256": hashlib.sha256, "sha512": hashlib.sha512}
    if algo not in funcs:
        return f"Unknown algorithm '{algorithm}'. Choose: md5, sha1, sha256, sha512, sir."
    h = funcs[algo](text.encode("utf-8")).hexdigest()
    return f"{algo.upper()}:\n{h}"


@register(
    name="hash_file",
    description="Calculate the SHA-256 hash of a file to verify its integrity.",
    parameters={"type": "object", "properties": {
        "path":      {"type": "string", "description": "Full file path"},
        "algorithm": {"type": "string", "description": "md5 / sha256 (default sha256)"},
    }, "required": ["path"]},
)
def hash_file(path: str, algorithm: str = "sha256") -> str:
    p = Path(path)
    if not p.exists():
        return f"File not found: {path}, sir."
    algo  = algorithm.lower().replace("-", "")
    funcs = {"md5": hashlib.md5, "sha256": hashlib.sha256}
    if algo not in funcs:
        return "Choose md5 or sha256, sir."
    h = funcs[algo]()
    try:
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        size_mb = p.stat().st_size / (1024 * 1024)
        return f"{algo.upper()} of '{p.name}':\n{h.hexdigest()}\nSize: {size_mb:.2f} MB"
    except Exception as e:
        return f"Could not hash file: {e}"


# ── Text Transform ─────────────────────────────────────────────────────────────
_TRANSFORMS = {
    "upper":     str.upper,
    "lower":     str.lower,
    "title":     str.title,
    "reverse":   lambda s: s[::-1],
    "strip":     str.strip,
    "base64":    lambda s: base64.b64encode(s.encode()).decode(),
    "debase64":  lambda s: base64.b64decode(s.encode()).decode(errors="replace"),
    "urlencode": urllib.parse.quote_plus,
    "urldecode": urllib.parse.unquote_plus,
    "camel":     lambda s: re.sub(r'[\s_]+(.)', lambda m: m.group(1).upper(), s.strip()),
    "snake":     lambda s: re.sub(r'(?<=[a-z])([A-Z])', r'_\1', s.replace(" ","_")).lower(),
    "slug":      lambda s: re.sub(r'[^a-z0-9]+','-', s.lower().strip()).strip('-'),
    "count_words": lambda s: str(len(s.split())),
    "remove_spaces": lambda s: re.sub(r'\s+', '', s),
    "rot13":     lambda s: s.translate(str.maketrans(
                     'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz',
                     'NOPQRSTUVWXYZABCDEFGHIJKLMnopqrstuvwxyzabcdefghijklm')),
}

@register(
    name="transform_text",
    description=(
        "Transform text with various operations: upper, lower, title, reverse, strip, "
        "base64, debase64, urlencode, urldecode, camel, snake, slug, rot13, remove_spaces."
    ),
    parameters={"type": "object", "properties": {
        "text":      {"type": "string"},
        "operation": {"type": "string", "description": "Transformation to apply"},
    }, "required": ["text", "operation"]},
)
def transform_text(text: str, operation: str) -> str:
    op = operation.lower().replace(" ", "_").replace("-", "_")
    if op not in _TRANSFORMS:
        opts = ", ".join(_TRANSFORMS.keys())
        return f"Unknown operation '{operation}'. Available: {opts}, sir."
    try:
        result = _TRANSFORMS[op](text)
        return f"Result:\n{result}"
    except Exception as e:
        return f"Transform error: {e}"


# ── QR Code ────────────────────────────────────────────────────────────────────
@register(
    name="generate_qr",
    description="Generate a QR code image for any text or URL. Saves to memory/qrcodes/.",
    parameters={"type": "object", "properties": {
        "text": {"type": "string", "description": "Text or URL to encode"},
        "size": {"type": "integer", "description": "Size in pixels (default 300)"},
    }, "required": ["text"]},
)
def generate_qr(text: str, size: int = 300) -> str:
    try:
        encoded = urllib.parse.quote_plus(text)
        url     = f"https://api.qrserver.com/v1/create-qr-code/?size={size}x{size}&data={encoded}"
        req     = Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urlopen(req, timeout=8) as r:
            img_bytes = r.read()
        # Save locally
        slug     = re.sub(r'[^a-z0-9]+', '_', text.lower())[:30]
        filename = _QR_DIR / f"qr_{slug}.png"
        filename.write_bytes(img_bytes)
        try:
            import os
            os.startfile(str(filename))
        except Exception:
            pass
        return f"QR code generated and saved: {filename.name}, sir."
    except Exception as e:
        return f"QR generation error: {e}"


# ── Colour Converter ──────────────────────────────────────────────────────────
@register(
    name="convert_color",
    description="Convert a colour between HEX, RGB, and HSL formats.",
    parameters={"type": "object", "properties": {
        "color": {"type": "string",
                  "description": "Colour in any format: '#06b6d4', 'rgb(6,182,212)', 'hsl(189,90%,42%)'"},
    }, "required": ["color"]},
)
def convert_color(color: str) -> str:
    c = color.strip()
    try:
        # Parse HEX
        if c.startswith('#'):
            h = c.lstrip('#')
            if len(h) == 3:
                h = ''.join(x*2 for x in h)
            r, g, b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
        # Parse rgb(r,g,b)
        elif c.lower().startswith('rgb'):
            nums = re.findall(r'\d+', c)
            r, g, b = int(nums[0]), int(nums[1]), int(nums[2])
        # Parse hsl(h,s%,l%)
        elif c.lower().startswith('hsl'):
            nums = re.findall(r'[\d.]+', c)
            hh, s, l = float(nums[0])/360, float(nums[1])/100, float(nums[2])/100
            r, g, b  = [int(round(x*255)) for x in colorsys.hls_to_rgb(hh, l, s)]
        else:
            return "Unrecognised colour format. Use #RRGGBB, rgb(r,g,b) or hsl(h,s%,l%), sir."

        # Convert to all formats
        hex_str  = f"#{r:02X}{g:02X}{b:02X}"
        rgb_str  = f"rgb({r}, {g}, {b})"
        h, l, s  = colorsys.rgb_to_hls(r/255, g/255, b/255)
        hsl_str  = f"hsl({int(h*360)}, {int(s*100)}%, {int(l*100)}%)"
        return f"HEX: {hex_str}\nRGB: {rgb_str}\nHSL: {hsl_str}"
    except Exception as e:
        return f"Colour parse error: {e}"


# ── Regex Tester ──────────────────────────────────────────────────────────────
@register(
    name="test_regex",
    description="Test a regular expression against text and show all matches with groups.",
    parameters={"type": "object", "properties": {
        "pattern": {"type": "string", "description": "Regex pattern"},
        "text":    {"type": "string", "description": "Text to test against"},
        "flags":   {"type": "string", "description": "Flags: i=case-insensitive, m=multiline, s=dotall"},
    }, "required": ["pattern", "text"]},
)
def test_regex(pattern: str, text: str, flags: str = "") -> str:
    try:
        fl = 0
        if 'i' in flags: fl |= re.IGNORECASE
        if 'm' in flags: fl |= re.MULTILINE
        if 's' in flags: fl |= re.DOTALL
        compiled = re.compile(pattern, fl)
        matches  = list(compiled.finditer(text))
        if not matches:
            return f"Pattern r'{pattern}' — 0 matches found in the text, sir."
        lines = [f"Pattern r'{pattern}' — {len(matches)} match(es):"]
        for i, m in enumerate(matches[:20], 1):
            line = f"  [{i}] pos {m.start()}-{m.end()}: {repr(m.group())}"
            if m.groups():
                line += f"  groups={m.groups()}"
            lines.append(line)
        if len(matches) > 20:
            lines.append(f"  ... and {len(matches)-20} more.")
        return "\n".join(lines)
    except re.error as e:
        return f"Invalid regex: {e}"


@register(
    name="explain_regex",
    description="Ask JARVIS to explain what a regular expression does in plain English.",
    parameters={"type": "object", "properties": {
        "pattern": {"type": "string", "description": "Regex pattern to explain"},
    }, "required": ["pattern"]},
)
def explain_regex(pattern: str) -> str:
    try:
        from brain.core import get_brain
        prompt = (f"Explain this regular expression in clear, plain English. "
                  f"Break it down part by part. Pattern: {pattern!r}")
        return get_brain().quick(prompt, max_tokens=300)
    except Exception as e:
        return f"Could not explain regex: {e}"


@register(
    name="suggest_regex",
    description="Ask JARVIS to suggest a regular expression for a given task.",
    parameters={"type": "object", "properties": {
        "description": {"type": "string", "description": "What the regex should match, e.g. 'UK phone numbers'"},
    }, "required": ["description"]},
)
def suggest_regex(description: str) -> str:
    try:
        from brain.core import get_brain
        prompt = (f"Write a Python regular expression for: {description}. "
                  f"Reply with ONLY the regex pattern string, then one line of explanation.")
        return get_brain().quick(prompt, max_tokens=150)
    except Exception as e:
        return f"Could not generate regex: {e}"
