import json, time, urllib.request
import config

_SMART_TRIGGERS = {
    "research", "analyse", "analyze", "explain in detail", "write a", "create a",
    "build a", "generate", "debug", "refactor", "compare", "summarise", "summarize",
    "deep", "comprehensive", "step by step", "how does", "why does", "what causes",
}

# Tool-needing keywords — if present, run the full agent loop
TOOL_TRIGGERS = {
    "weather", "stock", "price", "crypto", "search", "news", "headline",
    "wikipedia", "look up", "find out", "check", "fetch", "open", "run",
    "execute", "shell", "file", "folder", "remember", "recall", "forget",
    "install", "process", "clipboard", "browse", "google",
    "email", "gmail", "inbox", "send email", "mail",
    "whatsapp", "sms", "text message", "phone", "message",
    "qr", "remote", "scan",
    "enroll", "voice auth", "voice authentication",
    "call", "contact", "contacts", "dial",
    "fullscreen", "full screen", "open ui", "close ui", "dashboard",
    "remind", "reminder", "alarm", "alert", "in 10 minutes", "at ",
    "briefing", "good morning", "morning briefing", "daily brief",
    "screen", "what's on", "what is on", "read screen", "screenshot",
    "open ", "close ", "switch to", "launch ",
    "clipboard", "copy", "paste", "summarise clipboard",
    "summarise file", "summarize file", "open file", "read file",
    "shutdown", "restart", "sleep", "lock", "hibernate",
    "volume", "mute", "brightness", "wifi", "wi-fi", "monitor",
    # context & meeting
    "what am i working", "what are you working", "context", "what's on my screen",
    "meeting", "record meeting", "start meeting", "stop meeting", "transcribe",
    "action items", "meeting summary",
    # password vault
    "password", "vault", "credentials", "login for", "password for",
    "store password", "get password", "list password",
    # translation
    "translate", "translation", "translat", "in spanish", "in french",
    "in hindi", "in german", "in japanese", "in arabic", "convert to",
    "speak in",
    # code execution
    "run code", "execute code", "run python", "python code", "run script",
    "calculate", "compute", "evaluate",
    # image generation
    "generate image", "create image", "draw me", "draw a", "generate a picture",
    "make an image", "imagine ", "create a picture",
    # desktop automation
    "click on", "click the", "type ", "press hotkey", "automate",
    "mouse ", "drag ", "scroll ", "take a screenshot",
    # google
    "connect google", "google account", "oauth",
    # habits
    "habit", "streak", "complete habit", "habits today",
    # pomodoro
    "pomodoro", "timer", "break time",
    # world clock / timezone
    "time in ", "timezone", "world clock", "convert timezone",
    # dictionary
    "define ", "synonym", "antonym", "rhyme", "word of the day", "etymology",
    # phone
    "phone link", "phone remote", "connect phone",
    # windows
    "windows contacts", "installed apps", "default assistant", "windows startup",
    "register jarvis", "open windows", "windows settings",
}

# Pre-initialise clients once — avoid per-call overhead
_groq_client   = None
_gemini_client = None


def _get_groq():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=config.GROQ_API_KEY)
    return _groq_client


_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
]


def _get_gemini():
    """Return (google.genai.Client, model_name) or (None, None)."""
    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client   # already (client, model) tuple
    key = getattr(config, "GEMINI_API_KEY", "")
    if not key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=key)
        # Probe for the best available model
        preferred = getattr(config, "GEMINI_MODEL", "gemini-2.0-flash")
        for model_name in [preferred] + [m for m in _GEMINI_MODELS if m != preferred]:
            try:
                resp = client.models.generate_content(
                    model=model_name, contents="hi",
                    config={"max_output_tokens": 3},
                )
                _ = resp.text   # raises if model unavailable
                config.GEMINI_MODEL = model_name
                _gemini_client = (client, model_name)
                print(f"[Brain] Gemini model: {model_name}")
                return _gemini_client
            except Exception:
                continue
        return None
    except ImportError:
        return None
    except Exception:
        return None


def _needs_smart(messages: list) -> bool:
    last = " ".join(m.get("content", "") for m in messages[-3:]).lower()
    return any(t in last for t in _SMART_TRIGGERS)


def needs_tool(text: str) -> bool:
    lower = text.lower()
    return any(t in lower for t in TOOL_TRIGGERS)


class JarvisBrain:
    def __init__(self):
        self._backend  = "groq"
        self._backends = []   # ordered preference list
        self._detect_backend()

    def _detect_backend(self):
        """Prefer Gemini (free+unlimited) → Groq → Anthropic → Ollama."""
        backends = []
        # Gemini first — free, 1500 RPD, multimodal
        if getattr(config, "GEMINI_API_KEY", ""):
            pair = _get_gemini()
            if pair is not None:
                backends.append("gemini")
        if config.GROQ_API_KEY:
            try:
                import groq  # noqa
                _get_groq()
                backends.append("groq")
            except ImportError:
                pass
        if config.ANTHROPIC_API_KEY:
            try:
                import anthropic  # noqa
                backends.append("anthropic")
            except ImportError:
                pass
        if not backends:
            backends.append("ollama")
        self._backends = backends
        self._backend  = backends[0]
        print(f"[Brain] {self._backend.upper()} ready  (available: {', '.join(backends)})")

    def chat(self, messages: list, system: str = "", smart: bool = False,
             max_tokens: int = 400) -> str:
        sys_prompt = system or config.PERSONA
        full = [{"role": "system", "content": sys_prompt}] + messages
        # Try backends in order; fall back on rate-limit or error
        for backend in self._backends:
            try:
                if backend == "groq":
                    r = self._groq_chat(full, smart, max_tokens)
                elif backend == "gemini":
                    r = self._gemini_chat(messages, max_tokens)
                elif backend == "anthropic":
                    r = self._anthropic_chat(messages, sys_prompt, max_tokens)
                else:
                    r = self._ollama_chat(full)
                if r and not r.startswith("[") and "rate limit" not in r.lower():
                    return r
                # Rate-limited — try next backend
            except Exception:
                pass
        return "[AI unavailable — all backends failed]"

    def quick(self, prompt: str, max_tokens: int = 200) -> str:
        """Single fast turn — no history, fast model, tight token limit."""
        messages = [
            {"role": "system", "content": config.PERSONA},
            {"role": "user",   "content": prompt},
        ]
        # quick() always tries Groq fast model first
        try:
            r = self._groq_chat(messages, smart=False, max_tokens=max_tokens)
            if r and not r.startswith("["):
                return r
        except Exception:
            pass
        # Fall back to Gemini if Groq fails
        try:
            r = self._gemini_chat([{"role": "user", "content": prompt}], max_tokens)
            if r and not r.startswith("["):
                return r
        except Exception:
            pass
        return self._groq_chat(messages, smart=False, max_tokens=max_tokens)

    def _gemini_chat(self, messages: list, max_tokens: int = 400) -> str:
        """Google Gemini — free, 1500 RPD, multimodal (google-genai SDK)."""
        try:
            pair = _get_gemini()
            if pair is None:
                return "[Gemini not configured]"
            client, model_name = pair
            # Build Gemini contents list from message history
            contents = []
            for m in messages:
                role = "model" if m["role"] == "assistant" else "user"
                contents.append({"role": role, "parts": [{"text": m["content"]}]})
            # Include system persona as a leading user/model exchange
            system_turn = [
                {"role": "user",  "parts": [{"text": "System: " + config.PERSONA}]},
                {"role": "model", "parts": [{"text": "Understood. I will follow these instructions."}]},
            ]
            from google.genai import types
            resp = client.models.generate_content(
                model=model_name,
                contents=system_turn + contents,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=0.65,
                ),
            )
            return resp.text.strip()
        except Exception as e:
            global _gemini_client
            _gemini_client = None   # reset so next call re-probes
            return f"[Gemini error] {e}"

    def _groq_chat(self, messages: list, smart: bool = False,
                   max_tokens: int = 400) -> str:
        try:
            client = _get_groq()
            model = config.GROQ_MODEL if (smart or _needs_smart(messages)) else config.GROQ_MODEL_FAST
            resp = client.chat.completions.create(
                model=model, messages=messages,
                max_tokens=max_tokens, temperature=0.6,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"[Groq error] {e}"

    def _anthropic_chat(self, messages: list, system: str,
                        max_tokens: int = 400) -> str:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
            resp = client.messages.create(
                model=config.CLAUDE_MODEL, max_tokens=max_tokens,
                system=system, messages=messages,
            )
            return resp.content[0].text.strip()
        except Exception as e:
            return f"[Anthropic error] {e}"

    def _ollama_chat(self, messages: list) -> str:
        try:
            url = "http://localhost:11434/api/chat"
            payload = json.dumps({"model": "llama3", "messages": messages, "stream": False}).encode()
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())["message"]["content"].strip()
        except Exception as e:
            return f"[Ollama error] {e}"


_brain = None


def get_brain() -> JarvisBrain:
    global _brain
    if _brain is None:
        _brain = JarvisBrain()
    return _brain
