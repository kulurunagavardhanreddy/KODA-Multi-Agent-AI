# backend/routers/translate.py
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from backend.core.security import get_current_user
from backend.agents.supervisor import llm

router = APIRouter(prefix="/api", tags=["translate"])

class TranslateRequest(BaseModel):
    text: str
    target_language: str

@router.post("/translate")
async def translate_endpoint(request: Request, payload: TranslateRequest, current_user: dict = Depends(get_current_user)):
    """Translates text to the specified target language directly via LLM (Fast Path)."""
    prompt = f"Translate the following text into {payload.target_language}. Provide ONLY the direct {payload.target_language} translation, nothing else. Text:\n\n{payload.text}"
    langchain_history = [HumanMessage(content=prompt)]
    
    async def stream_generator():
        try:
            async for chunk in llm.astream(langchain_history):
                if await request.is_disconnected():
                    break
                if chunk.content:
                    yield f"data: {json.dumps({'chunk': chunk.content})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
