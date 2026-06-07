"""
Security middleware for JARVIS API:
- Sliding-window rate limiter (per IP, no external deps)
- Input sanitizer / validator
- Auth enforcement
- Request size guard
- Security headers
- Secret leak scanner
"""
import hashlib
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


# ── Rate Limiter ───────────────────────────────────────────────────────────────
class _SlidingWindow:
    """In-memory sliding-window rate limiter, thread-safe without locks (GIL)."""
    def __init__(self):
        self._log: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, key: str, max_req: int, window_s: int) -> bool:
        now  = time.monotonic()
        hist = self._log[key]
        # Prune expired
        self._log[key] = [t for t in hist if now - t < window_s]
        if len(self._log[key]) >= max_req:
            return False
        self._log[key].append(now)
        return True

    def cleanup(self):
        """Call periodically to free memory (optional)."""
        now = time.monotonic()
        stale = [k for k, v in self._log.items()
                 if not v or now - v[-1] > 3600]
        for k in stale:
            del self._log[k]


_limiter = _SlidingWindow()

# Rate limit profiles (max_requests, window_seconds)
RATE_PROFILES = {
    "chat":    (20,  60),   # 20 msgs/min  per IP
    "upload":  (10,  60),   # 10 uploads/min
    "auth":    (5,   30),   # 5 login attempts per 30s
    "tool":    (60,  60),   # 60 tool calls/min
    "default": (120, 60),   # 120 misc requests/min
}


def rate_limit(request: Request, profile: str = "default") -> None:
    """Call inside an endpoint to enforce rate limiting. Raises 429 if exceeded."""
    ip       = request.client.host if request.client else "unknown"
    max_r, w = RATE_PROFILES.get(profile, RATE_PROFILES["default"])
    key      = f"{ip}:{profile}"
    if not _limiter.is_allowed(key, max_r, w):
        raise HTTPException(
            status_code=429,
            detail=f"Too many requests. Limit: {max_r}/{w}s. Try again shortly.",
            headers={"Retry-After": str(w)},
        )


# ── Security Headers Middleware ────────────────────────────────────────────────
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"]    = "nosniff"
        response.headers["X-Frame-Options"]            = "SAMEORIGIN"
        response.headers["X-XSS-Protection"]           = "1; mode=block"
        response.headers["Referrer-Policy"]            = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"]         = "camera=(), microphone=(self), geolocation=(self)"
        # Strict CSP — allow local resources + trusted CDNs
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "          # inline JS needed for app.html
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https://api.qrserver.com https://api.coingecko.com; "
            "connect-src 'self' ws: wss: https://api.qrserver.com https://api.coingecko.com "
            "https://api.exchangerate-api.com https://api.dictionaryapi.dev "
            "https://en.wikipedia.org https://haveibeenpwned.com https://api.pwnedpasswords.com;"
        )
        response.headers["Content-Security-Policy"] = csp
        return response


# ── Request Size Guard ─────────────────────────────────────────────────────────
MAX_BODY_SIZES = {
    "/api/upload": 50 * 1024 * 1024,   # 50 MB for file uploads
    "/api/chat":    32 * 1024,           # 32 KB for chat
    "/api/tool":    16 * 1024,           # 16 KB for tool calls
}
DEFAULT_MAX_BODY = 64 * 1024  # 64 KB default

class RequestSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path     = request.url.path
        max_size = MAX_BODY_SIZES.get(path, DEFAULT_MAX_BODY)
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > max_size:
            return JSONResponse(
                {"error": f"Request too large. Max: {max_size // 1024} KB"},
                status_code=413,
            )
        return await call_next(request)


# ── Input Sanitizer ────────────────────────────────────────────────────────────
_DANGEROUS_PATTERNS = [
    re.compile(r"<script[\s\S]*?>[\s\S]*?</script>", re.I),
    re.compile(r"javascript\s*:", re.I),
    re.compile(r"on\w+\s*=", re.I),              # onclick=, onerror=, etc.
    re.compile(r"\x00"),                           # Null bytes
    re.compile(r"[\x01-\x08\x0b\x0c\x0e-\x1f]"), # Control chars
]

def sanitize_text(value: str, max_len: int = 4000) -> str:
    """Strip dangerous patterns and enforce max length."""
    if not isinstance(value, str):
        raise ValueError("Expected a string")
    value = value[:max_len]
    for pat in _DANGEROUS_PATTERNS:
        value = pat.sub("", value)
    return value.strip()

def sanitize_dict(data: dict, rules: dict[str, int] | None = None) -> dict:
    """
    Sanitize all string values in a dict.
    rules = {field_name: max_length}
    """
    rules = rules or {}
    out   = {}
    for k, v in data.items():
        if isinstance(v, str):
            out[k] = sanitize_text(v, rules.get(k, 4000))
        elif isinstance(v, dict):
            out[k] = sanitize_dict(v, rules)
        elif isinstance(v, list):
            out[k] = [sanitize_text(i, 2000) if isinstance(i, str) else i for i in v]
        else:
            out[k] = v
    return out


# ── Auth Dependency ────────────────────────────────────────────────────────────
def require_auth(request: Request) -> str:
    """FastAPI dependency: raise 401 if no valid token."""
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    if not token:
        # Check cookie as fallback
        token = request.cookies.get("jarvis_token", "")
    if token in ("local", ""):
        # pywebview local bypass — only allow from localhost
        host = request.client.host if request.client else ""
        if host in ("127.0.0.1", "::1", "localhost"):
            return "local"
    try:
        from api.auth_manager import verify_token
        if verify_token(token):
            return token
    except Exception:
        pass
    raise HTTPException(status_code=401, detail="Unauthorised. Please log in.")


# ── Secret Leak Scanner ────────────────────────────────────────────────────────
_SECRET_PATTERNS = {
    "Groq API Key":     re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    "OpenAI API Key":   re.compile(r"sk-[A-Za-z0-9]{20,}"),
    "GitHub Token":     re.compile(r"ghp_[A-Za-z0-9]{36}"),
    "JWT Secret":       re.compile(r"(?i)jwt.{0,10}secret.{0,10}=.{8,}"),
    "Generic API Key":  re.compile(r"(?i)api[_\-]?key\s*[:=]\s*['\"]?[A-Za-z0-9+/]{20,}"),
}

def scan_for_secrets(text: str) -> list[str]:
    """Return list of secret type names found in text."""
    found = []
    for name, pat in _SECRET_PATTERNS.items():
        if pat.search(text):
            found.append(name)
    return found

def scan_response_for_leaks(response_text: str) -> str:
    """Replace potential secrets in outgoing responses with [REDACTED]."""
    for name, pat in _SECRET_PATTERNS.items():
        response_text = pat.sub(f"[REDACTED:{name}]", response_text)
    return response_text


# ── Pydantic Request Models ────────────────────────────────────────────────────
from pydantic import BaseModel, Field, field_validator

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    token:   str = Field(default="", max_length=512)

    @field_validator("message")
    @classmethod
    def clean_message(cls, v: str) -> str:
        return sanitize_text(v, 4000)

class ToolRequest(BaseModel):
    tool: str = Field(..., min_length=1, max_length=64,
                      pattern=r'^[a-z_][a-z0-9_]*$')
    args: dict = Field(default_factory=dict)

    @field_validator("tool")
    @classmethod
    def validate_tool(cls, v: str) -> str:
        # Only lowercase letters and underscores
        if not re.match(r'^[a-z_][a-z0-9_]*$', v):
            raise ValueError("Invalid tool name")
        return v

    @field_validator("args")
    @classmethod
    def clean_args(cls, v: dict) -> dict:
        return sanitize_dict(v)

class AuthSetupRequest(BaseModel):
    name:     str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=4, max_length=128)
    email:    str = Field(default="", max_length=254)
    phone:    str = Field(default="", max_length=20,
                          pattern=r'^[\d\s\+\-\(\)]*$')

    @field_validator("name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return sanitize_text(v, 100)

class AuthLoginRequest(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)


# ── .gitignore helper ──────────────────────────────────────────────────────────
_GITIGNORE_ENTRIES = [
    ".env", "*.env",
    "memory/", "memory/**",
    "static/icon-*.png",
    "__pycache__/", "*.pyc", "*.pyo",
    ".jwt_secret",
    "google_token.json",
    "google_credentials.json",
    "vault.enc",
    ".vault_key",
    ".github_token",
    ".telegram_token",
    ".telegram_chat_id",
    "auth.json",
    "*.log",
    "dist/", "build/",
    ".vscode/settings.json",
]

def ensure_gitignore():
    gi = Path(__file__).parent.parent / ".gitignore"
    existing = gi.read_text() if gi.exists() else ""
    added    = []
    for entry in _GITIGNORE_ENTRIES:
        if entry not in existing:
            added.append(entry)
    if added:
        with gi.open("a") as f:
            f.write("\n# JARVIS security — auto-added\n")
            f.write("\n".join(added) + "\n")
    return len(added)


# Run gitignore check on import
try:
    n = ensure_gitignore()
    if n > 0:
        print(f"[Security] Added {n} entries to .gitignore")
except Exception:
    pass
