# backend/email_service/watch.py
import os
import uuid
import logging
import requests
from datetime import datetime, timezone, timedelta

from .permissions import get_email_permissions, save_gmail_watch_info
from .oauth import refresh_google_access_token

logger = logging.getLogger(__name__)

def is_watch_active(perms: dict) -> bool:
    """Returns True if the watch is active and has more than 24 hours left to live."""
    exp = perms.get("watch_expiration")
    if not exp:
        return False
    try:
        exp_dt = datetime.fromisoformat(exp)
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        return (exp_dt - datetime.now(timezone.utc)).total_seconds() > 86400
    except Exception:
        return False

def create_gmail_watch(user_id: str) -> dict:
    """Sends a watch request to Gmail API to establish real-time push notifications."""
    perms = get_email_permissions(user_id)
    if not perms.get("enabled"):
        return {"status": "error", "message": "Email intelligence is disabled."}
        
    access_token = refresh_google_access_token(user_id)
    if not access_token:
        return {"status": "error", "message": "Failed to authenticate with Google."}
        
    # Simulated mock watch in development mode if mock token detected
    if access_token.startswith("mock_access_token_"):
        logger.info("📡 [Dev Mode] Simulating Gmail Watch creation for mock token...")
        mock_expiration = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        mock_history_id = "mock_hist_123456"
        save_gmail_watch_info(user_id, mock_history_id, mock_expiration)
        return {"status": "success", "historyId": mock_history_id, "expiration": mock_expiration, "mode": "mock"}
        
    topic = os.getenv("GOOGLE_PUBSUB_TOPIC", "projects/wide-planet-501205-s8/topics/koda-gmail-notifications")
    url = "https://gmail.googleapis.com/gmail/v1/users/me/watch"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "topicName": topic,
        "labelIds": ["INBOX"]
    }
    
    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            history_id = str(data.get("historyId"))
            expiration_ms = data.get("expiration")
            if expiration_ms:
                expiration_dt = datetime.fromtimestamp(int(expiration_ms) / 1000.0, tz=timezone.utc)
                expiration_iso = expiration_dt.isoformat()
            else:
                expiration_iso = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
                
            save_gmail_watch_info(user_id, history_id, expiration_iso)
            logger.info(f"✅ [Gmail Watch] Successfully registered watch for user {perms.get('connected_email')}. Expiration: {expiration_iso}")
            return {"status": "success", "historyId": history_id, "expiration": expiration_iso, "mode": "watch"}
        else:
            err_msg = f"Gmail API watch returned {res.status_code}: {res.text}"
            logger.warning(f"⚠️ [Gmail Watch] Watch registration failed, falling back to Polling. Error: {err_msg}")
            save_gmail_watch_info(user_id, None, None)
            return {"status": "fallback", "message": err_msg}
    except Exception as e:
        logger.error(f"❌ [Gmail Watch Exception] {e}. Falling back to Polling.")
        save_gmail_watch_info(user_id, None, None)
        return {"status": "fallback", "message": str(e)}
