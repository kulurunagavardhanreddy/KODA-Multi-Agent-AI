# main.py
import sys
import io
import logging
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI

# Force UTF-8 encoding for stdout/stderr on Windows to support emojis and symbols
if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

# ─── Application logging ────────────────────────────────────────────────────
# Show INFO-level logs from our own modules, suppress uvicorn access spam.
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s │ %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
# Suppress noisy third-party loggers
for _noisy in (
    "httpx", "httpcore", "urllib3",
    "sentence_transformers", "transformers",
    "pyngrok", "pyngrok.process", "pyngrok.ngrok", "pyngrok.process.ngrok",  # ngrok tunnel verbose logs
    "websockets", "uvicorn.access",  # websocket 'connection open' + HTTP access logs
):
    logging.getLogger(_noisy).setLevel(logging.WARNING)
# ─────────────────────────────────────────────────────────────────────────────

from backend.core.lifespan import lifespan
from backend.core.middleware import setup_middlewares
from backend.core.static import setup_static
from backend.core.config import PORT
from backend.routers import register_routes

# Initialize core FastAPI instance
app = FastAPI(title="LangChain Gemini Agent API", lifespan=lifespan)

# Setup middlewares, register modular routes and mount static templates
setup_middlewares(app)
register_routes(app)
setup_static(app)

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=PORT, reload=True, access_log=False)