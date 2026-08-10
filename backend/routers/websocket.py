# backend/routers/websocket.py
import jwt
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from backend.core.config import SECRET_KEY, ALGORITHM
from backend.websocket.manager import ws_manager, get_needs_response_count

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["websocket"])

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    user_id = None
    try:
        while True:
            data = await websocket.receive_text()
            try:
                import json
                event_data = json.loads(data)
                if event_data.get("action") == "auth":
                    auth_token = event_data.get("token")
                    decoded = jwt.decode(auth_token, SECRET_KEY, algorithms=[ALGORITHM])
                    user_id = decoded.get("sub")
                    
                    if user_id:
                        await ws_manager.connect(websocket, user_id)
                        # Immediately send the current unread/needs response count
                        count = get_needs_response_count(user_id)
                        await websocket.send_json({"event": "unread_count", "count": count})
            except Exception as e:
                logger.warning(f"⚠️ [WS Message Process Error] {e}")
    except WebSocketDisconnect:
        if user_id:
            ws_manager.disconnect(websocket, user_id)
    except Exception as ex:
        logger.warning(f"⚠️ [WS Connection Error] {ex}")
        if user_id:
            ws_manager.disconnect(websocket, user_id)
