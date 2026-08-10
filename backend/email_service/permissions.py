# backend/email_service/permissions.py
import sqlite3
import logging
from datetime import datetime, timezone
from backend.database.chat_database import DB_PATH
from .crypto import encrypt_password, decrypt_password

logger = logging.getLogger(__name__)

def get_email_permissions(user_id: str) -> dict:
    """Retrieves the email permissions for the user. If they do not exist, returns defaults (disabled)."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM email_permissions WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            res = dict(row)
            # Mask sensitive values before returning to user facing API/logs
            if res.get("app_password"):
                res["app_password"] = "********"
            if res.get("refresh_token"):
                res["refresh_token"] = "********"
            if res.get("access_token"):
                res["access_token"] = "********"
            return res
        else:
            # Default state (all disabled)
            return {
                "user_id": user_id,
                "enabled": 0,
                "connected_email": None,
                "app_password": None,
                "refresh_token": None,
                "access_token": None,
                "token_expiry": None,
                "last_synced_at": None,
                "last_sync_error": None,
                "started_monitoring_at": None,
                "can_read": 0,
                "can_summarize": 0,
                "can_prioritize": 0,
                "can_notify": 0,
                "can_send": 0,
                "can_archive": 0,
                "can_delete": 0,
                "can_read_attachments": 0,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
    finally:
        conn.close()

def save_email_permissions(user_id: str, perms: dict) -> dict:
    """Saves or updates the email permissions for a user."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    try:
        # Check existing row
        cursor.execute("SELECT enabled, started_monitoring_at, app_password, refresh_token, access_token, token_expiry FROM email_permissions WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        now_str = datetime.now(timezone.utc).isoformat()
        started_monitoring_at = None
        existing_pw = None
        existing_refresh = None
        existing_access = None
        existing_expiry = None
        
        if row:
            was_enabled = row[0]
            started_monitoring_at = row[1]
            existing_pw = row[2]
            existing_refresh = row[3]
            existing_access = row[4]
            existing_expiry = row[5]
            if not was_enabled and perms.get("enabled"):
                started_monitoring_at = now_str
        else:
            if perms.get("enabled"):
                started_monitoring_at = now_str
        
        # Determine target app password
        new_pw = perms.get("app_password")
        if new_pw and new_pw.strip() and new_pw != "********":
            sanitized_pw = "".join(new_pw.split())
            app_password = encrypt_password(sanitized_pw)
        else:
            app_password = existing_pw

        # Determine target OAuth tokens
        new_refresh = perms.get("refresh_token")
        if new_refresh and new_refresh.strip() and new_refresh != "********":
            refresh_token = encrypt_password(new_refresh.strip())
        else:
            refresh_token = existing_refresh

        new_access = perms.get("access_token")
        if new_access and new_access.strip() and new_access != "********":
            access_token = encrypt_password(new_access.strip())
        else:
            access_token = existing_access

        token_expiry = perms.get("token_expiry", existing_expiry)

        cursor.execute('''
            INSERT INTO email_permissions (
                user_id, enabled, connected_email, app_password, refresh_token, access_token, token_expiry, started_monitoring_at,
                can_read, can_summarize, can_prioritize, can_notify,
                can_send, can_archive, can_delete, can_read_attachments, updated_at, last_sync_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                enabled=excluded.enabled,
                connected_email=excluded.connected_email,
                app_password=excluded.app_password,
                refresh_token=excluded.refresh_token,
                access_token=excluded.access_token,
                token_expiry=excluded.token_expiry,
                started_monitoring_at=COALESCE(started_monitoring_at, excluded.started_monitoring_at),
                can_read=excluded.can_read,
                can_summarize=excluded.can_summarize,
                can_prioritize=excluded.can_prioritize,
                can_notify=excluded.can_notify,
                can_send=excluded.can_send,
                can_archive=excluded.can_archive,
                can_delete=excluded.can_delete,
                can_read_attachments=excluded.can_read_attachments,
                updated_at=excluded.updated_at,
                last_sync_error=excluded.last_sync_error
            ''', (
            user_id, perms.get("enabled", 0), perms.get("connected_email"), app_password, refresh_token, access_token, token_expiry, started_monitoring_at,
            perms.get("can_read", 0), perms.get("can_summarize", 0), perms.get("can_prioritize", 0), perms.get("can_notify", 0),
            perms.get("can_send", 0), perms.get("can_archive", 0), perms.get("can_delete", 0), perms.get("can_read_attachments", 0),
            now_str, perms.get("last_sync_error")
        ))
        conn.commit()
        return get_email_permissions(user_id)
    finally:
        conn.close()

def disconnect_email_service(user_id: str, delete_data: bool = False) -> bool:
    """Disconnects the email service, revokes configurations, and optionally wipes analyzed caches."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    try:
        # 1. Reset permissions and wipe secrets
        cursor.execute('''
            UPDATE email_permissions SET
                enabled = 0,
                connected_email = NULL,
                app_password = NULL,
                refresh_token = NULL,
                access_token = NULL,
                token_expiry = NULL,
                started_monitoring_at = NULL,
                can_read = 0,
                can_summarize = 0,
                can_prioritize = 0,
                can_notify = 0,
                can_send = 0,
                can_archive = 0,
                can_delete = 0,
                can_read_attachments = 0,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
        ''', (user_id,))
        
        # 2. Optionally wipe analysis cache
        if delete_data:
            cursor.execute("DELETE FROM email_analysis WHERE user_id = ?", (user_id,))
            
        conn.commit()
        return True
    except Exception as e:
        logger.error("❌ [Disconnect Error] Failed: %s", e)
        return False
    finally:
        conn.close()

def update_sync_status(user_id: str, last_error: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            UPDATE email_permissions SET 
                last_synced_at = ?,
                last_sync_error = ?
            WHERE user_id = ?
        """, (now_str, last_error, user_id))
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to update email sync status: {e}")
    finally:
        conn.close()

def save_gmail_watch_info(user_id: str, history_id: str, watch_expiration: str):
    """Saves Gmail watch information to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE email_permissions SET
                history_id = ?,
                watch_expiration = ?
            WHERE user_id = ?
        """, (history_id, watch_expiration, user_id))
        conn.commit()
    except Exception as e:
        logger.error(f"❌ Failed to save Gmail watch info: {e}")
    finally:
        conn.close()

def save_latest_history_id(user_id: str, history_id: str):
    """Saves the last synchronized history ID to the database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE email_permissions SET history_id = ? WHERE user_id = ?", (history_id, user_id))
        conn.commit()
    except Exception as e:
        logger.error(f"❌ Failed to save latest history ID: {e}")
    finally:
        conn.close()
