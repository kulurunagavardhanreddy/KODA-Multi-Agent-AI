# chat_database.py

import sqlite3
import os
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

# This creates a SQLite database file at the root of your project
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "chat_history.db")

def init_db():
    """Initialize the SQLite database and create a neatly formatted chats table."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            deleted_at DATETIME DEFAULT NULL
        )
    ''')
    # Safely migrate chats table with deleted_at column if missing
    cursor.execute("PRAGMA table_info(chats)")
    chats_columns = [row[1] for row in cursor.fetchall()]
    if "deleted_at" not in chats_columns:
        cursor.execute("ALTER TABLE chats ADD COLUMN deleted_at DATETIME DEFAULT NULL")
        conn.commit()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversation_memories (
            user_id TEXT,
            session_id TEXT NOT NULL,
            category TEXT NOT NULL,
            summary_text TEXT,
            memory_type TEXT DEFAULT 'general',
            entities TEXT DEFAULT '[]',
            importance INTEGER DEFAULT 5,
            last_accessed DATETIME DEFAULT CURRENT_TIMESTAMP,
            access_count INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (session_id, category)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS uploaded_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_name TEXT NOT NULL,
            uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shared_chats (
            share_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_workspaces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            path TEXT NOT NULL,
            is_active INTEGER DEFAULT 0,
            UNIQUE(user_id, path)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_sync (
            user_id TEXT PRIMARY KEY,
            sync_data TEXT NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_permissions (
            user_id TEXT PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            connected_email TEXT,
            app_password TEXT,
            refresh_token TEXT,
            access_token TEXT,
            token_expiry DATETIME,
            last_synced_at DATETIME,
            last_sync_error TEXT,
            started_monitoring_at DATETIME,
            history_id TEXT,
            watch_expiration DATETIME,
            can_read INTEGER DEFAULT 0,
            can_summarize INTEGER DEFAULT 0,
            can_prioritize INTEGER DEFAULT 0,
            can_notify INTEGER DEFAULT 0,
            can_send INTEGER DEFAULT 0,
            can_archive INTEGER DEFAULT 0,
            can_delete INTEGER DEFAULT 0,
            can_read_attachments INTEGER DEFAULT 0,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Safely migrate email_permissions with app_password and OAuth columns
    cursor.execute("PRAGMA table_info(email_permissions)")
    email_columns = [row[1] for row in cursor.fetchall()]
    if email_columns:
        migrations = [
            ("app_password",          "ALTER TABLE email_permissions ADD COLUMN app_password TEXT"),
            ("refresh_token",         "ALTER TABLE email_permissions ADD COLUMN refresh_token TEXT"),
            ("access_token",          "ALTER TABLE email_permissions ADD COLUMN access_token TEXT"),
            ("token_expiry",          "ALTER TABLE email_permissions ADD COLUMN token_expiry DATETIME"),
            ("last_synced_at",        "ALTER TABLE email_permissions ADD COLUMN last_synced_at DATETIME"),
            ("last_sync_error",       "ALTER TABLE email_permissions ADD COLUMN last_sync_error TEXT"),
            ("started_monitoring_at", "ALTER TABLE email_permissions ADD COLUMN started_monitoring_at DATETIME"),
            ("history_id",            "ALTER TABLE email_permissions ADD COLUMN history_id TEXT"),
            ("watch_expiration",      "ALTER TABLE email_permissions ADD COLUMN watch_expiration DATETIME"),
        ]
        for col_name, sql in migrations:
            if col_name not in email_columns:
                cursor.execute(sql)
        conn.commit()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            gmail_message_id TEXT NOT NULL,
            gmail_thread_id TEXT,
            subject TEXT,
            original_subject TEXT,
            original_body TEXT,
            original_sender TEXT,
            original_received_at DATETIME,
            thread_summary TEXT,
            latest_message_body TEXT,
            latest_message_sender TEXT,
            latest_received_at DATETIME,
            gmail_message_count INTEGER DEFAULT 1,
            priority TEXT,
            confidence_score REAL,
            status TEXT DEFAULT 'Open',
            previous_status TEXT,
            conversation_stage TEXT,
            thread_health TEXT,
            needs_response INTEGER DEFAULT 0,
            last_sender_type TEXT,
            suggested_action TEXT,
            suggested_action_type TEXT,
            last_activity_at DATETIME,
            sender TEXT,
            received_at DATETIME,
            summary TEXT,
            reason TEXT,
            stars INTEGER,
            estimated_time INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    
    # Safely migrate email_analysis with thread columns
    cursor.execute("PRAGMA table_info(email_analysis)")
    analysis_columns = [row[1] for row in cursor.fetchall()]
    if analysis_columns:
        migrations = [
            ("gmail_thread_id",        "ALTER TABLE email_analysis ADD COLUMN gmail_thread_id TEXT"),
            ("original_subject",       "ALTER TABLE email_analysis ADD COLUMN original_subject TEXT"),
            ("original_body",          "ALTER TABLE email_analysis ADD COLUMN original_body TEXT"),
            ("original_sender",        "ALTER TABLE email_analysis ADD COLUMN original_sender TEXT"),
            ("original_received_at",   "ALTER TABLE email_analysis ADD COLUMN original_received_at DATETIME"),
            ("thread_summary",         "ALTER TABLE email_analysis ADD COLUMN thread_summary TEXT"),
            ("latest_message_body",    "ALTER TABLE email_analysis ADD COLUMN latest_message_body TEXT"),
            ("latest_message_sender",  "ALTER TABLE email_analysis ADD COLUMN latest_message_sender TEXT"),
            ("latest_received_at",     "ALTER TABLE email_analysis ADD COLUMN latest_received_at DATETIME"),
            ("gmail_message_count",    "ALTER TABLE email_analysis ADD COLUMN gmail_message_count INTEGER DEFAULT 1"),
            ("confidence_score",       "ALTER TABLE email_analysis ADD COLUMN confidence_score REAL"),
            ("status",                 "ALTER TABLE email_analysis ADD COLUMN status TEXT DEFAULT 'Open'"),
            ("previous_status",        "ALTER TABLE email_analysis ADD COLUMN previous_status TEXT"),
            ("conversation_stage",     "ALTER TABLE email_analysis ADD COLUMN conversation_stage TEXT"),
            ("thread_health",          "ALTER TABLE email_analysis ADD COLUMN thread_health TEXT"),
            ("needs_response",         "ALTER TABLE email_analysis ADD COLUMN needs_response INTEGER DEFAULT 0"),
            ("last_sender_type",       "ALTER TABLE email_analysis ADD COLUMN last_sender_type TEXT"),
            ("suggested_action",       "ALTER TABLE email_analysis ADD COLUMN suggested_action TEXT"),
            ("suggested_action_type",  "ALTER TABLE email_analysis ADD COLUMN suggested_action_type TEXT"),
            ("last_activity_at",       "ALTER TABLE email_analysis ADD COLUMN last_activity_at DATETIME"),
        ]
        for col_name, sql in migrations:
            if col_name not in analysis_columns:
                cursor.execute(sql)
        conn.commit()

    # Create unique index for thread_id to allow upserting
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_email_analysis_thread_id ON email_analysis(gmail_thread_id);")
    conn.commit()
    
    # Safely add deleted_at for Soft Delete capabilities
    cursor.execute("PRAGMA table_info(chats)")
    columns = [row[1] for row in cursor.fetchall()]
    if "deleted_at" not in columns:
        cursor.execute("ALTER TABLE chats ADD COLUMN deleted_at DATETIME")
        conn.commit()
        
    # Safely migrate conversation_memories with rich metadata columns
    cursor.execute("PRAGMA table_info(conversation_memories)")
    mem_columns = [row[1] for row in cursor.fetchall()]
    if mem_columns:
        if "user_id" not in mem_columns:
            cursor.execute("ALTER TABLE conversation_memories ADD COLUMN user_id TEXT")
        if "memory_type" not in mem_columns:
            cursor.execute("ALTER TABLE conversation_memories ADD COLUMN memory_type TEXT DEFAULT 'general'")
        if "entities" not in mem_columns:
            cursor.execute("ALTER TABLE conversation_memories ADD COLUMN entities TEXT DEFAULT '[]'")
        if "importance" not in mem_columns:
            cursor.execute("ALTER TABLE conversation_memories ADD COLUMN importance INTEGER DEFAULT 5")
        if "last_accessed" not in mem_columns:
            cursor.execute("ALTER TABLE conversation_memories ADD COLUMN last_accessed DATETIME")
            cursor.execute("UPDATE conversation_memories SET last_accessed = CURRENT_TIMESTAMP WHERE last_accessed IS NULL")
        if "access_count" not in mem_columns:
            cursor.execute("ALTER TABLE conversation_memories ADD COLUMN access_count INTEGER DEFAULT 0")
        conn.commit()
        
    # INDEXES FOR LOOKUPS
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chats_user_session ON chats(user_id, session_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_shared_chats_share_id ON shared_chats(share_id);")
        
    conn.close()

def save_message(user_id: str, session_id: str, role: str, content: str):
    """Save a single chat message (user or assistant) to the SQLite database."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chats (user_id, session_id, role, content, timestamp) VALUES (?, ?, ?, ?, ?)",
            (user_id, session_id, role, content, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        print(f"💾 [SQLite DB] Saved '{role}' message to chat history.")
    finally:
        conn.close()

def get_history(user_id: str, session_id: str, limit: int = 20, offset: int = 0) -> list:
    """Retrieves the chat history for a given session_id from the SQLite database."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT role, content FROM (
                SELECT role, content, timestamp FROM chats 
                WHERE user_id = ? AND session_id = ? AND deleted_at IS NULL 
                ORDER BY timestamp DESC LIMIT ? OFFSET ?
            ) ORDER BY timestamp ASC
            """,
            (user_id, session_id, limit, offset)
        )
        history = cursor.fetchall()
        print(f"\n📂 [SQLite DB] Loaded {len(history)} messages from session '{session_id}' (Offset: {offset}).")
        return [dict(row) for row in history]
    finally:
        conn.close()

def soft_delete_session(user_id: str, session_id: str):
    """Marks all messages in a session as deleted."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    cursor.execute("UPDATE chats SET deleted_at = CURRENT_TIMESTAMP WHERE user_id = ? AND session_id = ?", (user_id, session_id))
    conn.commit()
    conn.close()

def get_expired_sessions() -> list:
    """Finds sessions deleted more than 30 days ago."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT user_id, session_id FROM chats WHERE deleted_at IS NOT NULL AND deleted_at <= datetime('now', '-30 days')")
    rows = cursor.fetchall()
    conn.close()
    return [(r[0], r[1]) for r in rows]

def hard_delete_session(user_id: str, session_id: str):
    """Permanently deletes a session from SQLite."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chats WHERE user_id = ? AND session_id = ?", (user_id, session_id))
    cursor.execute("DELETE FROM conversation_memories WHERE user_id = ? AND session_id = ?", (user_id, session_id))
    conn.commit()
    conn.close()

def create_user(email: str, username: str, password: str) -> bool:
    """Creates a new user with a hashed password. Returns False if email exists."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    user_id = str(uuid.uuid4())
    try:
        cursor.execute("INSERT INTO users (user_id, email, username, password_hash) VALUES (?, ?, ?, ?)", (user_id, email, username, pwd_hash))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def get_session_memories(user_id: str, session_id: str) -> str:
    """Retrieves formatted long-term memory summaries grouped by category."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    cursor.execute("SELECT category, summary_text FROM conversation_memories WHERE user_id = ? AND session_id = ?", (user_id, session_id))
    rows = cursor.fetchall()
    conn.close()
    if not rows: return ""
    return "\n".join([f"- [{row[0]}]: {row[1]}" for row in rows])

def get_session_memories_dict(user_id: str, session_id: str) -> dict:
    """Retrieves raw long-term memory summaries as a dictionary for the Memory Manager."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    cursor.execute("SELECT category, summary_text FROM conversation_memories WHERE user_id = ? AND session_id = ?", (user_id, session_id))
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}

def save_conversation_memory(
    user_id: str, 
    session_id: str, 
    category: str, 
    summary_text: str,
    memory_type: str = "general",
    entities: list = None,
    importance: int = 5
):
    """Saves or updates a specific topic memory for a chat session with rich metadata."""
    import json
    entities_str = json.dumps(entities or [])
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO conversation_memories (
                user_id, session_id, category, summary_text, 
                memory_type, entities, importance, last_accessed, access_count, updated_at
            ) 
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 0, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id, category) DO UPDATE SET 
            summary_text=excluded.summary_text, 
            memory_type=excluded.memory_type,
            entities=excluded.entities,
            importance=excluded.importance,
            updated_at=CURRENT_TIMESTAMP, 
            user_id=excluded.user_id
        ''', (user_id, session_id, category, summary_text, memory_type, entities_str, importance))
        conn.commit()
        
        try:
            from backend.memory.vector_memory import save_conversation_memory_vector
            save_conversation_memory_vector(
                user_id=user_id, 
                session_id=session_id, 
                category=category, 
                summary_text=summary_text,
                memory_type=memory_type,
                entities=entities or [],
                importance=importance
            )
        except Exception as qe:
            print(f"⚠️ [Vector Memory] Failed to save granular memory to vector storage: {qe}")
            
    except Exception as e:
        print(f"⚠️ [SQLite DB] Failed to save granular memory: {e}")
    finally:
        conn.close()

def increment_memory_access(user_id: str, session_id: str, category: str):
    """Increments access count and updates last_accessed timestamp for a specific memory."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE conversation_memories 
            SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
            WHERE user_id = ? AND session_id = ? AND category = ?
        ''', (user_id, session_id, category))
        conn.commit()
    except Exception as e:
        print(f"⚠️ [SQLite DB] Failed to increment memory access: {e}")
    finally:
        conn.close()

def verify_user(email: str, password: str) -> dict:
    """Verifies if the provided email and password match. Returns user dict or None."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute("SELECT user_id, username FROM users WHERE email = ? AND password_hash = ?", (email, pwd_hash))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def delete_uploaded_file_record(user_id: str, file_hash: str):
    """Deletes a specific uploaded file record from the database."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM uploaded_files WHERE user_id = ? AND file_hash = ?", (user_id, file_hash))
        conn.commit()
        print(f"🗑️ [SQLite DB] Deleted uploaded file record for user '{user_id}' with hash '{file_hash}'.")
    except Exception as e:
        print(f"❌ [SQLite DB] Failed to delete uploaded file record: {e}")
    finally:
        conn.close()

def clear_all_uploaded_file_records(user_id: str = None):
    """Clears all uploaded file records for a specific user, or for all users if user_id is None."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    try:
        if user_id:
            cursor.execute("DELETE FROM uploaded_files WHERE user_id = ?", (user_id,))
            print(f"🗑️ [SQLite DB] Cleared all uploaded file records for user '{user_id}'.")
        else:
            cursor.execute("DELETE FROM uploaded_files")
            print("🗑️ [SQLite DB] Cleared all uploaded file records for all users.")
        conn.commit()
    except Exception as e:
        print(f"❌ [SQLite DB] Failed to clear uploaded file records: {e}")
    finally:
        conn.close()

def is_file_uploaded(user_id: str, file_hash: str) -> bool:
    """Checks if a user has already uploaded a file with this specific hash."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM uploaded_files WHERE user_id = ? AND file_hash = ?", (user_id, file_hash))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def log_uploaded_file(user_id: str, file_hash: str, file_name: str):
    """Logs a successfully uploaded file into the database."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO uploaded_files (user_id, file_hash, file_name) VALUES (?, ?, ?)", (user_id, file_hash, file_name))
        conn.commit()
    except Exception as e:
        print(f"⚠️ [SQLite DB] Failed to log file upload: {e}")
    finally:
        conn.close()

def create_share_link(user_id: str, session_id: str) -> str:
    """Creates or retrieves a shareable UUID for a chat session."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    cursor.execute("SELECT share_id FROM shared_chats WHERE user_id = ? AND session_id = ?", (user_id, session_id))
    row = cursor.fetchone()
    if row:
        conn.close()
        return row[0]
    
    share_id = str(uuid.uuid4())
    cursor.execute("INSERT INTO shared_chats (share_id, user_id, session_id) VALUES (?, ?, ?)", (share_id, user_id, session_id))
    conn.commit()
    conn.close()
    return share_id

def get_shared_history(share_id: str) -> list:
    """Retrieves the chat history for a shared session."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, session_id FROM shared_chats WHERE share_id = ?", (share_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None
    cursor.execute("SELECT role, content FROM chats WHERE user_id = ? AND session_id = ? ORDER BY timestamp ASC", (row['user_id'], row['session_id']))
    history = cursor.fetchall()
    conn.close()
    return [dict(r) for r in history]

def get_user_uploaded_files(user_id: str) -> list:
    """Retrieves distinct filenames uploaded by a user from the database."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT DISTINCT file_name FROM uploaded_files WHERE user_id = ?", (user_id,))
        files = [row[0] for row in cursor.fetchall()]
        return files
    except Exception as e:
        print(f"⚠️ [SQLite DB] Failed to query uploaded files: {e}")
        return []
    finally:
        conn.close()

def add_user_workspace(user_id: str, path: str):
    """Adds a new workspace path for the user."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO user_workspaces (user_id, path, is_active) VALUES (?, ?, 0)",
            (user_id, path)
        )
        conn.commit()
    finally:
        conn.close()

def delete_user_workspace(user_id: str, path: str):
    """Deletes a workspace path for the user."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM user_workspaces WHERE user_id = ? AND path = ?",
            (user_id, path)
        )
        conn.commit()
    finally:
        conn.close()

def get_user_workspaces(user_id: str) -> list:
    """Retrieves all workspaces registered by the user."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT path, is_active FROM user_workspaces WHERE user_id = ?",
            (user_id,)
        )
        return [{"path": row[0], "is_active": bool(row[1])} for row in cursor.fetchall()]
    finally:
        conn.close()

def activate_user_workspace(user_id: str, path: str):
    """Sets a specific workspace path as active for the user, deactivating all others."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE user_workspaces SET is_active = 0 WHERE user_id = ?",
            (user_id,)
        )
        if path != "uploads":
            cursor.execute(
                "UPDATE user_workspaces SET is_active = 1 WHERE user_id = ? AND path = ?",
                (user_id, path)
            )
        conn.commit()
    finally:
        conn.close()

def get_active_user_workspace(user_id: str) -> Optional[str]:
    """Retrieves the active workspace path for the user, returning None if uploads is active."""
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT path FROM user_workspaces WHERE user_id = ? AND is_active = 1 LIMIT 1",
            (user_id,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    finally:
        conn.close()
