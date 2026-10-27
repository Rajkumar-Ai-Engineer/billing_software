"""
Application entrypoint for deployment environments that look for app.py (e.g. uvicorn app:app).
Re-exports the production FastAPI ASGI application from main.py.
For the legacy Streamlit prototype, see app_streamlit.py.
"""
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
SDM_DIR = ROOT_DIR / "sdm_billing"

for p in (str(ROOT_DIR), str(SDM_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("app:app", host=host, port=port, reload=False)
