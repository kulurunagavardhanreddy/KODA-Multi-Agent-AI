# backend/core/startup.py
import asyncio
import logging
import requests
from backend.database.chat_database import init_db
from backend.utils.sync import init_sync_table
from backend.core.config import NGROK_AUTH_TOKEN, NGROK_DOMAIN, PORT, MISTRAL_API_BASE
from backend.loaders.document_loader import get_vector_store
from backend.workers.backup import automated_backup
from backend.workers.cleanup import automated_cleanup
from backend.email_service import email_polling_worker
from backend.integrations.mcp import mcp_manager
from pyngrok import ngrok

logger = logging.getLogger(__name__)

async def startup(app):
    # Run DB initializations
    init_db()
    init_sync_table()
    logger.info("━" * 55)
    logger.info("🚀  KODA Agent API  |  Booting up...")
    logger.info("━" * 55)

    # Pre-load embedding model silently in the background
    async def preload_model():
        import sys, io
        # Suppress the BertModel LOAD REPORT table printed to stdout by sentence_transformers
        _old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        try:
            await asyncio.to_thread(get_vector_store)
        finally:
            sys.stdout = _old_stdout
        logger.info("🧠  Embedding model  │ Loaded into RAM")

    asyncio.create_task(preload_model())

    # GPU server ping
    if MISTRAL_API_BASE:
        try:
            resp = requests.get(f"{MISTRAL_API_BASE}/models", timeout=3)
            status = "🟢 ONLINE" if resp.status_code == 200 else f"🟡 REACHABLE ({resp.status_code})"
        except requests.exceptions.RequestException:
            status = "🔴 OFFLINE"
        logger.info("⚡  GPU Server       │ %s  (%s)", status, MISTRAL_API_BASE)

    # Ngrok tunnel
    public_url = None
    if NGROK_AUTH_TOKEN:
        try:
            ngrok.set_auth_token(NGROK_AUTH_TOKEN)
            connect_kwargs = {"addr": f"127.0.0.1:{PORT}"}
            if NGROK_DOMAIN:
                connect_kwargs["domain"] = NGROK_DOMAIN
            public_url = ngrok.connect(**connect_kwargs).public_url
            logger.info("🌍  Ngrok Tunnel     │ %s", public_url)
        except Exception as ne:
            logger.warning("⚠️  Ngrok Tunnel     │ Failed: %s", ne)

    # Store tasks & url in app state for graceful teardowns
    app.state.public_url = public_url
    app.state.backup_task = asyncio.create_task(automated_backup())
    app.state.cleanup_task = asyncio.create_task(automated_cleanup())

    # Email Intelligence poller
    try:
        app.state.email_task = asyncio.create_task(email_polling_worker())
    except Exception as ee:
        logger.warning("⚠️  Email Poller     │ Failed to start: %s", ee)

    # MCP Manager
    try:
        await mcp_manager.start_all_servers()
    except Exception as me:
        logger.warning("⚠️  MCP Manager      │ Failed to start: %s", me)

