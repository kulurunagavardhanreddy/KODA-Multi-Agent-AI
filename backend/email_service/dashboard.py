# backend/email_service/dashboard.py
import math
import sqlite3
from datetime import datetime, timezone

from backend.database.chat_database import DB_PATH

def get_email_digest_dashboard(user_id: str) -> dict:
    """Computes Today's Email Digest summary metrics and groups analyses by priority classification."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, gmail_message_id, gmail_thread_id, subject,
                   original_subject, original_body, original_sender, original_received_at,
                   thread_summary, latest_message_body, latest_message_sender, latest_received_at, gmail_message_count,
                   priority, confidence_score, status, previous_status, conversation_stage, thread_health,
                   needs_response, last_sender_type, suggested_action, suggested_action_type, last_activity_at,
                   sender, received_at, summary, reason, stars, estimated_time
            FROM email_analysis
            WHERE user_id = ?
            ORDER BY last_activity_at DESC
        ''', (user_id,))
        rows = cursor.fetchall()
        
        digest = {
            "Critical": [],
            "High": [],
            "Medium": [],
            "Low": []
        }
        
        total_time_saved_sec = 0
        
        for row in rows:
            p_dict = dict(row)
            p_class = p_dict["priority"]
            if p_class in digest:
                digest[p_class].append(p_dict)
            else:
                digest["Medium"].append(p_dict)
                
            if p_class in ["Low", "Medium"]:
                total_time_saved_sec += p_dict.get("estimated_time", 0)

        estimated_time_saved_min = math.ceil(total_time_saved_sec / 60)

        # Fetch sync status metadata & watch status
        cursor.execute("SELECT last_synced_at, last_sync_error, watch_expiration FROM email_permissions WHERE user_id = ?", (user_id,))
        perm_row = cursor.fetchone()
        last_synced_at = None
        last_sync_error = None
        watch_expiration = None
        if perm_row:
            last_synced_at = perm_row["last_synced_at"]
            last_sync_error = perm_row["last_sync_error"]
            watch_expiration = perm_row["watch_expiration"]

        # Determine watch active status (must have > 24 hours left, else we'll renew)
        watch_active = 0
        if watch_expiration:
            try:
                exp_dt = datetime.fromisoformat(watch_expiration)
                if exp_dt.tzinfo is None:
                    exp_dt = exp_dt.replace(tzinfo=timezone.utc)
                if (exp_dt - datetime.now(timezone.utc)).total_seconds() > 86400:
                    watch_active = 1
            except Exception:
                pass

        needs_response_count = sum(1 for row in rows if row["needs_response"] == 1)

        return {
            "digest": digest,
            "metrics": {
                "total_unread": sum(len(items) for items in digest.values()),
                "estimated_time_saved_minutes": estimated_time_saved_min,
                "critical_count": len(digest["Critical"]),
                "high_count": len(digest["High"]),
                "medium_count": len(digest["Medium"]),
                "low_count": len(digest["Low"]),
                "needs_response_count": needs_response_count,
                "last_synced_at": last_synced_at,
                "last_sync_error": last_sync_error,
                "watch_active": watch_active,
                "polling_interval_seconds": 1800
            }
        }
    finally:
        conn.close()
