# backend/email_service/polling.py
import logging
import requests
from datetime import datetime, timezone

from .permissions import get_email_permissions, update_sync_status, save_latest_history_id
from .watch import is_watch_active
from .oauth import refresh_google_access_token
from .parser import sync_gmail_thread

logger = logging.getLogger(__name__)

async def poll_user_emails(user_id: str, force: bool = False):
    """Refreshes the Google OAuth token, polls Gmail inbox using Gmail REST API, and parses unseen messages."""
    perms = get_email_permissions(user_id)
    if not perms.get("enabled"):
        return
        
    # Skip polling if watch is active and we are not forcing it
    if is_watch_active(perms) and not force:
        logger.debug(f"ℹ️ [Polling Guard] Webhook watch is active for user {perms.get('connected_email')}. Skipping scheduled poll.")
        return
        
    access_token = refresh_google_access_token(user_id)
    if not access_token:
        update_sync_status(user_id, "Gmail token expired or missing. Please reconnect in Email Intelligence settings.")
        return
        
    try:
        # If using simulated mock token in development mode, skip auto-polling.
        if access_token.startswith("mock_access_token_"):
            logger.info("📡 [Dev Mode] Mock token detected — skipping auto-poll. Use Sandbox Simulate to generate demo emails.")
            update_sync_status(user_id, None)
            return
            
        logger.info(f"📡 Polling Gmail inbox for user {perms['connected_email']}...")
        
        # 1. Fetch unread messages received after started_monitoring_at
        started_at = perms.get("started_monitoring_at")
        started_ts = 0
        if started_at:
            try:
                started_dt = datetime.fromisoformat(started_at)
                if started_dt.tzinfo is None:
                    started_dt = started_dt.replace(tzinfo=timezone.utc)
                started_ts = int(started_dt.timestamp())
            except Exception:
                pass
                
        messages_url = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        q_filter = "is:unread is:inbox"
        if started_ts > 0:
            q_filter += f" after:{started_ts}"
            
        params = {"q": q_filter, "maxResults": 20}
        
        res = requests.get(messages_url, headers=headers, params=params, timeout=10)
        if res.status_code != 200:
            raise Exception(f"Gmail API returned {res.status_code}: {res.text}")
            
        data = res.json()
        messages = data.get("messages", [])
        
        # Keep track of history ID
        latest_history_id = data.get("historyId")
        if latest_history_id:
            save_latest_history_id(user_id, str(latest_history_id))
            
        if not messages:
            update_sync_status(user_id, None)
            return
            
        # Collect unique thread IDs to sync
        unique_threads = []
        for msg in messages:
            t_id = msg.get("threadId")
            if t_id and t_id not in unique_threads:
                unique_threads.append(t_id)
                
        if unique_threads:
            logger.info(f"📡 Found {len(unique_threads)} unique threads to sync via Gmail API.")
            for t_id in unique_threads:
                try:
                    await sync_gmail_thread(user_id, t_id, access_token)
                except Exception as thread_err:
                    logger.error(f"❌ Failed to sync thread {t_id}: {thread_err}")
                    
        update_sync_status(user_id, None)
        
        # Notify WebSocket listeners of dashboard updates
        from .worker import notify_db_updated_listeners
        await notify_db_updated_listeners()
    except Exception as e:
        logger.error(f"❌ [Gmail API Polling Error] {e}")
        update_sync_status(user_id, str(e))
