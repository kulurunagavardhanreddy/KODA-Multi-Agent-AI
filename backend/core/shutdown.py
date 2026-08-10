# backend/core/shutdown.py
import logging
from backend.integrations.mcp import mcp_manager
from pyngrok import ngrok

logger = logging.getLogger(__name__)

async def shutdown(app):
    # Stop MCP servers
    try:
        await mcp_manager.stop_all_servers()
        print("📡 [MCP Manager] All MCP servers shut down successfully.")
    except Exception as se:
        print(f"⚠️ [MCP Shutdown Error] Failed to stop MCP Manager: {se}")

    # Close Ngrok tunnel
    public_url = getattr(app.state, "public_url", None)
    if public_url:
        print("\n🛑 Closing Ngrok Tunnel...")
        try:
            ngrok.disconnect(public_url)
            ngrok.kill()
        except Exception as e:
            print(f"⚠️ [Shutdown Warning] Ngrok close failed: {e}")

    # Cancel background workers
    backup_task = getattr(app.state, "backup_task", None)
    if backup_task:
        backup_task.cancel()

    cleanup_task = getattr(app.state, "cleanup_task", None)
    if cleanup_task:
        cleanup_task.cancel()

    email_task = getattr(app.state, "email_task", None)
    if email_task:
        email_task.cancel()
