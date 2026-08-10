# backend/routers/email_settings.py
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.core.security import get_current_user
from backend.email_service import (
    get_email_permissions, save_email_permissions, create_gmail_watch, disconnect_email_service
)

router = APIRouter(prefix="/api/email", tags=["email_settings"])

class EmailPermissionsModel(BaseModel):
    enabled: int
    connected_email: Optional[str] = None
    app_password: Optional[str] = None
    refresh_token: Optional[str] = None
    access_token: Optional[str] = None
    token_expiry: Optional[str] = None
    history_id: Optional[str] = None
    watch_expiration: Optional[str] = None
    can_read: int
    can_summarize: int
    can_prioritize: int
    can_notify: int
    can_send: int
    can_archive: int
    can_delete: int
    can_read_attachments: int

class EmailDisconnectRequest(BaseModel):
    delete_data: bool = False

@router.get("/settings")
def get_email_settings_endpoint(current_user: dict = Depends(get_current_user)):
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot access Inbox Intelligence.")
    return get_email_permissions(current_user["user_id"])

@router.post("/settings")
def save_email_settings_endpoint(payload: EmailPermissionsModel, current_user: dict = Depends(get_current_user)):
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot access Inbox Intelligence.")
    res = save_email_permissions(current_user["user_id"], payload.model_dump())
    if payload.enabled:
        create_gmail_watch(current_user["user_id"])
    return res

@router.post("/disconnect")
def disconnect_email_endpoint(payload: EmailDisconnectRequest, current_user: dict = Depends(get_current_user)):
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot access Inbox Intelligence.")
    success = disconnect_email_service(current_user["user_id"], delete_data=payload.delete_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to disconnect Inbox Intelligence.")
    return {"status": "success"}
