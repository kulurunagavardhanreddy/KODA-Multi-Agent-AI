# backend/routers/upload.py
import os
import uuid
import shutil
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from backend.core.security import get_current_user
from backend.loaders.document_loader import process_and_store_document

logger = logging.getLogger(__name__)
router = APIRouter(tags=["upload"])

@router.post("/upload-pdf")
@router.post("/upload")
def upload_document(
    file: UploadFile = File(...), 
    session_id: str = Form(""), 
    background_tasks: BackgroundTasks = BackgroundTasks(), 
    current_user: dict = Depends(get_current_user)
):
    """Uploads a PDF or TXT file, splits it, and stores it in Qdrant Vector DB."""
    ALLOWED_EXTENSIONS = {".pdf", ".txt", ".docx", ".csv", ".xls", ".xlsx", ".jpg", ".jpeg", ".png", ".bmp"}
    
    filename = file.filename or "unknown_file"
    ext = os.path.splitext(filename)[1].lower()
    
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning("Rejected file upload: %s (Extension: %s)", filename, ext)
        raise HTTPException(status_code=400, detail=f"Unsupported file type: '{ext}'. Supported formats: PDF, CSV, TXT, DOCX, Images.")
        
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)
    if file_size > 15 * 1024 * 1024:  # 15 MB limit
        logger.warning("Rejected file upload: %s (Size: %s bytes exceeds 15MB)", filename, file_size)
        raise HTTPException(status_code=400, detail="File size exceeds the 15MB limit.")

    os.makedirs("temp_docs", exist_ok=True)
    temp_path = f"temp_docs/{file.filename}"
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    def process_file_bg(path: str, uid: str, sid: str):
        try:
            process_and_store_document(path, uid, sid)
        except Exception as e:
            print(f"❌ [Background Task Error] Failed to process {path}: {e}")
        finally:
            if os.path.exists(path):
                os.remove(path)

    background_tasks.add_task(process_file_bg, temp_path, current_user["user_id"], session_id)
    return {"message": f"Uploading and processing {file.filename} in the background...", "filename": file.filename, "status": "Processing in background"}

@router.post("/api/upload-image")
def upload_image_endpoint(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """Handles local image uploads to avoid massive Base64 strings in the browser."""
    if current_user.get("is_guest"):
        raise HTTPException(status_code=403, detail="Guests cannot upload images.")
        
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    if size > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image size exceeds 10MB limit.")
        
    os.makedirs("uploads/images", exist_ok=True)
    ext = os.path.splitext(file.filename)[1].lower()
    safe_filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join("uploads/images", safe_filename)
    
    with open(filepath, "wb") as f:
        shutil.copyfileobj(file.file, f)
        
    return {"url": f"/uploads/images/{safe_filename}", "filename": file.filename}
