"""
Random & Fun Tools — jokes, facts, quotes, dice rolls, coin flips, random names.
All from free public APIs with graceful fallbacks to built-in lists.
"""
import json
import random
import string
from urllib.request import urlopen, Request

from tools.registry import register


def _http_get(url: str, timeout: int = 6) -> str:
    req = Request(url, headers={"User-Agent": "JARVIS/1.0",
                                 "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


# ── Coin Flip ──────────────────────────────────────────────────────────────────
@register(
    name="flip_coin",
    description="Flip a coin (or multiple coins).",
    parameters={"type": "object", "properties": {
        "times": {"type": "integer", "description": "How many flips (default 1)"},
    }},
)
def flip_coin(times: int = 1) -> str:
    if times < 1 or times > 100:
        times = 1
    results = [random.choice(["Heads", "Tails"]) for _ in range(times)]
    if times == 1:
        return f"[Coin] {results[0]}, sir."
    h = results.count("Heads")
    t = results.count("Tails")
    preview = ", ".join(results[:10]) + ("..." if times > 10 else "")
    return f"[Coin] {times} flips - Heads: {h}, Tails: {t}\n{preview}"


# ── Dice Roll ─────────────────────────────────────────────────────────────────
@register(
    name="roll_dice",
    description="Roll one or more dice. Supports standard RPG notation like 2d6, 1d20, 3d8.",
    parameters={"type": "object", "properties": {
        "notation": {"type": "string",
                     "description": "Dice notation: '1d6' (one 6-sided), '2d20' (two 20-sided), etc."},
    }, "required": ["notation"]},
)
def roll_dice(notation: str) -> str:
    import re
    m = re.match(r'^(\d{1,3})d(\d{1,4})([+-]\d+)?$', notation.strip().lower())
    if not m:
        return (f"Invalid notation '{notation}'. Use format like '2d6', '1d20+3', sir.")
    n    = int(m.group(1))
    sides= int(m.group(2))
    mod  = int(m.group(3) or 0)
    if n > 100 or sides > 10000:
        return "Too many dice, sir."
    rolls = [random.randint(1, sides) for _ in range(n)]
    total = sum(rolls) + mod
    if n == 1:
        return f"🎲 d{sides}: {rolls[0]}{f' + {mod} = {total}' if mod else ''}, sir."
    r_str = f"[{', '.join(str(r) for r in rolls)}]"
    return (f"🎲 {notation}: {r_str}\n"
            f"Sum: {sum(rolls)}{f' + {mod} = {total}' if mod else f' = {total}'}, sir.")


# ── Random Number ─────────────────────────────────────────────────────────────
@register(
    name="random_number",
    description="Generate a random integer or float in a given range.",
    parameters={"type": "object", "properties": {
        "min":   {"type": "number", "description": "Minimum value (default 1)"},
        "max":   {"type": "number", "description": "Maximum value (default 100)"},
        "float": {"type": "boolean","description": "Return a decimal number (default false)"},
    }},
)
def random_number(min: float = 1, max: float = 100, float: bool = False) -> str:
    if min > max:
        min, max = max, min
    if float:
        n = random.uniform(min, max)
        return f"🎲 Random number: {n:.4f}, sir."
    n = random.randint(int(min), int(max))
    return f"🎲 Random number: {n}, sir."


# ── Random Choice ─────────────────────────────────────────────────────────────
@register(
    name="random_choice",
    description="Pick a random item from a list. Great for decisions.",
    parameters={"type": "object", "properties": {
        "options": {"type": "string",
                    "description": "Comma-separated list of options, e.g. 'pizza, burgers, sushi'"},
        "count":   {"type": "integer", "description": "How many to pick (default 1)"},
    }, "required": ["options"]},
)
def random_choice(options: str, count: int = 1) -> str:
    items = [o.strip() for o in options.split(",") if o.strip()]
    if not items:
        return "No options provided, sir."
    count = min(count, len(items))
    picks = random.sample(items, count)
    if count == 1:
        return f"[>] I choose: **{picks[0]}**, sir."
    return f"[>] Chosen: {', '.join(picks)}, sir."


# ── Joke ──────────────────────────────────────────────────────────────────────
_FALLBACK_JOKES = [
    ("Why do programmers prefer dark mode?", "Because light attracts bugs."),
    ("Why did the AI go to therapy?", "Too many deep issues."),
    ("How do you comfort a JavaScript bug?", "You console it."),
    ("Why did the Python programmer wear glasses?", "He couldn't C."),
    ("What's a computer's favourite snack?", "Microchips."),
    ("Why do Java developers wear glasses?", "Because they don't C#."),
    ("What did the RAM say to the CPU?", "You cache me if you can."),
    ("Why is the IT department always calm?", "They have a lot of Ctrl."),
]

@register(
    name="tell_joke",
    description="Tell a random joke (always safe/clean).",
    parameters={"type": "object", "properties": {
        "category": {"type": "string",
                     "description": "Category: programming, pun, misc (default: programming)"},
    }},
)
def tell_joke(category: str = "programming") -> str:
    try:
        cat_map = {"programming": "Programming", "pun": "Pun", "misc": "Misc"}
        cat = cat_map.get(category.lower(), "Programming")
        url = (f"https://v2.jokeapi.dev/joke/{cat}"
               f"?safe-mode&blacklistFlags=nsfw,racist,sexist,explicit,political")
        data = json.loads(_http_get(url))
        if data.get("type") == "twopart":
            return f"😄 {data['setup']}\n\n... {data['delivery']}"
        return f"😄 {data.get('joke', 'Joke unavailable.')}"
    except Exception:
        q, a = random.choice(_FALLBACK_JOKES)
        return f"😄 {q}\n\n... {a}"


# ── Random Fact ───────────────────────────────────────────────────────────────
_FALLBACK_FACTS = [
    "Honey never spoils — archaeologists found 3,000-year-old honey in Egyptian tombs still edible.",
    "A group of flamingos is called a 'flamboyance'.",
    "Cleopatra lived closer in time to the Moon landing than to the construction of the Great Pyramid.",
    "Oxford University is older than the Aztec Empire.",
    "A single strand of spaghetti is called a 'spaghetto'.",
    "The inventor of the Pringles can is buried in one.",
    "Crows can recognise human faces and hold grudges.",
    "The total weight of ants on Earth roughly equals the total weight of humans.",
    "Sharks are older than trees. Sharks are ~450M years old; trees ~350M years.",
    "There are more possible chess games than atoms in the observable universe.",
]

@register(
    name="random_fact",
    description="Get a random interesting or surprising fact.",
    parameters={"type": "object", "properties": {}},
)
def random_fact() -> str:
    try:
        data = json.loads(_http_get("https://uselessfacts.jsph.pl/api/v2/facts/random?language=en"))
        return f"🧠 {data.get('text', random.choice(_FALLBACK_FACTS))}"
    except Exception:
        return f"🧠 {random.choice(_FALLBACK_FACTS)}"


# ── Random Quote ──────────────────────────────────────────────────────────────
_FALLBACK_QUOTES = [
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("In the middle of difficulty lies opportunity.", "Albert Einstein"),
    ("It does not matter how slowly you go as long as you do not stop.", "Confucius"),
    ("The future belongs to those who believe in the beauty of their dreams.", "Eleanor Roosevelt"),
    ("Success is not final, failure is not fatal: it is the courage to continue that counts.", "Churchill"),
    ("Simplicity is the ultimate sophistication.", "Leonardo da Vinci"),
    ("Life is what happens when you're busy making other plans.", "John Lennon"),
]

@register(
    name="random_quote",
    description="Get an inspirational or thought-provoking quote.",
    parameters={"type": "object", "properties": {
        "topic": {"type": "string", "description": "Optional topic: technology, life, success, etc."},
    }},
)
def random_quote(topic: str = "") -> str:
    try:
        url  = f"https://api.quotable.io/random{'?tags='+topic if topic else ''}"
        data = json.loads(_http_get(url))
        return f"💬 \"{data['content']}\"\n    — {data['author']}"
    except Exception:
        q, a = random.choice(_FALLBACK_QUOTES)
        return f"💬 \"{q}\"\n    — {a}"


# ── Magic 8-Ball ───────────────────────────────────────────────────────────────
_8BALL = [
    "It is certain.", "It is decidedly so.", "Without a doubt.",
    "Yes, definitely.", "You may rely on it.", "As I see it, yes.",
    "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
    "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
    "Cannot predict now.", "Concentrate and ask again.",
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.",
]

@register(
    name="magic_8ball",
    description="Ask the magic 8-ball a yes/no question.",
    parameters={"type": "object", "properties": {
        "question": {"type": "string", "description": "Your yes/no question"},
    }, "required": ["question"]},
)
def magic_8ball(question: str) -> str:
    answer = random.choice(_8BALL)
    return f"🎱 Question: {question}\n\nAnswer: {answer}"


# ── Random Password (pronounceable) ──────────────────────────────────────────
@register(
    name="random_word_combo",
    description="Generate a random memorable phrase, nickname, or project name.",
    parameters={"type": "object", "properties": {
        "style": {"type": "string",
                  "description": "Style: adjective-noun, code-name, project (default adjective-noun)"},
    }},
)
def random_word_combo(style: str = "adjective-noun") -> str:
    adjectives = ["swift","bright","calm","bold","keen","dark","golden","silver",
                  "cyber","quantum","silent","electric","magnetic","cosmic","iron",
                  "azure","crimson","jade","obsidian","phantom","shadow","neon"]
    nouns      = ["falcon","tiger","wave","storm","cipher","forge","nexus","orbit",
                  "spark","blade","echo","zenith","vortex","pulse","nova","raven",
                  "atlas","comet","prism","vector","titan","apex"]
    verbs      = ["code","build","craft","forge","launch","scale","sync","push"]

    s = style.lower()
    if "code" in s:
        result = f"{random.choice(adjectives).title()}{random.choice(nouns).title()}"
    elif "project" in s:
        result = f"Project {random.choice(adjectives).title()} {random.choice(nouns).title()}"
    else:
        num = random.randint(10, 999)
        result = f"{random.choice(adjectives)}-{random.choice(nouns)}-{num}"

    return f"🎲 {result}"
