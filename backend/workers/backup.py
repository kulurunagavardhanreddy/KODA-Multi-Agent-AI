# backend/workers/backup.py
import os
import asyncio
import zipfile
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

async def automated_backup():
    """Runs continuously in the background and backs up the databases every 24 hours."""
    while True:
        try:
            await asyncio.sleep(86400)  # Wait 24 hours
            os.makedirs("backups", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backups/backup_{timestamp}.zip"
            with zipfile.ZipFile(backup_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
                if os.path.exists("chat_history.db"):
                    zipf.write("chat_history.db")
                if os.path.exists("qdrant_db"):
                    for root, dirs, files in os.walk("qdrant_db"):
                        for file in files:
                            zipf.write(os.path.join(root, file))
            print(f"\n💾 [Backup] Automated daily backup created: {backup_name}\n")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("❌ [Backup Error] %s", e, exc_info=True)
            await asyncio.sleep(60)  # Prevent rapid failure loops from burning CPU
