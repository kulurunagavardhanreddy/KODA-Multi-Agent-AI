# backend/core/config.py
import os
import sys
import logging
from backend.config import GEMINI_API_KEY, NGROK_AUTH_TOKEN, NGROK_DOMAIN, GOOGLE_CLIENT_ID

logger = logging.getLogger(__name__)

# --- JWT Configuration ---
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    logger.warning("⚠️ CRITICAL WARNING: SECRET_KEY not found in .env. Using a static fallback key. Please set SECRET_KEY in production!")
    SECRET_KEY = "koda-dev-fallback-secret-key-change-me"

ALGORITHM = "HS256"

# --- LLM API Configuration ---
from backend.agents.supervisor import MISTRAL_API_BASE

# --- Dynamic Port Detection ---
PORT = int(os.getenv("PORT", 8000))
if "--port" in sys.argv:
    try:
        PORT = int(sys.argv[sys.argv.index("--port") + 1])
    except (ValueError, IndexError):
        pass
