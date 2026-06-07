"""
Note-taking — Markdown notes stored in memory/notes/.
Tools: create_note, list_notes, search_notes, read_note, delete_note, append_note
"""
import re
import time
from datetime import datetime
from pathlib import Path

import config
from tools.registry import register

_NOTES_DIR = config.MEMORY_DIR / "notes"


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", "", title.lower())
    return re.sub(r"\s+", "_", s.strip())[:60]


def _all_notes() -> list[Path]:
    _NOTES_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(_NOTES_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)


@register(
    name="create_note",
    description="Create a new note with a title and content. Saved as Markdown.",
    parameters={
        "type": "object",
        "properties": {
            "title":   {"type": "string"},
            "content": {"type": "string"},
            "tags":    {"type": "string", "description": "Comma-separated tags"},
        },
        "required": ["title", "content"],
    },
)
def create_note(title: str, content: str, tags: str = "") -> str:
    _NOTES_DIR.mkdir(parents=True, exist_ok=True)
    ts   = datetime.now().strftime("%Y-%m-%d %H:%M")
    slug = f"{int(time.time())}_{_slug(title)}"
    body = f"# {title}\n\n**Created:** {ts}"
    if tags:
        body += f"  \n**Tags:** {tags}"
    body += f"\n\n---\n\n{content}\n"
    path = _NOTES_DIR / f"{slug}.md"
    path.write_text(body)
    return f"Note '{title}' saved, sir. ({path.name})"


@register(
    name="list_notes",
    description="List all saved notes with their titles and dates.",
    parameters={"type": "object", "properties": {}},
)
def list_notes() -> str:
    notes = _all_notes()
    if not notes:
        return "No notes yet, sir."
    lines = []
    for p in notes[:20]:
        first = p.read_text().splitlines()[0].lstrip("# ").strip()
        ts    = datetime.fromtimestamp(p.stat().st_mtime).strftime("%b %d %H:%M")
        lines.append(f"• {first}  [{ts}]  ({p.name})")
    return "\n".join(lines)


@register(
    name="read_note",
    description="Read a specific note by title or filename.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string", "description": "Note title or filename"}},
        "required": ["query"],
    },
)
def read_note(query: str) -> str:
    notes  = _all_notes()
    q      = query.lower()
    match  = next(
        (p for p in notes if q in p.stem.lower() or q in p.read_text().splitlines()[0].lower()),
        None,
    )
    if not match:
        return f"No note matching '{query}', sir."
    return match.read_text()


@register(
    name="search_notes",
    description="Search note contents for a keyword.",
    parameters={
        "type": "object",
        "properties": {"keyword": {"type": "string"}},
        "required": ["keyword"],
    },
)
def search_notes(keyword: str) -> str:
    kw    = keyword.lower()
    hits  = []
    for p in _all_notes():
        txt = p.read_text()
        if kw in txt.lower():
            title = txt.splitlines()[0].lstrip("# ").strip()
            # Extract a snippet
            idx  = txt.lower().index(kw)
            snip = txt[max(0, idx-40):idx+80].replace("\n", " ")
            hits.append(f"• {title}\n  …{snip}…")
    return "\n\n".join(hits) if hits else f"No notes contain '{keyword}', sir."


@register(
    name="append_note",
    description="Add content to an existing note.",
    parameters={
        "type": "object",
        "properties": {
            "query":   {"type": "string", "description": "Note title to find"},
            "content": {"type": "string"},
        },
        "required": ["query", "content"],
    },
)
def append_note(query: str, content: str) -> str:
    notes = _all_notes()
    q     = query.lower()
    match = next(
        (p for p in notes
         if q in p.stem.lower() or q in p.read_text().splitlines()[0].lower()),
        None,
    )
    if not match:
        return create_note(query, content)
    existing = match.read_text()
    ts       = datetime.now().strftime("%Y-%m-%d %H:%M")
    match.write_text(existing + f"\n\n---\n*Added {ts}*\n\n{content}\n")
    return f"Appended to '{query}', sir."


@register(
    name="delete_note",
    description="Delete a note by title.",
    parameters={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)
def delete_note(query: str) -> str:
    notes   = _all_notes()
    q       = query.lower()
    matches = [
        p for p in notes
        if q in p.stem.lower() or q in p.read_text().splitlines()[0].lower()
    ]
    if not matches:
        return f"No note matching '{query}', sir."
    title   = matches[0].read_text().splitlines()[0].lstrip("# ").strip()
    for m in matches:
        m.unlink()
    n = len(matches)
    return (f"Note '{title}' deleted, sir." if n == 1
            else f"Deleted {n} notes matching '{query}', sir.")
