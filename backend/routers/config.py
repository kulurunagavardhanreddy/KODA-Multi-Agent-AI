# backend/routers/config.py
from fastapi import APIRouter, Request
from backend.config import GOOGLE_CLIENT_ID
from backend.core.middleware import limiter

router = APIRouter(prefix="/api", tags=["config"])

@router.get("/config")
def get_config():
    return {"google_client_id": GOOGLE_CLIENT_ID}

@router.get("/health")
@limiter.limit("10/minute")
def health_check(request: Request):
    return {"status": "ok", "message": "🤖 Chatbot Agent API is running!"}
