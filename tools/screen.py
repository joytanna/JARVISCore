"""Screen awareness — screenshot + vision model analysis."""
import base64, io
from tools.registry import register
import config


def _grab_b64() -> str:
    from PIL import ImageGrab
    img = ImageGrab.grab()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _analyse_anthropic(b64: str, query: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": "image/png", "data": b64}},
                {"type": "text", "text": query},
            ],
        }],
    )
    return resp.content[0].text.strip()


def _analyse_groq(b64: str, query: str) -> str:
    from groq import Groq
    client = Groq(api_key=config.GROQ_API_KEY)
    resp = client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url",
                 "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": query},
            ],
        }],
    )
    return resp.choices[0].message.content.strip()


def _analyse_ocr(b64: str) -> str:
    import pytesseract, base64, io
    from PIL import Image
    img = Image.open(io.BytesIO(base64.b64decode(b64)))
    text = pytesseract.image_to_string(img).strip()
    return f"Screen text (OCR):\n{text[:1500]}" if text else "No readable text detected on screen."


@register(
    name="read_screen",
    description="Take a screenshot and analyse what's on screen, or answer a question about it",
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string",
                      "description": "What to look for or ask about the screen (default: describe what's visible)"},
        },
    },
)
def read_screen(query: str = "Describe concisely what is on the screen right now.") -> str:
    try:
        b64 = _grab_b64()
    except Exception as e:
        return f"Could not take screenshot: {e}"

    if config.ANTHROPIC_API_KEY:
        try:
            return _analyse_anthropic(b64, query)
        except Exception as e:
            pass  # fall through

    if config.GROQ_API_KEY:
        try:
            return _analyse_groq(b64, query)
        except Exception:
            pass

    try:
        return _analyse_ocr(b64)
    except Exception:
        pass

    return "No vision model available. Add ANTHROPIC_API_KEY to .env for screen reading, sir."
