import sys
import os
import traceback

root_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(root_dir, 'backend')

if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
# Define 'app' for Vercel AST 
app = None

try:
    from backend.main import app as main_app
    app = main_app
except Exception as e:
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()
    error_detail = traceback.format_exc()
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    def catch_all(path: str):
        return JSONResponse(status_code=500, content={"error": "Vercel Init Error", "traceback": error_detail})
