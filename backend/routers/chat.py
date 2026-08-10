# backend/routers/chat.py
import json
import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, AIMessage

from backend.core.middleware import limiter
from backend.core.security import get_current_user
from backend.agents.supervisor import chat_with_agent, generate_chat_title
from backend.database.chat_database import save_message

router = APIRouter(tags=["chat"])

class MessageModel(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: Optional[str] = ""
    messages: Optional[List[MessageModel]] = []
    session_id: str = "default_session"
    user_location: Optional[str] = ""
    bot_name: Optional[str] = ""
    image_b64: Optional[str] = ""
    is_temporary: bool = False

class TitleRequest(BaseModel):
    message: str

@router.post("/chat")
@limiter.limit("30/minute")
async def chat_endpoint(request: Request, payload: ChatRequest, current_user: dict = Depends(get_current_user)):
    """Secured endpoint that ensures chats are mapped to the requesting user."""
    try:
        user_msg_content = ""
        if payload.messages:
            user_msg_content = payload.messages[-1].content
        elif payload.message:
            user_msg_content = payload.message

        if not user_msg_content:
            raise HTTPException(status_code=400, detail="No message content provided.")

        should_save = not current_user.get("is_guest") and not payload.is_temporary

        if should_save:
            # Save text to DB. Add a simple text tag for the image to avoid saving 10MB of base64 text into SQLite!
            db_content = user_msg_content
            if payload.image_b64:
                db_content += "\n[Image Attached]"
            # Async non-blocking write
            asyncio.create_task(asyncio.to_thread(save_message, current_user["user_id"], payload.session_id, "user", db_content))

        # Always trust the frontend's meticulously constructed branch history.
        langchain_history = []
        if payload.messages:
            recent_msgs = payload.messages[-15:]
            langchain_history = [
                HumanMessage(content=m.content) if m.role == 'user' else AIMessage(content=m.content)
                for m in recent_msgs
            ]
        else:
            langchain_history.append(HumanMessage(content=user_msg_content))

        async def stream_generator():
            full_reply_list = []
            try:
                async for chunk in chat_with_agent(langchain_history, payload.user_location, current_user["user_id"], payload.image_b64, payload.session_id):
                    if await request.is_disconnected():
                        print("⚠️ [SSE] Client disconnected. Halting AI generation to save resources.")
                        break
                    if isinstance(chunk, dict):
                        if "status" in chunk:
                            yield f"data: {json.dumps({'status': chunk['status']})}\n\n"
                        elif "error" in chunk:
                            yield f"data: {json.dumps({'error': chunk['error']})}\n\n"
                    else:
                        full_reply_list.append(chunk)
                        yield f"data: {json.dumps({'chunk': chunk})}\n\n"
            except Exception as e:
                print(f"❌ [Stream Error] {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            finally:
                full_reply = "".join(full_reply_list)
                if full_reply and should_save:
                    # Save the rich reply to SQLite so the UI can parse followups and sources on load
                    asyncio.create_task(asyncio.to_thread(save_message, current_user["user_id"], payload.session_id, "assistant", full_reply))

        return StreamingResponse(
            stream_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    except Exception as e:
        print(f"❌ [Chat Endpoint Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/generate-title")
async def generate_title_endpoint(request: TitleRequest, current_user: dict = Depends(get_current_user)):
    """Generates a short, professional chat title based on the first message."""
    title = await generate_chat_title(request.message)
    return {"title": title}
