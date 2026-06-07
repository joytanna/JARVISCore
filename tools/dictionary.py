"""
Dictionary, Thesaurus & Word Tools — free APIs, no key required.
Uses dictionaryapi.dev (free, open-source) for definitions + synonyms.
Falls back to a local common-word map for offline use.
"""
import json
import re
import urllib.request
import urllib.parse
from tools.registry import register

_API = "https://api.dictionaryapi.dev/api/v2/entries/en/"


def _fetch(word: str) -> list:
    """Fetch definitions from dictionaryapi.dev. Returns list of entries."""
    url = _API + urllib.parse.quote(word.lower().strip())
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=6) as r:
            return json.loads(r.read())
    except Exception:
        return []


# ── Define ────────────────────────────────────────────────────────────────────
@register(
    name="define_word",
    description="Get the definition, phonetic pronunciation, and examples for any English word.",
    parameters={"type": "object", "properties": {
        "word": {"type": "string", "description": "Word to define"},
        "n":    {"type": "integer", "description": "Number of definitions to show (default 3)"},
    }, "required": ["word"]},
)
def define_word(word: str, n: int = 3) -> str:
    entries = _fetch(word)
    if not entries or not isinstance(entries, list):
        return f"Definition for '{word}' not found, sir. Check spelling?"
    if isinstance(entries, dict) and entries.get("title") == "No Definitions Found":
        return f"No definition found for '{word}', sir."
    # First entry
    entry = entries[0]
    phonetic = entry.get("phonetic", "")
    meanings = entry.get("meanings", [])
    lines = [f"**{word}**" + (f"  /{phonetic}/" if phonetic else "")]
    count = 0
    for meaning in meanings:
        pos   = meaning.get("partOfSpeech", "")
        defs  = meaning.get("definitions", [])
        for d in defs:
            if count >= n:
                break
            defn    = d.get("definition", "")
            example = d.get("example", "")
            lines.append(f"  [{pos}] {defn}")
            if example:
                lines.append(f"         e.g. \"{example}\"")
            count += 1
        if count >= n:
            break
    return "\n".join(lines)


# ── Synonyms / Antonyms ───────────────────────────────────────────────────────
@register(
    name="synonyms",
    description="Get synonyms (and antonyms) for any English word.",
    parameters={"type": "object", "properties": {
        "word": {"type": "string"},
    }, "required": ["word"]},
)
def synonyms(word: str) -> str:
    entries = _fetch(word)
    if not entries or not isinstance(entries, list):
        return f"No synonyms found for '{word}', sir."
    syns: list = []
    ants: list = []
    for entry in entries:
        for meaning in entry.get("meanings", []):
            syns.extend(meaning.get("synonyms", []))
            ants.extend(meaning.get("antonyms", []))
            for d in meaning.get("definitions", []):
                syns.extend(d.get("synonyms", []))
                ants.extend(d.get("antonyms", []))
    # Deduplicate
    syns = list(dict.fromkeys(syns))[:15]
    ants = list(dict.fromkeys(ants))[:10]
    if not syns and not ants:
        return f"No synonyms found for '{word}', sir."
    lines = [f"**{word}**"]
    if syns:
        lines.append(f"  Synonyms:  {', '.join(syns)}")
    if ants:
        lines.append(f"  Antonyms:  {', '.join(ants)}")
    return "\n".join(lines)


# ── Word of the Day ───────────────────────────────────────────────────────────
_WOTD_LIST = [
    ("ephemeral",    "adj", "Lasting for only a short time."),
    ("perspicacious","adj", "Having a ready insight into things; shrewd."),
    ("sonder",       "n",   "The realisation that each passerby has a life as vivid and complex as one's own."),
    ("petrichor",    "n",   "The pleasant smell that frequently accompanies the first rain after a long period of dry weather."),
    ("serendipity",  "n",   "The occurrence of events by chance in a happy or beneficial way."),
    ("mellifluous",  "adj", "Sweet or musical; pleasant to hear."),
    ("sycophant",    "n",   "A person who acts obsequiously towards someone important in order to gain advantage."),
    ("obfuscate",    "v",   "Render obscure, unclear, or unintelligible."),
    ("equanimity",   "n",   "Mental calmness and composure, especially in difficult situations."),
    ("laconic",      "adj", "Using very few words."),
    ("pellucid",     "adj", "Translucently clear; easily understood."),
    ("ineffable",    "adj", "Too great or extreme to be expressed in words."),
    ("eloquent",     "adj", "Fluent or persuasive in speaking or writing."),
    ("paradigm",     "n",   "A typical example or pattern; a model."),
    ("ubiquitous",   "adj", "Present, appearing, or found everywhere."),
    ("cogent",       "adj", "Clear, logical, and convincing."),
    ("tenacious",    "adj", "Tending to keep a firm hold; not readily relinquishing."),
    ("prolific",     "adj", "Present in large numbers or quantities; plentiful."),
    ("arduous",      "adj", "Involving or requiring strenuous effort."),
    ("sagacious",    "adj", "Having or showing keen mental discernment and good judgement."),
    ("verbose",      "adj", "Using or expressed in more words than are needed."),
    ("catharsis",    "n",   "The process of releasing and providing relief from strong or repressed emotions."),
    ("zeitgeist",    "n",   "The defining spirit or mood of a particular period of history."),
    ("juxtapose",    "v",   "Place or deal with close together for contrasting effect."),
    ("insouciant",   "adj", "Showing a casual lack of concern; indifferent."),
    ("propitious",   "adj", "Giving or indicating a good chance of success; favourable."),
    ("recalcitrant", "adj", "Having an obstinately uncooperative attitude."),
    ("visceral",     "adj", "Relating to deep inward feelings rather than intellect."),
    ("penultimate",  "adj", "Last but one in a series."),
    ("ephemeron",    "n",   "A thing that exists only for a short time."),
]

@register(
    name="word_of_the_day",
    description="Get an interesting or advanced English word of the day with definition and usage.",
    parameters={"type": "object", "properties": {}},
)
def word_of_the_day() -> str:
    from datetime import date
    import hashlib
    # Deterministic per day — same word all day, changes daily
    idx = int(hashlib.md5(date.today().isoformat().encode()).hexdigest(), 16) % len(_WOTD_LIST)
    word, pos, defn = _WOTD_LIST[idx]
    # Try to get a real example from the API
    example = ""
    try:
        entries = _fetch(word)
        if entries and isinstance(entries, list):
            for meaning in entries[0].get("meanings", []):
                for d in meaning.get("definitions", []):
                    if d.get("example"):
                        example = d["example"]
                        break
                if example:
                    break
    except Exception:
        pass
    lines = [f"Word of the Day: **{word}**  [{pos}]",
             f"  {defn}"]
    if example:
        lines.append(f'  e.g. "{example}"')
    return "\n".join(lines)


# ── Spell check ───────────────────────────────────────────────────────────────
@register(
    name="spell_check",
    description="Check if a word is spelled correctly and suggest the correct spelling.",
    parameters={"type": "object", "properties": {
        "word": {"type": "string"},
    }, "required": ["word"]},
)
def spell_check(word: str) -> str:
    entries = _fetch(word)
    if entries and isinstance(entries, list) and not isinstance(entries, dict):
        # Check if it's a valid word
        if entries and "word" in entries[0]:
            return f"'{word}' is spelled correctly, sir."
    # Try fetching from the free Datamuse spell-suggest API
    try:
        url = f"https://api.datamuse.com/words?sp={urllib.parse.quote(word)}&max=5"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            results = json.loads(r.read())
        if results:
            suggestions = [r["word"] for r in results[:5]]
            return f"'{word}' may be misspelled. Did you mean: {', '.join(suggestions)}?"
    except Exception:
        pass
    return f"Could not verify spelling of '{word}', sir."


# ── Rhyming words ─────────────────────────────────────────────────────────────
@register(
    name="find_rhymes",
    description="Find words that rhyme with a given word.",
    parameters={"type": "object", "properties": {
        "word": {"type": "string"},
        "n":    {"type": "integer", "description": "Max results (default 10)"},
    }, "required": ["word"]},
)
def find_rhymes(word: str, n: int = 10) -> str:
    try:
        url = f"https://api.datamuse.com/words?rel_rhy={urllib.parse.quote(word)}&max={n}"
        req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            results = json.loads(r.read())
        if not results:
            return f"No rhymes found for '{word}', sir."
        words = [r["word"] for r in results]
        return f"Words that rhyme with '{word}': {', '.join(words)}, sir."
    except Exception as e:
        return f"Rhyme search error: {e}"


# ── Etymology ─────────────────────────────────────────────────────────────────
@register(
    name="word_etymology",
    description="Get the meaning and part of speech of a word (concise etymology-style info).",
    parameters={"type": "object", "properties": {
        "word": {"type": "string"},
    }, "required": ["word"]},
)
def word_etymology(word: str) -> str:
    entries = _fetch(word)
    if not entries or not isinstance(entries, list):
        return f"No information found for '{word}', sir."
    out = []
    for entry in entries[:1]:
        for meaning in entry.get("meanings", []):
            pos  = meaning.get("partOfSpeech", "")
            defs = meaning.get("definitions", [])[:2]
            if defs:
                out.append(f"[{pos}] {defs[0].get('definition', '')}")
    origin = entries[0].get("origin", "")
    if origin:
        out.append(f"Origin: {origin}")
    return "\n".join(out) if out else f"No etymology for '{word}', sir."
