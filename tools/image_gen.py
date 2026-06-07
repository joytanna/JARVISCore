"""
AI image generation — Pollinations.ai (completely free, no API key required).
Falls back to DALL-E if OPENAI_API_KEY is set in .env.
"""
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

import config
from tools.registry import register

_SAVE_DIR = config.MEMORY_DIR / "generated_images"

_MODELS = {
    "flux":       "flux",           # photorealistic
    "turbo":      "turbo",          # fast
    "flux-realism": "flux-realism", # hyper-real
}


def _pollinations(prompt: str, width: int, height: int, model: str) -> bytes:
    encoded = urllib.parse.quote(prompt)
    seed = int(time.time()) % 99999
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={width}&height={height}&model={model}"
        f"&nologo=true&seed={seed}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "JARVIS/1.0"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        return resp.read()


def _dalle(prompt: str, size: str = "1024x1024") -> bytes:
    import openai
    client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    resp = client.images.generate(prompt=prompt, n=1, size=size)
    img_url = resp.data[0].url
    req = urllib.request.Request(img_url, headers={"User-Agent": "JARVIS/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


@register(
    name="generate_image",
    description="Generate an AI image from a text description. Opens the result automatically.",
    parameters={
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "Detailed description of the image to generate"},
            "style":  {"type": "string",  "description": "Style: realistic, artistic, or fast (default: realistic)"},
            "width":  {"type": "integer", "description": "Width in pixels (default 1024)"},
            "height": {"type": "integer", "description": "Height in pixels (default 1024)"},
        },
        "required": ["prompt"],
    },
)
def generate_image(prompt: str, style: str = "realistic", width: int = 1024, height: int = 1024) -> str:
    _SAVE_DIR.mkdir(parents=True, exist_ok=True)

    style_map = {"realistic": "flux-realism", "artistic": "flux", "fast": "turbo"}
    model = style_map.get(style.lower(), "flux-realism")

    # Safe filename
    safe = "".join(c if c.isalnum() or c in " _-" else "" for c in prompt[:50]).strip().replace(" ", "_")
    ts   = int(time.time())
    out_path = _SAVE_DIR / f"{ts}_{safe}.png"

    try:
        # Try DALL-E if key present
        if os.getenv("OPENAI_API_KEY"):
            try:
                data = _dalle(prompt)
                out_path.write_bytes(data)
                os.startfile(str(out_path))
                return f"Image generated with DALL-E and opened: {out_path.name}"
            except Exception:
                pass   # fall through to Pollinations

        # Pollinations (free fallback — always available)
        data = _pollinations(prompt, width, height, model)
        out_path.write_bytes(data)
        os.startfile(str(out_path))
        return f"Image generated and opened, sir. Saved as {out_path.name}"

    except Exception as e:
        return f"Image generation failed: {e}"


@register(
    name="list_generated_images",
    description="List all previously generated images.",
    parameters={"type": "object", "properties": {}},
)
def list_generated_images() -> str:
    _SAVE_DIR.mkdir(parents=True, exist_ok=True)
    imgs = sorted(_SAVE_DIR.glob("*.png"), reverse=True)[:10]
    if not imgs:
        return "No generated images yet, sir."
    lines = [f"• {p.name}" for p in imgs]
    return f"Last {len(imgs)} generated images:\n" + "\n".join(lines)


@register(
    name="open_last_image",
    description="Open the most recently generated image.",
    parameters={"type": "object", "properties": {}},
)
def open_last_image() -> str:
    _SAVE_DIR.mkdir(parents=True, exist_ok=True)
    imgs = sorted(_SAVE_DIR.glob("*.png"), reverse=True)
    if not imgs:
        return "No generated images found, sir."
    os.startfile(str(imgs[0]))
    return f"Opening {imgs[0].name}, sir."
