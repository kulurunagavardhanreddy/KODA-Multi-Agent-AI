# backend/workers/cleanup.py
import asyncio
import logging
from backend.database.chat_database import get_expired_sessions, hard_delete_session
from qdrant_client.http import models

logger = logging.getLogger(__name__)

async def automated_cleanup():
    """Runs continuously and permanently deletes chats soft-deleted > 30 days ago."""
    while True:
        try:
            await asyncio.sleep(86400)  # Check every 24 hours
            sessions_to_delete = get_expired_sessions()

            if sessions_to_delete:
                # 1. Clean Qdrant Vectors
                try:
                    from backend.loaders.document_loader import get_shared_qdrant_client
                    client = get_shared_qdrant_client()
                    for uid, sid in sessions_to_delete:
                        client.delete(
                            collection_name="uploaded_docs",
                            points_selector=models.Filter(
                                must=[
                                    models.FieldCondition(key="metadata.owner", match=models.MatchValue(value=uid)),
                                    models.FieldCondition(key="metadata.session_id", match=models.MatchValue(value=sid))
                                ]
                            )
                        )
                except Exception as qe:
                    logger.error(f"Qdrant cleanup error: {qe}")
                
                # 2. Clean SQLite
                for uid, sid in sessions_to_delete:
                    hard_delete_session(uid, sid)
                    
                print(f"🗑️ [Cleanup] Permanently deleted {len(sessions_to_delete)} old chat sessions.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("❌ [Cleanup Error] %s", e, exc_info=True)
            await asyncio.sleep(60)  # Prevent rapid failure loops
