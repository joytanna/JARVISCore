"""Clipboard read, write, and AI-powered processing."""
from tools.registry import register
import config


def _get():
    try:
        import pyperclip
        return pyperclip.paste()
    except ImportError:
        import subprocess
        r = subprocess.run(
            ["powershell", "-Command", "Get-Clipboard"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        return r.stdout.strip()


def _set(text: str):
    try:
        import pyperclip
        pyperclip.copy(text)
    except ImportError:
        import subprocess
        escaped = text.replace('"', '`"')
        subprocess.run(
            ["powershell", "-Command", f'Set-Clipboard -Value "{escaped}"'],
            capture_output=True,
        )


@register(
    name="read_clipboard",
    description="Read the current clipboard contents",
    parameters={"type": "object", "properties": {}},
)
def read_clipboard() -> str:
    text = _get()
    if not text:
        return "Clipboard is empty, sir."
    preview = text[:500]
    suffix = "..." if len(text) > 500 else ""
    return f"Clipboard contents:\n{preview}{suffix}"


@register(
    name="process_clipboard",
    description="Read clipboard and process it with an AI instruction (summarise, translate, fix grammar, etc.)",
    parameters={
        "type": "object",
        "properties": {
            "instruction": {"type": "string",
                            "description": "What to do with the clipboard text, e.g. 'summarise', 'translate to Hindi', 'fix grammar'"},
        },
        "required": ["instruction"],
    },
)
def process_clipboard(instruction: str) -> str:
    text = _get()
    if not text:
        return "Clipboard is empty, sir."
    from brain.core import get_brain
    brain = get_brain()
    prompt = f"{instruction}:\n\n{text[:3000]}"
    result = brain.quick(prompt, max_tokens=500)
    return result


@register(
    name="copy_to_clipboard",
    description="Copy a given text string to the clipboard",
    parameters={
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
)
def copy_to_clipboard(text: str) -> str:
    try:
        _set(text)
        return f"Copied to clipboard, sir."
    except Exception as e:
        return f"Clipboard write error: {e}"
