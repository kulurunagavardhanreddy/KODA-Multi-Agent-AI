# backend/routers/email_auth.py
import os
import uuid
import logging
import requests
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from backend.core.security import get_current_user
from backend.config import GOOGLE_CLIENT_ID
from backend.email_service import save_email_permissions, create_gmail_watch

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email", tags=["email_auth"])

@router.get("/auth-url")
def get_email_auth_url(request: Request, current_user: dict = Depends(get_current_user)):
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot access Inbox Intelligence.")
    
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    state = current_user["user_id"]
    
    # Dev / local mode: skip Google entirely, redirect to our own mock callback
    if not client_secret or client_secret in ("", "your-google-client-secret"):
        mock_url = f"{request.url.scheme}://{request.url.netloc}/api/email/oauth-callback?code=mock_dev_bypass&state={state}"
        return {"auth_url": mock_url, "dev_mode": True}
    
    # Production: real Google OAuth consent URL
    client_id = GOOGLE_CLIENT_ID
    redirect_uri = f"{request.url.scheme}://{request.url.netloc}/api/email/oauth-callback"
    scopes = "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/userinfo.email"
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        "response_type=code&"
        f"scope={scopes}&"
        "access_type=offline&"
        "prompt=consent&"
        f"state={state}"
    )
    return {"auth_url": auth_url, "dev_mode": False}

@router.get("/oauth-callback", response_class=HTMLResponse)
def get_email_oauth_callback(request: Request, code: str, state: str):
    user_id = state
    client_id = GOOGLE_CLIENT_ID
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    
    # If client secret is not configured, fallback to mock generation for local test bypass
    if not client_secret or client_secret == "your-google-client-secret":
        mock_email = "nag1505880@gmail.com"
        mock_refresh = f"mock_refresh_token_{uuid.uuid4().hex}"
        mock_access = f"mock_access_token_{uuid.uuid4().hex}"
        mock_expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        perms = {
            "enabled": 1,
            "connected_email": mock_email,
            "refresh_token": mock_refresh,
            "access_token": mock_access,
            "token_expiry": mock_expiry,
            "can_read": 1,
            "can_summarize": 1,
            "can_prioritize": 1,
            "can_notify": 1,
            "can_send": 0,
            "can_archive": 0,
            "can_delete": 0,
            "can_read_attachments": 0
        }
        save_email_permissions(user_id, perms)
        
        return """
        <html>
          <body style="background:#171717; color:#fff; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; text-align:center; padding: 40px; display:flex; flex-direction:column; align-items:center; justify-content:center; height:80vh;">
            <div style="background:#1e1e1e; border: 1px solid #2f2f2f; border-radius:12px; padding:32px; max-width:400px; box-shadow:0 10px 30px rgba(0,0,0,0.5);">
              <div style="font-size:3rem; margin-bottom:16px;">🟢</div>
              <h2 style="margin-top:0; color:#10a37f;">Mock Connection Successful</h2>
              <p style="color:#b4b4b4; font-size:0.9rem; line-height:1.5;">KODA Inbox Intelligence is now connected in Sandbox Mode to <strong>nag1505880@gmail.com</strong>.</p>
              <p style="color:#8e8e93; font-size:0.8rem; margin-top:20px;">Closing window and loading your dashboard...</p>
            </div>
            <script>
              setTimeout(() => {
                if (window.opener) {
                  window.opener.postMessage("email_connected", "*");
                  window.close();
                } else {
                  window.location.href = "/";
                }
              }, 1500);
            </script>
          </body>
        </html>
        """
        
    try:
        # Real OAuth token exchange
        redirect_uri = f"{request.url.scheme}://{request.url.netloc}/api/email/oauth-callback"
        token_url = "https://oauth2.googleapis.com/token"
        payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code"
        }
        res = requests.post(token_url, data=payload, timeout=10)
        if res.status_code != 200:
            raise Exception(f"Google Token endpoint returned {res.status_code}: {res.text}")
            
        token_data = res.json()
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token")
        expires_in = token_data.get("expires_in", 3600)
        
        # Get user email
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        userinfo_res = requests.get(userinfo_url, headers=headers, timeout=10)
        if userinfo_res.status_code != 200:
            raise Exception("Failed to retrieve user email profile from Google API.")
            
        profile = userinfo_res.json()
        connected_email = profile.get("email")
        if not connected_email:
            raise Exception("No email address returned from Google Profile.")
            
        # Save credentials in Koda permission store
        perms = {
            "enabled": 1,
            "connected_email": connected_email,
            "refresh_token": refresh_token,
            "access_token": access_token,
            "token_expiry": (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat(),
            "can_read": 1,
            "can_summarize": 1,
            "can_prioritize": 1,
            "can_notify": 1,
            "can_send": 0,
            "can_archive": 0,
            "can_delete": 0,
            "can_read_attachments": 0
        }
        save_email_permissions(user_id, perms)
        
        return f"""
        <html>
          <body style="background:#171717; color:#fff; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; text-align:center; padding: 40px; display:flex; flex-direction:column; align-items:center; justify-content:center; height:80vh;">
            <div style="background:#1e1e1e; border: 1px solid #2f2f2f; border-radius:12px; padding:32px; max-width:400px; box-shadow:0 10px 30px rgba(0,0,0,0.5);">
              <div style="font-size:3rem; margin-bottom:16px;">🟢</div>
              <h2 style="margin-top:0; color:#10a37f;">Connection Successful</h2>
              <p style="color:#b4b4b4; font-size:0.9rem; line-height:1.5;">KODA Inbox Intelligence is now connected to <strong>{connected_email}</strong>.</p>
              <p style="color:#8e8e93; font-size:0.8rem; margin-top:20px;">Closing window and loading your dashboard...</p>
            </div>
            <script>
              setTimeout(() => {{
                if (window.opener) {{
                  window.opener.postMessage("email_connected", "*");
                  window.close();
                }} else {{
                  window.location.href = "/";
                }}
              }}, 1500);
            </script>
          </body>
        </html>
        """
    except Exception as e:
        return f"""
        <html>
          <body style="background:#171717; color:#fff; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; text-align:center; padding: 40px; display:flex; flex-direction:column; align-items:center; justify-content:center; height:80vh;">
            <div style="background:#1e1e1e; border: 1px solid #ef4444; border-radius:12px; padding:32px; max-width:400px; box-shadow:0 10px 30px rgba(0,0,0,0.5);">
              <div style="font-size:3rem; margin-bottom:16px;">❌</div>
              <h2 style="margin-top:0; color:#ef4444;">OAuth Connection Failed</h2>
              <p style="color:#b4b4b4; font-size:0.9rem; line-height:1.5;">Error details: {str(e)}</p>
              <button onclick="window.close()" style="margin-top:20px; background:#2f2f2f; color:#fff; border:none; padding:10px 20px; border-radius:6px; cursor:pointer;">Close Window</button>
            </div>
          </body>
        </html>
        """

@router.post("/connect-token")
async def connect_email_token_endpoint(request: Request, current_user: dict = Depends(get_current_user)):
    """
    Accepts a Gmail access token or authorization code obtained by the browser.
    If code is provided, exchanges it for both access and refresh tokens.
    """
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot access Inbox Intelligence.")
    
    body = await request.json()
    code = body.get("code", "").strip()
    access_token = body.get("access_token", "").strip()
    
    refresh_token = None
    expires_in = 3600
    
    if code:
        client_id = GOOGLE_CLIENT_ID
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
        if not client_secret or client_secret == "your-google-client-secret":
            # Mock dev mode bypass
            access_token = f"mock_access_token_{uuid.uuid4().hex}"
            refresh_token = f"mock_refresh_token_{uuid.uuid4().hex}"
            expires_in = 3600
        else:
            import requests as req
            token_url = "https://oauth2.googleapis.com/token"
            payload = {
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": "postmessage",
                "grant_type": "authorization_code"
            }
            res = req.post(token_url, data=payload, timeout=10)
            if res.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Failed to exchange auth code: {res.text}")
            token_data = res.json()
            access_token = token_data["access_token"]
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in", 3600)
            
    if not access_token:
        raise HTTPException(status_code=400, detail="access_token or code is required.")
    
    # Verify token by fetching user's Gmail address from Google
    import requests as req
    userinfo_res = req.get(
        "https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=8
    )
    if userinfo_res.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired Google access token.")
    
    profile = userinfo_res.json()
    connected_email = profile.get("email")
    if not connected_email:
        raise HTTPException(status_code=400, detail="Could not retrieve email from Google profile.")
    
    token_expiry = (datetime.now(timezone.utc) + timedelta(seconds=expires_in)).isoformat()
    
    perms = {
        "enabled": 1,
        "connected_email": connected_email,
        "refresh_token": refresh_token,
        "access_token": access_token,
        "token_expiry": token_expiry,
        "can_read": 1,
        "can_summarize": 1,
        "can_prioritize": 1,
        "can_notify": 1,
        "can_send": 0,
        "can_archive": 0,
        "can_delete": 0,
        "can_read_attachments": 0
    }
    save_email_permissions(current_user["user_id"], perms)
    create_gmail_watch(current_user["user_id"])
    return {"status": "connected", "email": connected_email}
