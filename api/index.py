import sys
import os
import mimetypes
from pathlib import Path

# Register standard MIME types to guarantee proper headers in serverless runtimes
mimetypes.init()
mimetypes.add_type("text/css", ".css", strict=True)
mimetypes.add_type("application/javascript", ".js", strict=True)
mimetypes.add_type("image/png", ".png", strict=True)
mimetypes.add_type("image/jpeg", ".jpg", strict=True)
mimetypes.add_type("image/svg+xml", ".svg", strict=True)

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
        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers", [])
        }
        path = scope.get("path", "")

        # Depending on whether the request arrived through a Vercel rewrite or
        # directly through the Python function, the runtime may expose either
        # the internal function path or the original public URI.
        for header_name in (
            "x-forwarded-uri",
            "x-vercel-original-url",
            "x-original-url",
            "x-invoke-path",
        ):
            forwarded_path = headers.get(header_name, "").split("?", 1)[0]
            if forwarded_path and not forwarded_path.startswith("/api/index"):
                path = forwarded_path
                break

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
