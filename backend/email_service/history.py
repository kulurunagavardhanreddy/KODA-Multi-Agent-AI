# backend/email_service/history.py
import logging
import requests
from typing import Optional

from .permissions import get_email_permissions, save_latest_history_id, update_sync_status
from .oauth import refresh_google_access_token
from .polling import poll_user_emails
from .parser import sync_gmail_thread

logger = logging.getLogger(__name__)

async def sync_new_emails(user_id: str, webhook_history_id: Optional[str] = None):
    """Fetches incremental inbox changes from Gmail API since the last stored history_id."""
    perms = get_email_permissions(user_id)
    if not perms.get("enabled"):
        return
        
    access_token = refresh_google_access_token(user_id)
    if not access_token:
        logger.warning(f"⚠️ [Webhook Sync] Failed to refresh token for user {user_id}")
        return
        
    headers = {"Authorization": f"Bearer {access_token}"}
    last_history_id = perms.get("history_id")
    
    # If no last_history_id or in mock mode, perform full scan
    if not last_history_id or last_history_id.startswith("mock_") or (webhook_history_id and webhook_history_id.startswith("mock_")):
        logger.info("📡 [Webhook Sync] No valid history ID found or mock token active. Performing full scan fallback.")
        await poll_user_emails(user_id, force=True)
        if webhook_history_id:
            save_latest_history_id(user_id, webhook_history_id)
        return
        
    history_url = "https://gmail.googleapis.com/gmail/v1/users/me/history"
    params = {
        "startHistoryId": last_history_id,
        "historyTypes": ["messageAdded"],
        "maxResults": 50
    }
    
    try:
        res = requests.get(history_url, headers=headers, params=params, timeout=10)
        
        # If the history ID is too old (404/410), fallback to full scan
        if res.status_code in [404, 410]:
            logger.info("📡 [Webhook Sync] History ID is expired. Performing full scan fallback.")
            await poll_user_emails(user_id, force=True)
            if webhook_history_id:
                save_latest_history_id(user_id, webhook_history_id)
            return
        elif res.status_code != 200:
            raise Exception(f"Gmail History API returned {res.status_code}: {res.text}")
            
        history_data = res.json()
        history_records = history_data.get("history", [])
        
        unique_threads = []
        for record in history_records:
            messages_added = record.get("messagesAdded", [])
            for added in messages_added:
                msg = added.get("message", {})
                t_id = msg.get("threadId")
                if not t_id:
                    t_id = msg.get("id")
                if t_id and t_id not in unique_threads:
                    unique_threads.append(t_id)
                    
        if unique_threads:
            logger.info(f"📡 [Webhook Sync] Found {len(unique_threads)} unique threads to sync since history_id {last_history_id}.")
            for t_id in unique_threads:
                try:
                    await sync_gmail_thread(user_id, t_id, access_token)
                except Exception as thread_err:
                    logger.error(f"❌ [Webhook Sync] Failed to sync thread {t_id}: {thread_err}")
                    
        current_history_id = history_data.get("historyId") or webhook_history_id
        if current_history_id:
            save_latest_history_id(user_id, str(current_history_id))
            
        update_sync_status(user_id, None)
        
        # Notify WebSocket connection manager
        from .worker import notify_db_updated_listeners
        await notify_db_updated_listeners()
        
    except Exception as e:
        logger.error(f"❌ [Webhook Sync Error] {e}")
        update_sync_status(user_id, str(e))
