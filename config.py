import os
from pathlib import Path

# Sanitize NO_PROXY for httpx compatibility (removes [::1] and <local> which crash httpx url parsing)
if "NO_PROXY" in os.environ:
    cleaned_no_proxy = ",".join([
        p for p in os.environ["NO_PROXY"].split(",")
        if p.strip() not in ("[::1]", "::1", "<local>")
    ])
    os.environ["NO_PROXY"] = cleaned_no_proxy
if "no_proxy" in os.environ:
    cleaned_no_proxy = ",".join([
        p for p in os.environ["no_proxy"].split(",")
        if p.strip() not in ("[::1]", "::1", "<local>")
    ])
    os.environ["no_proxy"] = cleaned_no_proxy

BASE_DIR = Path(__file__).resolve().parent


# Telegram Bot Token
BOT_TOKEN = os.getenv("BOT_TOKEN", "your_telegram_bot_token_here")
BOT_USERNAME = os.getenv("BOT_USERNAME", "warok18bot")

# Web App Base URL (URL where Mini App is hosted)
WEBAPP_URL = os.getenv("WEBAPP_URL", "http://localhost:8000")

# Database Path
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "splitbill.db"))

# Server settings
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", 8000))

# Proverkacheka API Token (for official FNS receipt lookups by QR)
PROVERKACHEKA_TOKEN = os.getenv("PROVERKACHEKA_TOKEN", "your_proverkacheka_token_here")

