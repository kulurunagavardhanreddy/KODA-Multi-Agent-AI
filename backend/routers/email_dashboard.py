# backend/routers/email_dashboard.py
from fastapi import APIRouter, Depends, HTTPException
from backend.core.security import get_current_user
from backend.email_service import (
    get_email_permissions, get_email_digest_dashboard, generate_mock_sandbox_emails
)

router = APIRouter(prefix="/api/email", tags=["email_dashboard"])

@router.get("/dashboard")
def get_email_dashboard_endpoint(current_user: dict = Depends(get_current_user)):
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot access Inbox Intelligence.")
    perms = get_email_permissions(current_user["user_id"])
    if not perms.get("enabled"):
        raise HTTPException(status_code=403, detail="KODA Inbox Intelligence is disabled. Enable it in settings first.")
    return get_email_digest_dashboard(current_user["user_id"])

@router.post("/dev-mock-generate")
async def dev_mock_generate_endpoint(current_user: dict = Depends(get_current_user)):
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot access Inbox Intelligence.")
    success = await generate_mock_sandbox_emails(current_user["user_id"])
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate mock emails.")
    return {"status": "success"}
