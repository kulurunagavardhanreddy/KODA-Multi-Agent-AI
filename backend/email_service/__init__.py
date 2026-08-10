# backend/email_service/__init__.py
from .crypto import encrypt_password, decrypt_password
from .permissions import (
    get_email_permissions,
    save_email_permissions,
    disconnect_email_service,
    update_sync_status,
    save_gmail_watch_info,
    save_latest_history_id
)
from .oauth import refresh_google_access_token
from .watch import is_watch_active, create_gmail_watch
from .parser import strip_gmail_quotes, parse_message_resource, sync_gmail_thread
from .processor import process_incoming_email
from .history import sync_new_emails
from .dashboard import get_email_digest_dashboard
from .mock import generate_mock_sandbox_emails, DEVELOPMENT_MODE
from .worker import (
    email_polling_worker,
    check_and_sync_user,
    notify_db_updated_listeners,
    db_update_callbacks
)
