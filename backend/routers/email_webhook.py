# backend/routers/email_webhook.py
import os
import json
import sqlite3
import logging
import asyncio
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from backend.database.chat_database import DB_PATH
from backend.email_service import sync_new_emails

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email", tags=["email_webhook"])

class PubSubMessage(BaseModel):
    message: dict
    subscription: str

@router.post("/webhook")
async def email_webhook_endpoint(request: Request, payload: PubSubMessage):
    """
    Receives Google Pub/Sub push notifications.
    Verifies the Google-signed JWT token in the Authorization: Bearer header.
    """
    logger.info(f"Headers: {dict(request.headers)}")
    logger.info(f"Query Params: {dict(request.query_params)}")
    
    auth_header = request.headers.get("Authorization")
    secret = request.query_params.get("secret")
    
    authenticated = False
    
    # 1. Google JWT token verification
    if auth_header and auth_header.startswith("Bearer "):
        jwt_token = auth_header.split(" ")[1].strip()
        try:
            x_proto = request.headers.get("x-forwarded-proto", "https")
            x_host = request.headers.get("x-forwarded-host", request.headers.get("host", "localhost:8000"))
            dynamic_aud = f"{x_proto}://{x_host}/api/email/webhook"
            
            audiences = [
                dynamic_aud,
                "https://citrus-tibia-bluish.ngrok-free.dev/api/email/webhook",
                "http://localhost:8000/api/email/webhook"
            ]
            try:
                from backend.config import NGROK_DOMAIN
                if NGROK_DOMAIN:
                    audiences.append(f"https://{NGROK_DOMAIN}/api/email/webhook")
            except Exception:
                pass
                
            verified_claims = None
            for aud in audiences:
                try:
                    verified_claims = id_token.verify_oauth2_token(jwt_token, google_requests.Request(), aud)
                    if verified_claims.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
                        raise ValueError("Invalid issuer.")
                    break
                except Exception:
                    continue
                    
            if not verified_claims:
                # Fallback to verify token structure/signature without strict audience check
                verified_claims = id_token.verify_oauth2_token(jwt_token, google_requests.Request(), audience=None)
                if verified_claims.get("iss") not in ["accounts.google.com", "https://accounts.google.com"]:
                    raise ValueError("Invalid issuer on fallback check.")
                    
            logger.info(f"🟢 [Webhook Auth] Authorized via Google JWT. Service Account: {verified_claims.get('email')}")
            authenticated = True
        except Exception as auth_ex:
            logger.warning(f"⚠️ [Webhook Auth JWT Mismatch] Attempted JWT verify but failed: {auth_ex}")
            
    # 2. Fallback to URL shared secret check
    if not authenticated:
        expected_secret = os.getenv("WEBHOOK_SECRET")
        if not expected_secret:
            # Fall back to default key ONLY in local development mode
            from backend.email_service import DEVELOPMENT_MODE
            if DEVELOPMENT_MODE:
                expected_secret = "koda_pubsub_secret_default_key"
                
        if expected_secret and secret == expected_secret:
            logger.info("🟢 [Webhook Auth] Authorized via shared URL secret parameter.")
            authenticated = True
            
    if not authenticated:
        logger.warning("❌ [Webhook Auth] Unauthorized webhook access attempt — missing/invalid credentials.")
        raise HTTPException(status_code=401, detail="Unauthorized webhook request.")

    try:
        msg = payload.message
        data_b64 = msg.get("data")
        if not data_b64:
            raise Exception("No data payload in Pub/Sub message.")
            
        import base64
        decoded_bytes = base64.b64decode(data_b64)
        event_data = json.loads(decoded_bytes.decode("utf-8"))
        
        email_address = event_data.get("emailAddress")
        history_id = str(event_data.get("historyId"))
        
        if not email_address or not history_id:
            raise Exception("Missing emailAddress or historyId in decodable payload.")
            
        logger.info(f"📡 [Webhook Received] Inbox updated for: {email_address}, history_id: {history_id}")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM email_permissions WHERE connected_email = ? AND enabled = 1", (email_address,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            logger.warning(f"⚠️ [Webhook] No enabled user connection found for email address: {email_address}")
            return {"status": "ignored", "reason": "No active user found."}
            
        user_id = row[0]
        asyncio.create_task(sync_new_emails(user_id, history_id))
        return {"status": "processed"}
    except Exception as ex:
        logger.error(f"❌ [Webhook Endpoint Error] {ex}")
        raise HTTPException(status_code=400, detail=f"Bad request payload: {str(ex)}")
