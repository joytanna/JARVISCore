"""
Real-time translation — uses deep_translator (Google Translate backend) with LLM fallback.
pip install deep-translator
"""
from tools.registry import register

# Common language codes for voice parsing
_LANG_ALIASES = {
    "hindi": "hi", "spanish": "es", "french": "fr", "german": "de",
    "chinese": "zh-CN", "japanese": "ja", "arabic": "ar", "russian": "ru",
    "portuguese": "pt", "italian": "it", "korean": "ko", "dutch": "nl",
    "bengali": "bn", "tamil": "ta", "telugu": "te", "marathi": "mr",
    "gujarati": "gu", "punjabi": "pa", "urdu": "ur", "english": "en",
    "turkish": "tr", "polish": "pl", "swedish": "sv", "norwegian": "no",
    "danish": "da", "finnish": "fi", "greek": "el", "hebrew": "iw",
    "thai": "th", "vietnamese": "vi", "indonesian": "id", "malay": "ms",
}

_auto_translate: bool = False
_auto_to: str = "en"
_auto_from: str = "auto"


def _resolve_lang(lang: str) -> str:
    """Convert language name to code."""
    return _LANG_ALIASES.get(lang.lower().strip(), lang.lower().strip())


def _do_translate(text: str, to_lang: str, from_lang: str = "auto") -> str:
    to_code   = _resolve_lang(to_lang)
    from_code = _resolve_lang(from_lang) if from_lang != "auto" else "auto"
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source=from_code, target=to_code).translate(text)
        return result or text
    except ImportError:
        # LLM fallback
        from brain.core import get_brain
        lang_name = to_lang.title()
        return get_brain().quick(
            f"Translate the following text to {lang_name}. Reply with ONLY the translation, nothing else.\n\n{text}",
            max_tokens=300,
        )
    except Exception as e:
        # LLM fallback on any error
        from brain.core import get_brain
        return get_brain().quick(
            f"Translate to {to_lang}: {text}",
            max_tokens=300,
        )


@register(
    name="translate",
    description="Translate text to another language.",
    parameters={
        "type": "object",
        "properties": {
            "text":      {"type": "string", "description": "Text to translate"},
            "to_lang":   {"type": "string", "description": "Target language (e.g. 'Hindi', 'fr', 'Spanish')"},
            "from_lang": {"type": "string", "description": "Source language (default: auto-detect)"},
        },
        "required": ["text", "to_lang"],
    },
)
def translate(text: str, to_lang: str, from_lang: str = "auto") -> str:
    result = _do_translate(text, to_lang, from_lang)
    to_name = to_lang.title()
    return f"[{to_name}] {result}"


@register(
    name="set_auto_translate",
    description="Enable or disable automatic translation of all JARVIS responses into a chosen language.",
    parameters={
        "type": "object",
        "properties": {
            "enable":    {"type": "boolean"},
            "to_lang":   {"type": "string", "description": "Target language when enabling"},
            "from_lang": {"type": "string", "description": "Source language (default: auto)"},
        },
        "required": ["enable"],
    },
)
def set_auto_translate(enable: bool, to_lang: str = "en", from_lang: str = "auto") -> str:
    global _auto_translate, _auto_to, _auto_from
    _auto_translate = enable
    _auto_to   = to_lang
    _auto_from = from_lang
    if enable:
        return f"Auto-translation active: all responses will be translated to {to_lang.title()}, sir."
    return "Auto-translation disabled, sir."


@register(
    name="detect_language",
    description="Detect the language of a given text.",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
)
def detect_language(text: str) -> str:
    try:
        from deep_translator import GoogleTranslator
        # Use translate with verbose to detect
        from langdetect import detect
        lang = detect(text)
        # Find full name
        for name, code in _LANG_ALIASES.items():
            if code == lang or code.startswith(lang):
                return f"Detected language: {name.title()} ({lang})"
        return f"Detected language code: {lang}"
    except ImportError:
        from brain.core import get_brain
        return get_brain().quick(
            f"What language is this text written in? Reply with just the language name.\n\n{text}",
            max_tokens=20,
        )
    except Exception as e:
        return f"Detection error: {e}"


def get_auto_translate_settings() -> tuple[bool, str, str]:
    """Used by jarvis.py to optionally post-translate responses."""
    return _auto_translate, _auto_to, _auto_from
