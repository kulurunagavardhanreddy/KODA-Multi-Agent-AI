# backend/routers/auth.py
import jwt
import uuid
import sqlite3
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, EmailStr
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from backend.core.config import SECRET_KEY, ALGORITHM
from backend.config import GOOGLE_CLIENT_ID
from backend.database.chat_database import create_user, verify_user

router = APIRouter(prefix="/api", tags=["authentication"])

class UserSignup(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)
    
class UserLogin(BaseModel):
    email: EmailStr
    password: str

class GoogleToken(BaseModel):
    token: str

@router.post("/signup")
def signup_endpoint(user: UserSignup):
    """Handles new user registration."""
    success = create_user(user.email, user.username, user.password)
    if success:
        return {"message": "User created successfully"}
    raise HTTPException(status_code=400, detail="Email is already registered")

@router.post("/login")
def login_endpoint(user: UserLogin):
    """Handles user authentication."""
    user_data = verify_user(user.email, user.password)
    if user_data:
        expire = datetime.now(timezone.utc) + timedelta(days=7)
        payload = {
            "sub": user_data["user_id"],
            "username": user_data["username"],
            "exp": expire
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return {"message": "Login successful", "access_token": token, "username": user_data["username"], "email": user.email}
    raise HTTPException(status_code=401, detail="Invalid email or password")

@router.post("/guest-login")
def guest_login_endpoint():
    """Handles guest authentication without saving to DB."""
    expire = datetime.now(timezone.utc) + timedelta(days=1)
    guest_id = f"guest_{uuid.uuid4().hex}"
    payload = {
        "sub": guest_id,
        "username": "Guest",
        "is_guest": True,
        "exp": expire
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return {"message": "Guest login successful", "access_token": token, "username": "Guest", "email": "Guest Session"}

@router.post("/google-login")
def google_login_endpoint(data: GoogleToken):
    """Handles Google OAuth Token verification."""
    if not GOOGLE_CLIENT_ID or GOOGLE_CLIENT_ID == "your_google_client_id_here":
        raise HTTPException(status_code=500, detail="Google Client ID is not configured on the server.")
    try:
        idinfo = id_token.verify_oauth2_token(data.token, google_requests.Request(), GOOGLE_CLIENT_ID)
        email = idinfo.get("email")
        name = idinfo.get("name", "Google User")
        
        # --- AUTO-MERGE OR CREATE GOOGLE ACCOUNT ---
        conn = sqlite3.connect("chat_history.db")
        c = conn.cursor()
        
        # 🛡️ DYNAMIC COLUMN MAPPING: Prevents silent failures if your DB uses different names (like 'id' or 'password_hash')
        c.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in c.fetchall()]
        id_col = "user_id" if "user_id" in columns else "id"
        pwd_col = "password" if "password" in columns else "password_hash"
        
        c.execute(f"SELECT {id_col} FROM users WHERE email = ?", (email,))
        row = c.fetchone()
        if row:
            user_id = row[0] # Account exists (Native or Google), merge them!
        else:
            user_id = uuid.uuid4().hex
            c.execute(f"INSERT INTO users ({id_col}, email, username, {pwd_col}) VALUES (?, ?, ?, ?)", 
                      (user_id, email, name, "google_oauth_bypass"))
            conn.commit()
        conn.close()
        # -----------------------------------------
        
        expire = datetime.now(timezone.utc) + timedelta(days=7)
        payload = {
            "sub": user_id,
            "username": name,
            "exp": expire
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return {"message": "Google login successful", "access_token": token, "username": name, "email": email}
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token")
