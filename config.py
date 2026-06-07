import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

NAME = "JARVIS"
PERSONA = (
    "You are a personal AI assistant. "
    "Calm. British. Dry wit. Never flustered. Never verbose. "
    "Address the user as 'sir'. One or two sentences unless detail is required. "
    "You have tools and a swarm of specialist agents. Use them without being asked. "
    "Use remember_fact to store anything important you learn about the user. "
    "Use recall_fact to check what you already know about them."
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

GROQ_MODEL = "llama-3.3-70b-versatile"
GROQ_MODEL_FAST = "llama-3.1-8b-instant"
CLAUDE_MODEL = "claude-sonnet-4-6"
GEMINI_MODEL = "gemini-2.5-flash"

# Just "jarvis" — no "hey" prefix required
WAKE_WORDS = ["jarvis"]
SILENCE_SECS = 1.5
SAMPLE_RATE = 16000
API_PORT = 8100
AGENT_MAX_STEPS = 5

BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"

# LemonSqueezy — set after creating your store at lemonsqueezy.com
LEMONSQUEEZY_API_KEY   = os.getenv("LEMONSQUEEZY_API_KEY",   "")
LEMONSQUEEZY_STORE_ID  = os.getenv("LEMONSQUEEZY_STORE_ID",  "")
LS_PRODUCT_PRO_MONTHLY = os.getenv("LS_PRODUCT_PRO_MONTHLY", "")
LS_PRODUCT_PRO_ANNUAL  = os.getenv("LS_PRODUCT_PRO_ANNUAL",  "")
LS_PRODUCT_LIFETIME    = os.getenv("LS_PRODUCT_LIFETIME",     "")
LS_LINK_PRO_MONTHLY    = os.getenv("LS_LINK_PRO_MONTHLY",    "https://jarvisai.lemonsqueezy.com/buy/pro-monthly")
LS_LINK_PRO_ANNUAL     = os.getenv("LS_LINK_PRO_ANNUAL",     "https://jarvisai.lemonsqueezy.com/buy/pro-annual")
LS_LINK_LIFETIME       = os.getenv("LS_LINK_LIFETIME",        "https://jarvisai.lemonsqueezy.com/buy/lifetime")

ADMIN_EMAIL       = os.getenv("ADMIN_EMAIL", "joytanna21@gmail.com")
ADMIN_DEVICE_CODE = os.getenv("ADMIN_DEVICE_CODE", "JARVIS_OWNER_2026")
GMAIL_ADDRESS     = os.getenv("GMAIL_ADDRESS", "joytanna21@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
GMAIL_USER         = os.getenv("GMAIL_ADDRESS", "joytanna21@gmail.com")
UPI_ID             = os.getenv("UPI_ID", "joytanna21@yesfam")
APP_VERSION        = "1.0"
MY_PHONE = os.getenv("MY_PHONE", "7666639083")
FAST2SMS_KEY = os.getenv("FAST2SMS_KEY", "")
