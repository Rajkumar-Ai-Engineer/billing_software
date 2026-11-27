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

from sdm_billing.main import app
