# backend/utils/sync.py
import sqlite3
from backend.database.chat_database import DB_PATH

def init_sync_table():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS user_sync (user_id TEXT PRIMARY KEY, sync_data TEXT)''')
        conn.commit()
        conn.close()
    except Exception as e:
        print("Sync DB / Schema init error:", e)
