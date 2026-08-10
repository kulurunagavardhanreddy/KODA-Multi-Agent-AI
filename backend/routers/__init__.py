# backend/routers/__init__.py
from backend.routers.auth import router as auth_router
from backend.routers.chat import router as chat_router
from backend.routers.upload import router as upload_router
from backend.routers.workspace import router as workspace_router
from backend.routers.history import router as history_router
from backend.routers.translate import router as translate_router
from backend.routers.websocket import router as websocket_router
from backend.routers.share import router as share_router
from backend.routers.sync import router as sync_router
from backend.routers.config import router as config_router

# Split email routers
from backend.routers.email_auth import router as email_auth_router
from backend.routers.email_settings import router as email_settings_router
from backend.routers.email_dashboard import router as email_dashboard_router
from backend.routers.email_webhook import router as email_webhook_router
from backend.routers.email_notifications import router as email_notifications_router

from backend.routers.web import router as web_router

def register_routes(app):
    app.include_router(web_router)
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(upload_router)
    app.include_router(workspace_router)
    app.include_router(history_router)
    app.include_router(translate_router)
    app.include_router(websocket_router)
    app.include_router(share_router)
    app.include_router(sync_router)
    app.include_router(config_router)
    
    # Register split email routers
    app.include_router(email_auth_router)
    app.include_router(email_settings_router)
    app.include_router(email_dashboard_router)
    app.include_router(email_webhook_router)
    app.include_router(email_notifications_router)
