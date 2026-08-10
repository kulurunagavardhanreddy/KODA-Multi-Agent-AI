# vector_memory.py

import hashlib
import datetime
from backend.loaders.document_loader import get_memory_vector_store
from langchain_core.documents import Document
from qdrant_client.http import models

def save_conversation_memory_vector(
    user_id: str, 
    session_id: str, 
    category: str, 
    summary_text: str,
    memory_type: str = "general",
    entities: list = None,
    importance: int = 5
):
    """Upserts granular memory summary text to Qdrant vector storage with rich metadata payload."""
    try:
        vector_store = get_memory_vector_store()
        doc_id = hashlib.sha256(f"{session_id}_{category}".encode()).hexdigest()
        
        now_str = datetime.datetime.now().isoformat()
        
        doc = Document(
            page_content=summary_text,
            metadata={
                "user_id": user_id, 
                "session_id": session_id, 
                "category": category,
                "memory_type": memory_type,
                "entities": entities or [],
                "importance": importance,
                "created_at": now_str,
                "last_accessed": now_str,
                "access_count": 0
            }
        )
        vector_store.add_documents([doc], ids=[doc_id])
        print(f"🧠 [Qdrant DB] Successfully upserted '{category}' memory to vector storage.")
    except Exception as qe:
        print(f"⚠️ [Qdrant DB] Failed to save granular memory to vector storage: {qe}")

def search_conversation_memories(user_id: str, query: str, limit: int = 3) -> str:
    """Searches Qdrant for semantically relevant past conversation summaries for the user."""
    try:
        vector_store = get_memory_vector_store()
        qdrant_filter = models.Filter(
            must=[models.FieldCondition(key="metadata.user_id", match=models.MatchValue(value=user_id))]
        )
        # Fetch Top similarity matches
        docs = vector_store.similarity_search(query, k=limit, filter=qdrant_filter)
        
        if not docs: return ""
        
        from backend.database.chat_database import increment_memory_access
        retrieved_list = []
        
        for doc in docs:
            category = doc.metadata.get("category", "General")
            session_id = doc.metadata.get("session_id", "")
            if session_id:
                try:
                    increment_memory_access(user_id, session_id, category)
                except Exception as ie:
                    print(f"⚠️ [Vector Memory] Failed to increment access metadata in SQLite: {ie}")
            
            m_type = doc.metadata.get("memory_type", "general")
            importance = doc.metadata.get("importance", 5)
            retrieved_list.append(f"- [{category} ({m_type}, Importance: {importance})]: {doc.page_content}")
            
        return "\n".join(retrieved_list)
    except Exception as e:
        print(f"⚠️ [Qdrant DB] Semantic memory search failed: {e}")
        return ""
