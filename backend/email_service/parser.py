# backend/email_service/parser.py
import re
import html
import base64
import email
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def strip_gmail_quotes(text: str) -> str:
    if not text:
        return ""
    
    # 1. Decode HTML entities
    decoded = html.unescape(text)
    
    # 2. Split by common reply headers and patterns
    patterns = [
        r'(?mi)\s*On\s+[\s\S]*?\s+wrote:\s*$',
        r'(?mi)\s*On\s+[\s\S]*?\s+wrote:\s*\r?\n',
        r'(?mi)\s*On\s+[\s\S]*?at\s+[\s\S]*?wrote:\s*',
        r'(?mi)\s*On\s+[\s\S]*?:\s*\r?\n',
        r'(?mi)\s*---\s*Original Message\s*---\s*',
        r'(?mi)\s*________________________________',
        r'(?mi)\s*From:\s+',
        r'(?mi)\s*Sent:\s+',
        r'(?mi)\s*To:\s+',
    ]
    
    cleaned = decoded
    for pat in patterns:
        parts = re.split(pat, cleaned, maxsplit=1)
        if parts:
            cleaned = parts[0]
            
    # 3. Split lines and drop any lines starting with '>'
    lines = cleaned.split("\n")
    filtered_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        filtered_lines.append(line)
        
    cleaned_text = "\n".join(filtered_lines).strip()
    return cleaned_text

def parse_message_resource(msg_data):
    """Parses a Gmail message resource to extract subject, sender, received_at_iso, and text body."""
    payload = msg_data.get("payload", {})
    headers_list = payload.get("headers", [])
    
    subject = "(No Subject)"
    sender = "unknown"
    received_at_iso = None
    
    # Extract headers
    for h in headers_list:
        name = h.get("name", "").lower()
        if name == "subject":
            subject = h.get("value", "")
        elif name == "from":
            sender = h.get("value", "")
        elif name == "date":
            try:
                parsed_date = email.utils.parsedate_to_datetime(h.get("value"))
                received_at_iso = parsed_date.isoformat()
            except Exception:
                pass
                
    if not received_at_iso:
        # Fallback to internalDate
        internal_date = msg_data.get("internalDate")
        if internal_date:
            try:
                received_at_iso = datetime.fromtimestamp(int(internal_date) / 1000.0, timezone.utc).isoformat()
            except Exception:
                received_at_iso = datetime.now(timezone.utc).isoformat()
        else:
            received_at_iso = datetime.now(timezone.utc).isoformat()
            
    # Extract body
    body = ""
    def extract_body(part):
        body_parts = []
        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data", "")
        
        if mime_type == "text/plain" and body_data:
            decoded_bytes = base64.urlsafe_b64decode(body_data)
            body_parts.append(decoded_bytes.decode("utf-8", errors="ignore"))
        elif mime_type == "text/html" and body_data:
            decoded_bytes = base64.urlsafe_b64decode(body_data)
            html_text = decoded_bytes.decode("utf-8", errors="ignore")
            body_parts.append(re.sub(r'<[^>]+>', '', html_text))
            
        parts = part.get("parts", [])
        for p in parts:
            body_parts.extend(extract_body(p))
        return body_parts
        
    body_list = extract_body(payload)
    if body_list:
        body = "\n".join(body_list)
    else:
        body_data = payload.get("body", {}).get("data", "")
        if body_data:
            try:
                decoded_bytes = base64.urlsafe_b64decode(body_data)
                body = decoded_bytes.decode("utf-8", errors="ignore")
                if payload.get("mimeType") == "text/html":
                    body = re.sub(r'<[^>]+>', '', body)
            except Exception:
                pass
                
    return {
        "id": msg_data.get("id"),
        "subject": subject,
        "sender": sender,
        "received_at_iso": received_at_iso,
        "body": body or "Empty body."
    }

async def sync_gmail_thread(user_id: str, thread_id: str, access_token: str) -> bool:
    """Fetches a full Gmail thread, parses it chronologically, keeps the last 10 messages for LLM context, and updates the db."""
    headers = {"Authorization": f"Bearer {access_token}"}
    thread_url = f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{thread_id}"
    res = requests.get(thread_url, headers=headers, timeout=10)
    if res.status_code != 200:
        logger.error(f"❌ Failed to fetch Gmail thread {thread_id}: {res.text}")
        return False
        
    thread_data = res.json()
    messages_raw = thread_data.get("messages", [])
    if not messages_raw:
        return False
        
    # Sort messages chronologically by internalDate
    try:
        messages_raw.sort(key=lambda m: int(m.get("internalDate", 0)))
    except Exception:
        pass
        
    parsed_messages = [parse_message_resource(m) for m in messages_raw]
    total_messages = len(parsed_messages)
    
    # Check if the thread actually contains any messages in INBOX
    latest_raw = messages_raw[-1]
    latest_labels = latest_raw.get("labelIds", [])
    if "INBOX" not in latest_labels:
        logger.info(f"🛡️ Thread {thread_id} latest message is not in INBOX. Skipping.")
        return False
        
    # 1. Original message (first message in thread)
    orig_msg = parsed_messages[0]
    
    # 2. Latest message (last message in thread)
    latest_msg = parsed_messages[-1]
    
    # 3. Last 10 messages for LLM context budget
    context_messages = parsed_messages[-10:]
    
    # Combine context messages into a conversation history block
    history_blocks = []
    for idx, msg in enumerate(context_messages):
        clean_body = "\n".join([line.strip() for line in msg["body"].split("\n") if line.strip()])[:600]
        history_blocks.append(
            f"Message #{idx+1} (ID: {msg['id']})\n"
            f"From: {msg['sender']}\n"
            f"Date: {msg['received_at_iso']}\n"
            f"Content:\n{clean_body}\n"
            f"-----------------------------------------"
        )
    combined_history = "\n".join(history_blocks)
    
    # Import process_incoming_email inside function to break circular dependencies
    from .processor import process_incoming_email
    
    # Call process_incoming_email
    await process_incoming_email(
        user_id=user_id,
        msg_id=latest_msg["id"],
        subject=orig_msg["subject"],
        sender=latest_msg["sender"],
        body=latest_msg["body"],
        received_at_iso=latest_msg["received_at_iso"],
        thread_id=thread_id,
        gmail_message_count=total_messages,
        thread_history=combined_history
    )
    return True
