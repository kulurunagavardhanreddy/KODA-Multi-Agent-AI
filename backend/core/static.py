# backend/core/static.py
import os
from fastapi.staticfiles import StaticFiles

class NoCacheStaticFiles(StaticFiles):
    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

def setup_static(app):
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    frontend_path = os.path.join(root_dir, "frontend")
    
    os.makedirs("uploads/images", exist_ok=True)
    app.mount("/uploads", NoCacheStaticFiles(directory="uploads"), name="uploads")
    app.mount("/", NoCacheStaticFiles(directory=frontend_path), name="static")
