# backend/routers/share.py
import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from backend.core.security import get_current_user
from backend.database.chat_database import create_share_link, get_shared_history

router = APIRouter(tags=["share"])

# Determine frontend path
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
frontend_path = os.path.join(root_dir, "frontend")

@router.post("/api/share/{session_id}")
def share_chat_endpoint(session_id: str, current_user: dict = Depends(get_current_user)):
    """Generates a shareable link for a chat session."""
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot share chats.")
    share_id = create_share_link(current_user["user_id"], session_id)
    return {"share_url": f"/shared/{share_id}"}

@router.get("/shared/{share_id}")
def view_shared_chat(share_id: str):
    """Serves the frontend UI for a shared chat."""
    return FileResponse(os.path.join(frontend_path, "templates", "index.html"))

@router.get("/api/shared/{share_id}")
def get_shared_chat_data(share_id: str):
    """Returns the chat history payload for a shared chat."""
    history = get_shared_history(share_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Shared chat not found.")
    return {"history": history}
