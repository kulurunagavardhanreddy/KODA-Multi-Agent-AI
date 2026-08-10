# backend/routers/email_notifications.py
import sqlite3
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.core.security import get_current_user
from backend.database.chat_database import DB_PATH
from backend.email_service import notify_db_updated_listeners

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email", tags=["email_notifications"])

class EmailMarkReadRequest(BaseModel):
    gmail_message_id: str

@router.post("/mark-read")
async def mark_email_read_endpoint(payload: EmailMarkReadRequest, current_user: dict = Depends(get_current_user)):
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot access Inbox Intelligence.")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT gmail_thread_id FROM email_analysis WHERE gmail_message_id = ? AND user_id = ?", (payload.gmail_message_id, current_user["user_id"]))
        row = cursor.fetchone()
        if row:
            thread_id = row[0]
            cursor.execute("UPDATE email_analysis SET needs_response = 0 WHERE gmail_thread_id = ? AND user_id = ?", (thread_id, current_user["user_id"]))
            conn.commit()
            
            await notify_db_updated_listeners()
            return {"status": "success", "message": "Email thread marked as read/handled."}
        else:
            raise HTTPException(status_code=404, detail="Email record not found.")
    except Exception as e:
        logger.error(f"Error marking email as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
