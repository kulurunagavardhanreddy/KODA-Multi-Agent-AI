# backend/email_service/crypto.py
import os
import base64
from cryptography.fernet import Fernet

def _get_fernet_key() -> bytes:
    secret = os.getenv("SECRET_KEY", "koda-dev-fallback-secret-key-change-me")
    key_bytes = secret.encode("utf-8")
    if len(key_bytes) < 32:
        key_bytes = key_bytes + b"0" * (32 - len(key_bytes))
    else:
        key_bytes = key_bytes[:32]
    return base64.urlsafe_b64encode(key_bytes)

def encrypt_password(plain_text: str) -> str:
    if not plain_text:
        return None
    f = Fernet(_get_fernet_key())
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")

def decrypt_password(cipher_text: str) -> str:
    if not cipher_text:
        return None
    f = Fernet(_get_fernet_key())
    try:
        return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception:
        return None
