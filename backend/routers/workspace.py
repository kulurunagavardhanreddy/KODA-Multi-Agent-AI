# backend/routers/workspace.py
import os
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from backend.core.security import get_current_user
from backend.database.chat_database import (
    get_user_workspaces, add_user_workspace, delete_user_workspace, activate_user_workspace
)
from backend.integrations.mcp import mcp_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["workspace"])

class WorkspacePath(BaseModel):
    path: str

@router.get("/workspaces")
def get_workspaces_endpoint(user = Depends(get_current_user)):
    return {"workspaces": get_user_workspaces(user["user_id"])}

@router.post("/workspaces")
def add_workspace_endpoint(data: WorkspacePath, user = Depends(get_current_user)):
    path = data.path.strip()
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="The specified path is not a valid directory or is unreachable.")
    add_user_workspace(user["user_id"], path)
    return {"message": "Workspace registered successfully"}

@router.delete("/workspaces")
def delete_workspace_endpoint(path: str, user = Depends(get_current_user)):
    delete_user_workspace(user["user_id"], path)
    return {"message": "Workspace deleted successfully"}

@router.post("/workspaces/activate")
async def activate_workspace_endpoint(data: WorkspacePath, user = Depends(get_current_user)):
    path = data.path.strip()
    if path != "uploads" and not os.path.isdir(path):
        raise HTTPException(status_code=400, detail="The specified path is not a valid directory or is unreachable.")
        
    activate_user_workspace(user["user_id"], path)
    
    # Restart the filesystem MCP server with the new path
    if path == "uploads":
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        target_path = os.path.join(root_dir, "uploads")
    else:
        target_path = path
        
    args = ["-y", "@modelcontextprotocol/server-filesystem", target_path]
    await mcp_manager.restart_server("filesystem", new_args=args)
    return {"message": f"Active workspace successfully switched to: {path}"}

@router.post("/utils/select-directory")
async def select_directory_endpoint(user = Depends(get_current_user)):
    """Pops up a native directory selection dialog using Tkinter (Local Host Mode fallback)."""
    import tkinter as tk
    from tkinter import filedialog
    
    def popup_dialog():
        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            folder_path = filedialog.askdirectory(title="Select Project Directory")
            root.destroy()
            return folder_path
        except Exception as te:
            logger.warning("[FastAPI Utils] Native directory selector popup failed: %s", te)
            return ""

    folder_path = await asyncio.to_thread(popup_dialog)
    if not folder_path:
        return {"path": "", "message": "Native folder selection was cancelled or is not supported in this headless environment."}
    return {"path": folder_path}
