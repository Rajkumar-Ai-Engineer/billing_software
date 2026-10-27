"""
Sri Dhanam Motors - Root Application Entrypoint
Configured for production & cloud deployments (Manus, Docker, Vercel, Render, Railway).
"""
import os
import sys
import mimetypes
from pathlib import Path

# Ensure MIME types are registered before anything loads
mimetypes.init()
mimetypes.add_type("text/css", ".css", strict=True)
mimetypes.add_type("application/javascript", ".js", strict=True)
mimetypes.add_type("image/png", ".png", strict=True)
mimetypes.add_type("image/jpeg", ".jpg", strict=True)
mimetypes.add_type("image/svg+xml", ".svg", strict=True)

ROOT_DIR = Path(__file__).resolve().parent
SDM_DIR = ROOT_DIR / "sdm_billing"

for p in (str(ROOT_DIR), str(SDM_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sdm_billing.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=False)
