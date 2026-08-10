# backend/websocket/manager.py
import sqlite3
import logging
from fastapi import WebSocket
from backend.database.chat_database import DB_PATH

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # Map user_id -> list of WebSockets
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.active_connections:
            if websocket in self.active_connections[user_id]:
                self.active_connections[user_id].remove(websocket)
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: dict):
        if user_id in self.active_connections:
            for connection in self.active_connections[user_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

ws_manager = ConnectionManager()

def get_needs_response_count(user_id: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM email_analysis WHERE user_id = ? AND needs_response = 1", (user_id,))
        row = cursor.fetchone()
        return row[0] if row else 0
    except Exception as e:
        logger.error(f"Error fetching needs response count: {e}")
        return 0
    finally:
        conn.close()

async def notify_user_dashboard_updated():
    active_users = list(ws_manager.active_connections.keys())
    for uid in active_users:
        count = get_needs_response_count(uid)
        await ws_manager.send_to_user(uid, {"event": "dashboard_updated", "count": count})

# Register callback with email updates notifier list
try:
    from backend.email_service import db_update_callbacks
    db_update_callbacks.append(notify_user_dashboard_updated)
except Exception as e:
    logger.error(f"Failed to register notify_user_dashboard_updated callback: {e}")
