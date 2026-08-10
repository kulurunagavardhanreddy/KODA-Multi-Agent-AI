# backend/email_service/worker.py
import sqlite3
import logging
import asyncio

from backend.database.chat_database import DB_PATH
from .permissions import get_email_permissions
from .history import sync_new_emails
from .polling import poll_user_emails
from .watch import is_watch_active, create_gmail_watch

logger = logging.getLogger(__name__)

# Callbacks to notify listeners (e.g. WebSocket connection manager) of database updates
db_update_callbacks = []

async def notify_db_updated_listeners():
    for cb in db_update_callbacks:
        try:
            if asyncio.iscoroutinefunction(cb):
                await cb()
            else:
                cb()
        except Exception as e:
            logger.error(f"Error calling db_update_callback: {e}")

async def check_and_sync_user(user_id: str):
    """Checks the user's watch status, automatically renews if expiring soon, and falls back to polling if needed."""
    perms = get_email_permissions(user_id)
    if not perms.get("enabled"):
        return
        
    # Catch-up: On startup or check, sync any emails received since last_history_id
    last_history_id = perms.get("history_id")
    if last_history_id:
        logger.info(f"🔄 [Catch-Up] Syncing missed emails since history ID {last_history_id} for user {perms.get('connected_email')}...")
        try:
            await sync_new_emails(user_id, last_history_id)
        except Exception as e:
            logger.warning(f"⚠️ [Catch-Up Warning] Incremental history sync failed: {e}. Falling back to full poll.")
            await poll_user_emails(user_id, force=True)
    else:
        # Full poll catch-up if no history ID exists
        await poll_user_emails(user_id, force=True)

    # Now verify watch and renew if expired
    watch_active = is_watch_active(perms)
    if not watch_active:
        logger.info(f"🔄 [Watch Manager] Watch is expired or expiring soon for user {perms.get('connected_email')}. Attempting renewal...")
        watch_res = create_gmail_watch(user_id)
        if watch_res.get("status") == "success":
            logger.info(f"✅ [Watch Manager] Watch successfully renewed for user {perms.get('connected_email')}.")
        else:
            logger.warning(f"⚠️ [Watch Manager] Watch renewal failed for user {perms.get('connected_email')}. Falling back to Polling.")
            
    if not is_watch_active(perms):
        await poll_user_emails(user_id)

async def email_polling_worker():
    """Background loop that polls Gmail inbox using Gmail REST API for all enabled users."""
    logger.info("📡 Starting Email Inbox Intelligence background polling worker...")
    while True:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT user_id FROM email_permissions
                WHERE enabled = 1 AND (refresh_token IS NOT NULL OR access_token IS NOT NULL)
            """)
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                user_id = row[0]
                await check_and_sync_user(user_id)
                
        except Exception as err:
            logger.error(f"❌ [Email Polling Worker Exception] {err}")
            
        interval = 1800
        await asyncio.sleep(interval)
