# backend/routers/sync.py
import sqlite3
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.core.security import get_current_user
from backend.database.chat_database import DB_PATH

router = APIRouter(prefix="/api", tags=["sync"])

class SyncData(BaseModel):
    sync_data: str

@router.post("/sync")
def save_sync_data(payload: SyncData, current_user: dict = Depends(get_current_user)):
    """Saves user preferences and sidebar chat sessions to the cloud."""
    if current_user.get("is_guest"):
        return {"status": "ignored"}
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO user_sync (user_id, sync_data) VALUES (?, ?)", (current_user["user_id"], payload.sync_data))
        conn.commit()
        conn.close()
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sync")
def get_sync_data(current_user: dict = Depends(get_current_user)):
    """Retrieves user preferences and sidebar chat sessions from the cloud."""
    if current_user.get("is_guest"):
        return {"sync_data": None}
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT sync_data FROM user_sync WHERE user_id = ?", (current_user["user_id"],))
        row = c.fetchone()
        conn.close()
        if row:
            return {"sync_data": row[0]}
        return {"sync_data": None}
    except Exception as e:
        return {"sync_data": None}
