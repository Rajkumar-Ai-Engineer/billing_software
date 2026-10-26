import sys
import os
from pathlib import Path

# Add project root and sdm_billing to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
SDM_DIR = ROOT_DIR / "sdm_billing"

for p in (str(ROOT_DIR), str(SDM_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    os.chdir(str(SDM_DIR))
except Exception:
    pass

from sdm_billing.main import app


# Vercel may pass the function filename as a prefix in the ASGI request path.
# Strip only that internal prefix so FastAPI receives the public application path.
_fastapi_app = app


async def app_handler(scope, receive, send):
    if scope.get("type") == "http":
        path = scope.get("path", "")
        for prefix in ("/api/index.py", "/api/index"):
            if path == prefix or path.startswith(prefix + "/"):
                scope = dict(scope)
                adjusted_path = path[len(prefix):] or "/"
                scope["path"] = adjusted_path
                if scope.get("raw_path"):
                    scope["raw_path"] = adjusted_path.encode("utf-8")
                break
    await _fastapi_app(scope, receive, send)


app = app_handler
