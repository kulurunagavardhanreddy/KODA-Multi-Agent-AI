# backend/email_service/processor.py
import json
import sqlite3
import logging
import asyncio
from datetime import datetime
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage

from backend.database.chat_database import DB_PATH
from backend.agents.supervisor import _get_llm
from .permissions import get_email_permissions
from .parser import strip_gmail_quotes

logger = logging.getLogger(__name__)

async def process_incoming_email(
    user_id: str,
    msg_id: str,
    subject: str,
    sender: str,
    body: str,
    received_at_iso: str,
    thread_id: Optional[str] = None,
    gmail_message_count: int = 1,
    thread_history: Optional[str] = None
):
    """Asynchronously processes a new email or thread: runs AI classification, saves/updates metadata, and discards raw text body."""
    # Fast check: Are email permissions enabled?
    perms = get_email_permissions(user_id)
    if not perms.get("enabled"):
        logger.warning("⚠️ Email assistant is disabled for user %s. Ignoring email processing.", user_id)
        return

    # Check began monitoring date filter (mock emails are exempt to avoid timing race conditions in dev sandboxes)
    if not msg_id.startswith("mock_"):
        started_at = perms.get("started_monitoring_at")
        if started_at:
            try:
                started_dt = datetime.fromisoformat(started_at)
                received_dt = datetime.fromisoformat(received_at_iso)
                if received_dt < started_dt:
                    logger.info("🛡️ [Privacy Guard] Skipping email received prior to monitoring start date: %s", subject)
                    return
            except Exception as filter_err:
                logger.warning("Error evaluating started_monitoring_at check: %s", filter_err)

    body_cleaned = strip_gmail_quotes(body)

    if not thread_id:
        thread_id = msg_id

    if not thread_history:
        thread_history = f"From: {sender}\nDate: {received_at_iso}\nContent: {body_cleaned}"

    # Calculate reading time (roughly 200 words per minute average reading speed)
    words_count = len(body_cleaned.split())
    reading_time_sec = max(10, int((words_count / 200) * 60))

    # Defaults in case of parsing failures
    priority = "Medium"
    confidence_score = 100.0
    status = "Open"
    conversation_stage = "New"
    thread_health = "Healthy"
    needs_response = 0
    last_sender_type = "Customer"
    thread_summary = subject or "No Subject"
    suggested_action = "Standard email update."
    suggested_action_type = "Monitor"

    # Fetch existing thread data from DB to preserve original incident details and track status transitions
    existing_row = None
    previous_status = None
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM email_analysis WHERE gmail_thread_id = ?", (thread_id,))
        existing_row = cursor.fetchone()
        if existing_row:
            previous_status = existing_row["status"]
    except Exception as db_err:
        logger.warning("Error loading existing thread row: %s", db_err)
    finally:
        conn.close()

    # 2. AI Intelligence processing
    if perms.get("can_summarize") or perms.get("can_prioritize"):
        try:
            llm = _get_llm()
            sys_msg = SystemMessage(content=(
                "You are the core analysis engine of KODA Inbox Intelligence.\n"
                "Review the email parameters (original incident details, combined conversation history of the thread, and previous status if available) and return a valid JSON object matching the following structure:\n"
                "{\n"
                "  \"priority\": \"Critical\" | \"High\" | \"Medium\" | \"Low\",\n"
                "  \"confidence_score\": float (0.0 to 100.0),\n"
                "  \"status\": \"Open\" | \"Waiting for Internal Action\" | \"Waiting for Customer\" | \"Resolved\" | \"Closed\",\n"
                "  \"conversation_stage\": \"New\" | \"Follow-up\" | \"Reminder\" | \"Escalation\" | \"Resolved\" | \"Closed\",\n"
                "  \"thread_health\": \"Healthy\" | \"At Risk\" | \"Escalating\",\n"
                "  \"needs_response\": boolean,\n"
                "  \"last_sender_type\": \"Customer\" | \"Internal\" | \"System\" | \"Bot\" | \"Support Agent\",\n"
                "  \"thread_summary\": \"A short evolving summary of the entire thread so far (incorporating new replies).\",\n"
                "  \"suggested_action\": \"A concise suggested next step action description (1 sentence).\",\n"
                "  \"suggested_action_type\": \"Reply\" | \"Investigate\" | \"Escalate\" | \"Close\" | \"Monitor\" | \"Follow-up\"\n"
                "}\n"
                "Guidelines for Suggested Actions:\n"
                "- Do NOT assign 'Monitor' or generic review actions for critical issues, outages, or persistent customer queries.\n"
                "- For active service outages or technical errors, suggest concrete tasks like 'Investigate Production API Outage' or 'Escalate Incident to On-Call Engineer' with a type of 'Investigate' or 'Escalate'.\n"
                "- When the thread is waiting for internal response (especially after repeated customer follow-ups), suggest 'Reply with Status Update' with a type of 'Reply'.\n"
                "- Only recommend 'Monitor' or 'Close' for marketing newsletters, confirmations, or fully resolved threads.\n"
                "Do NOT include any extra formatting, markdown backticks, or comments. Output raw JSON only."
            ))
            
            orig_snd = existing_row['original_sender'] if existing_row else sender
            prompt_content = (
                f"Subject: {subject}\n"
                f"Original Sender: {orig_snd}\n"
                f"Previous Status: {previous_status or 'None'}\n"
                f"Combined Thread History (Latest Last):\n"
                f"{thread_history[:4000]}"
            )
            user_msg = HumanMessage(content=prompt_content)
            
            resp = await llm.ainvoke([sys_msg, user_msg])
            raw_text = resp.content.strip()
            
            # Clean JSON markdown wrappings if present
            if raw_text.startswith("```"):
                lines = raw_text.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    raw_text = "\n".join(lines[1:-1]).strip()
            
            analysis = json.loads(raw_text)
            priority = analysis.get("priority", priority)
            confidence_score = float(analysis.get("confidence_score", confidence_score))
            status = analysis.get("status", status)
            conversation_stage = analysis.get("conversation_stage", conversation_stage)
            thread_health = analysis.get("thread_health", thread_health)
            needs_response = 1 if analysis.get("needs_response", False) else 0
            last_sender_type = analysis.get("last_sender_type", last_sender_type)
            thread_summary = analysis.get("thread_summary", thread_summary)
            suggested_action = analysis.get("suggested_action", suggested_action)
            suggested_action_type = analysis.get("suggested_action_type", suggested_action_type)
        except Exception as ai_err:
            logger.error("❌ [AI Email Process Error] %s. Falling back to default metrics.", ai_err)

    # 3. Store or update thread in the database
    orig_subj = existing_row["original_subject"] if existing_row else subject
    orig_body = existing_row["original_body"] if existing_row else body_cleaned[:1000]
    orig_sender = existing_row["original_sender"] if existing_row else sender
    orig_received_at = existing_row["original_received_at"] if existing_row else received_at_iso

    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO email_analysis (
                user_id, gmail_message_id, gmail_thread_id, subject,
                original_subject, original_body, original_sender, original_received_at,
                thread_summary, latest_message_body, latest_message_sender, latest_received_at, gmail_message_count,
                priority, confidence_score, status, previous_status, conversation_stage, thread_health,
                needs_response, last_sender_type, suggested_action, suggested_action_type, last_activity_at,
                sender, received_at, summary, reason, stars, estimated_time
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(gmail_thread_id) DO UPDATE SET
                gmail_message_id=excluded.gmail_message_id,
                thread_summary=excluded.thread_summary,
                latest_message_body=excluded.latest_message_body,
                latest_message_sender=excluded.latest_message_sender,
                latest_received_at=excluded.latest_received_at,
                gmail_message_count=excluded.gmail_message_count,
                priority=excluded.priority,
                confidence_score=excluded.confidence_score,
                status=excluded.status,
                previous_status=excluded.previous_status,
                conversation_stage=excluded.conversation_stage,
                thread_health=excluded.thread_health,
                needs_response=excluded.needs_response,
                last_sender_type=excluded.last_sender_type,
                suggested_action=excluded.suggested_action,
                suggested_action_type=excluded.suggested_action_type,
                last_activity_at=excluded.last_activity_at,
                
                -- Legacy fallbacks
                received_at=excluded.received_at,
                summary=excluded.thread_summary,
                estimated_time=excluded.estimated_time
        ''', (
            user_id, msg_id, thread_id, subject,
            orig_subj, orig_body, orig_sender, orig_received_at,
            thread_summary, body_cleaned[:1000], sender, received_at_iso, gmail_message_count,
            priority, confidence_score, status, previous_status, conversation_stage, thread_health,
            needs_response, last_sender_type, suggested_action, suggested_action_type, received_at_iso,
            orig_sender, received_at_iso, thread_summary, suggested_action, 3, reading_time_sec
        ))
        conn.commit()
    finally:
        conn.close()
