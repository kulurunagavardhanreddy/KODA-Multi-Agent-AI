# backend/routers/history.py
from fastapi import APIRouter, Depends, HTTPException
from backend.core.security import get_current_user
from backend.database.chat_database import get_history, soft_delete_session

router = APIRouter(tags=["history"])

@router.get("/history/{session_id}")
def get_history_endpoint(session_id: str, limit: int = 20, offset: int = 0, current_user: dict = Depends(get_current_user)):
    """Retrieves the chat history for a specific session from the SQLite database."""
    if current_user.get("is_guest"):
        return {"history": []}
    try:
        history = get_history(current_user["user_id"], session_id, limit, offset)
        return {"history": history}
    except Exception as e:
        return {"error": str(e)}

@router.delete("/api/history/{session_id}")
def soft_delete_chat(session_id: str, current_user: dict = Depends(get_current_user)):
    """Soft deletes a chat session by marking the deleted_at timestamp."""
    if current_user.get("is_guest"):
        return {"status": "ignored"}
    try:
        soft_delete_session(current_user["user_id"], session_id)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
