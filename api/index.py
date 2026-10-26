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
