# backend/routers/web.py
import os
from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["web"])

# Determine paths
root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
frontend_path = os.path.join(root_dir, "frontend")
templates_path = os.path.join(frontend_path, "templates")

@router.get("/")
def serve_index():
    return FileResponse(os.path.join(templates_path, "index.html"))

@router.get("/login.html")
@router.get("/login")
def serve_login():
    return FileResponse(os.path.join(templates_path, "login.html"))

@router.get("/gold_calculator.html")
@router.get("/gold_calculator")
def serve_gold_calculator():
    return FileResponse(os.path.join(templates_path, "gold_calculator.html"))

@router.get("/js/ui/export_chat.js")
@router.get("/js/export_chat.js")
def serve_legacy_export_chat():
    return FileResponse(os.path.join(frontend_path, "js", "chat", "export_chat.js"), media_type="application/javascript")

@router.get("/{page_name}")
def serve_dynamic_template(page_name: str):
    safe_name = os.path.basename(page_name)
    if not safe_name.endswith(".html"):
        safe_name = f"{safe_name}.html"
    
    target_file = os.path.join(templates_path, safe_name)
    if os.path.exists(target_file) and os.path.isfile(target_file):
        return FileResponse(target_file)
    
    return FileResponse(os.path.join(templates_path, "index.html"))
