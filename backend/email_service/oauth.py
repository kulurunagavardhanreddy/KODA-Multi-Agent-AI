# backend/email_service/oauth.py
import os
import uuid
import sqlite3
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional

from backend.database.chat_database import DB_PATH
from .crypto import encrypt_password, decrypt_password
from .permissions import update_sync_status

logger = logging.getLogger(__name__)

def refresh_google_access_token(user_id: str) -> Optional[str]:
    """Checks the stored access token validity, refreshes it from Google OAuth server using the encrypted refresh_token, and saves the new token."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT refresh_token, access_token, token_expiry FROM email_permissions WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        # Implicit/token flow: no refresh_token, but may have a valid short-lived access_token
        if not row["refresh_token"]:
            if not row["access_token"]:
                return None
            # Check if access token is still valid
            try:
                now = datetime.now(timezone.utc)
                if row["token_expiry"]:
                    expiry = datetime.fromisoformat(row["token_expiry"])
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                    if (expiry - now).total_seconds() > 60:
                        return decrypt_password(row["access_token"])
                    else:
                        # Token expired — mark in DB and tell poller
                        update_sync_status(user_id, "Gmail token expired. Please reconnect in Email Intelligence settings.")
                        return None
            except Exception:
                pass
            return decrypt_password(row["access_token"])  # try anyway if no expiry info
            
        # Decrypt refresh token
        decrypted_refresh = decrypt_password(row["refresh_token"])
        if not decrypted_refresh:
            return None
            
        # Check if the existing access token is still valid (expiry > now + 60s)
        now = datetime.now(timezone.utc)
        if row["access_token"] and row["token_expiry"]:
            try:
                expiry = datetime.fromisoformat(row["token_expiry"])
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if (expiry - now).total_seconds() > 60:
                    return decrypt_password(row["access_token"])
            except Exception:
                pass
                
        # If expired or invalid, refresh the token
        client_id = os.getenv("GOOGLE_CLIENT_ID", "")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        
        # If mock tokens or empty secret in development mode, simulate token refresh
        if not client_secret or decrypted_refresh.startswith("mock_"):
            logger.info("🔑 [Mock OAuth Refresh] Simulating OAuth access token refresh in development mode...")
            mock_access = f"mock_access_token_{uuid.uuid4().hex}"
            mock_expiry = (now + timedelta(hours=1)).isoformat()
            
            # Save mock access token
            cursor.execute("""
                UPDATE email_permissions SET
                    access_token = ?,
                    token_expiry = ?
                WHERE user_id = ?
            """, (encrypt_password(mock_access), mock_expiry, user_id))
            conn.commit()
            return mock_access
            
        # Perform real token refresh via Google's endpoint
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": decrypted_refresh,
            "grant_type": "refresh_token"
        }
        res = requests.post(token_url, data=payload, timeout=10)
        if res.status_code == 200:
            data = res.json()
            new_access = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            new_expiry = (now + timedelta(seconds=expires_in)).isoformat()
            
            cursor.execute("""
                UPDATE email_permissions SET
                    access_token = ?,
                    token_expiry = ?
                WHERE user_id = ?
            """, (encrypt_password(new_access), new_expiry, user_id))
            conn.commit()
            return new_access
        else:
            logger.error(f"❌ [OAuth Refresh Error] Google returned {res.status_code}: {res.text}")
            return None
    except Exception as e:
        logger.error(f"❌ [refresh_google_access_token Exception] {e}")
        return None
    finally:
        conn.close()
