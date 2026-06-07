"""
Flashcard System — Create, review, and track spaced-repetition study cards.
Uses a simple SM-2-inspired algorithm: cards due for review bubble to the top.
All data stored locally in memory/flashcards/.
"""
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import config
from tools.registry import register

_DIR  = config.MEMORY_DIR / "flashcards"
_DIR.mkdir(parents=True, exist_ok=True)
_FILE = _DIR / "cards.json"


# ── SM-2 helper ────────────────────────────────────────────────────────────────
def _next_interval(card: dict, quality: int) -> int:
    """
    quality: 0=forgot, 1=hard, 2=ok, 3=easy.
    Returns days until next review.
    """
    n    = card.get('reps', 0)
    ef   = card.get('ef', 2.5)
    iv   = card.get('interval', 1)

    if quality < 2:
        return 1  # repeat tomorrow

    if n == 0:    iv = 1
    elif n == 1:  iv = 6
    else:         iv = round(iv * ef)

    ef = max(1.3, ef + 0.1 - (3 - quality) * (0.08 + (3 - quality) * 0.02))
    card['ef']       = round(ef, 2)
    card['reps']     = n + 1
    card['interval'] = iv
    return iv


def _load() -> list:
    if _FILE.exists():
        try: return json.loads(_FILE.read_text())
        except: pass
    return []

def _save(data: list):
    _FILE.write_text(json.dumps(data, indent=2))


# ── Create Card ────────────────────────────────────────────────────────────────
@register(
    name="create_flashcard",
    description="Create a new flashcard for study.",
    parameters={"type": "object", "properties": {
        "front":   {"type": "string", "description": "Question or term"},
        "back":    {"type": "string", "description": "Answer or definition"},
        "deck":    {"type": "string", "description": "Deck name (e.g. 'Python', 'French', 'Chemistry')"},
        "hint":    {"type": "string", "description": "Optional hint"},
    }, "required": ["front", "back"]},
)
def create_flashcard(front: str, back: str,
                     deck: str = "General", hint: str = "") -> str:
    cards = _load()
    # Check for duplicate
    for c in cards:
        if c['front'].lower() == front.lower() and c['deck'].lower() == deck.lower():
            return f"A card for '{front}' already exists in deck '{deck}', sir."
    cards.append({
        "front":    front,
        "back":     back,
        "deck":     deck,
        "hint":     hint,
        "reps":     0,
        "ef":       2.5,
        "interval": 1,
        "due":      date.today().isoformat(),
        "created":  datetime.now().isoformat(),
    })
    _save(cards)
    return f"Flashcard added to deck '{deck}': {front!r} → {back!r}, sir."


# ── List Decks ─────────────────────────────────────────────────────────────────
@register(
    name="list_flashcard_decks",
    description="List all flashcard decks and how many cards are due for review.",
    parameters={"type": "object", "properties": {}},
)
def list_flashcard_decks() -> str:
    cards = _load()
    if not cards:
        return "No flashcards yet. Use create_flashcard to add some, sir."
    today = date.today().isoformat()
    decks: dict = {}
    for c in cards:
        d = c.get('deck', 'General')
        decks.setdefault(d, {'total': 0, 'due': 0})
        decks[d]['total'] += 1
        if c.get('due', '9999') <= today:
            decks[d]['due'] += 1
    lines = ["--- Flashcard Decks ---"]
    for deck, s in sorted(decks.items()):
        lines.append(f"  {deck:20}  {s['total']:>3} cards  "
                     f"({s['due']} due{'!' if s['due'] > 0 else ''})")
    return "\n".join(lines)


# ── Review ─────────────────────────────────────────────────────────────────────
@register(
    name="review_flashcards",
    description="Start a review session. Returns the next due card (call repeatedly to review all).",
    parameters={"type": "object", "properties": {
        "deck":    {"type": "string", "description": "Deck to review (default: all due cards)"},
        "answer":  {"type": "string", "description": "Your answer to the last card shown (optional)"},
        "quality": {"type": "integer",
                    "description": "Rate last card: 0=forgot, 1=hard, 2=ok, 3=easy (required if answer given)"},
        "card_id": {"type": "integer", "description": "Internal card index to rate (from previous response)"},
    }},
)
def review_flashcards(deck: str = "", answer: str = "",
                      quality: int = -1, card_id: int = -1) -> str:
    cards = _load()
    today = date.today().isoformat()

    # If rating a previous card
    if card_id >= 0 and quality >= 0 and 0 <= card_id < len(cards):
        c = cards[card_id]
        days = _next_interval(c, quality)
        c['due']         = (date.today() + timedelta(days=days)).isoformat()
        c['last_review'] = today
        # Optionally show user's answer alongside correct answer
        resp_lines = [f"Correct answer: {c['back']}"]
        if answer:
            resp_lines.append(f"Your answer:    {answer}")
        qmap = {0:"Forgot", 1:"Hard", 2:"OK", 3:"Easy"}
        resp_lines.append(f"Marked as: {qmap.get(quality,'?')} → next review in {days} day(s).")
        _save(cards)
        # Now get next card
        next_card_resp = _get_next_card(cards, deck, today)
        return "\n".join(resp_lines) + "\n\n" + next_card_resp

    return _get_next_card(cards, deck, today)


def _get_next_card(cards: list, deck: str, today: str) -> str:
    due = [
        (i, c) for i, c in enumerate(cards)
        if c.get('due', '9999') <= today
        and (not deck or c.get('deck','').lower() == deck.lower())
    ]
    if not due:
        return "No cards due for review right now. Great job staying on top of it, sir!"

    # Shuffle slightly to avoid always seeing same card first
    import random
    random.shuffle(due)
    idx, card = due[0]
    hint = f"\n   Hint: {card['hint']}" if card.get('hint') else ""
    return (f"[{len(due)} cards due]  Deck: {card.get('deck','General')}\n\n"
            f"Q: {card['front']}{hint}\n\n"
            f"(Call review_flashcards with card_id={idx} and quality=0/1/2/3 to rate it)")


# ── Delete Card ────────────────────────────────────────────────────────────────
@register(
    name="delete_flashcards",
    description="Delete flashcards by keyword match on front/deck.",
    parameters={"type": "object", "properties": {
        "keyword": {"type": "string", "description": "Keyword to match in card front or deck name"},
        "deck":    {"type": "string", "description": "Delete entire deck (overrides keyword)"},
    }},
)
def delete_flashcards(keyword: str = "", deck: str = "") -> str:
    cards  = _load()
    before = len(cards)
    if deck:
        cards = [c for c in cards if c.get('deck','').lower() != deck.lower()]
    elif keyword:
        q     = keyword.lower()
        cards = [c for c in cards if q not in c['front'].lower()
                 and q not in c.get('back','').lower()
                 and q not in c.get('deck','').lower()]
    else:
        return "Specify a keyword or deck to delete, sir."
    _save(cards)
    removed = before - len(cards)
    return f"Deleted {removed} card(s), sir."


# ── Quick-add multiple cards ───────────────────────────────────────────────────
@register(
    name="bulk_create_flashcards",
    description=(
        "Create multiple flashcards at once. "
        "Format: 'Q1 | A1 || Q2 | A2 || Q3 | A3'"
    ),
    parameters={"type": "object", "properties": {
        "cards_text": {"type": "string",
                       "description": "Cards separated by ||, Q and A separated by |"},
        "deck":       {"type": "string", "description": "Deck name for all cards"},
    }, "required": ["cards_text"]},
)
def bulk_create_flashcards(cards_text: str, deck: str = "General") -> str:
    pairs  = [p.strip() for p in cards_text.split("||") if p.strip()]
    added  = 0
    errors = []
    for pair in pairs:
        parts = [x.strip() for x in pair.split("|")]
        if len(parts) < 2:
            errors.append(f"Skipped (no separator): {pair[:40]}")
            continue
        msg = create_flashcard(parts[0], parts[1], deck,
                                hint=parts[2] if len(parts) > 2 else "")
        if "already exists" not in msg:
            added += 1
    result = f"Added {added}/{len(pairs)} cards to deck '{deck}', sir."
    if errors:
        result += "\nSkipped:\n" + "\n".join(f"  - {e}" for e in errors)
    return result
