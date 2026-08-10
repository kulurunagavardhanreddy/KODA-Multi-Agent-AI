# backend/email_service/mock.py
import logging
from datetime import datetime, timezone

from .processor import process_incoming_email

logger = logging.getLogger(__name__)

DEVELOPMENT_MODE = True

async def generate_mock_sandbox_emails(user_id: str) -> bool:
    """Populates the development database with mock sandbox emails for demonstration purposes."""
    if not DEVELOPMENT_MODE:
        logger.warning("Attempted to generate sandbox emails outside of DEVELOPMENT_MODE.")
        return False

    mock_emails = [
        {
            "msg_id": "mock_msg_001",
            "subject": "Schedule change: Final Technical Interview schedule",
            "sender": "recruiters@corporation.com",
            "body": "Hi Vardhan, we would like to confirm your technical interview tomorrow at 10:00 AM. Please click the link to join the meeting room. Bring your resume and portfolio.",
            "received_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "msg_id": "mock_msg_002",
            "subject": "Salary Credited: Account statement update",
            "sender": "finance@bank.com",
            "body": "Dear customer, your monthly salary has been successfully credited to your checking account ending in 4921. Balance update is available inside the banking application.",
            "received_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "msg_id": "mock_msg_003",
            "subject": "Urgent review required: Quarterly API report modifications",
            "sender": "lead_manager@company.com",
            "body": "Hi, I need you to compile the system architecture changes for Phase 2 and review the supervisor logs. Please submit the code corrections to me by end of day.",
            "received_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "msg_id": "mock_msg_004",
            "subject": "Vite React component update checklist",
            "sender": "frontend_dev@company.com",
            "body": "Here is the checklist of CSS revisions and Tailwind updates we talked about during lunch. Let me know if you want to pair program on the styling.",
            "received_at": datetime.now(timezone.utc).isoformat()
        },
        {
            "msg_id": "mock_msg_005",
            "subject": "Limited offer: Save 60% on your developer subscription today!",
            "sender": "marketing@platform.io",
            "body": "Don't miss out on our premium builder subscription discounts. Get unlimited server nodes, database storage support, and API hooks for 60% off.",
            "received_at": datetime.now(timezone.utc).isoformat()
        }
    ]

    try:
        for mail in mock_emails:
            await process_incoming_email(
                user_id=user_id,
                msg_id=mail["msg_id"],
                subject=mail["subject"],
                sender=mail["sender"],
                body=mail["body"],
                received_at_iso=mail["received_at"]
            )
        
        # Notify WebSocket listeners of dashboard updates
        from .worker import notify_db_updated_listeners
        await notify_db_updated_listeners()
        return True
    except Exception as e:
        logger.error("❌ [Mock Generate Error] %s", e)
        return False
