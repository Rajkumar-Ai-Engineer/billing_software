from pathlib import Path
import json
import os

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# In serverless environments (e.g. Vercel), local filesystem is read-only.
# We store mutable data and SQLite database in /tmp.
IS_VERCEL = bool(os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

if IS_VERCEL:
    DATA_DIR = Path("/tmp/sdm_data")
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    DB_PATH = DATA_DIR / "sdm.db"

    # Seed initial data from repository bundle if not present
    SRC_DATA_DIR = BASE_DIR / "data"
    if SRC_DATA_DIR.exists():
        import shutil
        for item in SRC_DATA_DIR.iterdir():
            target_item = DATA_DIR / item.name
            if not target_item.exists():
                try:
                    if item.is_file():
                        shutil.copy2(item, target_item)
                    elif item.is_dir():
                        shutil.copytree(item, target_item)
                except Exception as e:
                    print(f"Warning: could not seed {item.name}: {e}")
else:
    DATA_DIR = BASE_DIR / "data"
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    DB_PATH = DATA_DIR / "sdm.db"

# Shop Details
SHOP_NAME = "SRI DHANAM MOTORS"
SHOP_TAGLINE = "⚡ SALES, SERVICES & SPARES"
VEHICLE_SUBTITLE = "AUTHORIZED JHEV MOTORS DEALER"
SHOP_ADDRESS = "Near RTO Office Mobirippatti, Harur (Tk), Dharmapuri (Dt) - 636903"
SHOP_PHONES = "+91 9344885449, +91 8428544972"
SHOP_GSTIN = "Applied (A/F)"
WEBSITE_URL = "https://www.sridhanammotors.com"

# Brand Colors
COLOR_GREEN = "#2E7D32"
COLOR_NAVY = "#1A365D"
COLOR_BLUE = "#2B6CB0"

# Margins
MARGIN_CUSTOMER = 0.80  # 80%
MARGIN_DEALER = 0.40    # 40%

# Invoice Prefixes
PREFIX_INVOICE = "SDM"
PREFIX_SPARE = "SDM"
PREFIX_SERVICE = "SDM"
PREFIX_VEHICLE = "SDM"

# Printer & Label Defaults
SETTINGS_FILE = DATA_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "printer_name": "TVS LP 46",
    "print_mode": "driver_html",  # "driver_html" or "raw"
    "printer_language": "TSPL",    # "TSPL", "ZPL", "EPL"
    "label_width_mm": 50,
    "label_height_mm": 30,
    "label_gap_mm": 3,
    "dpi": 203,
    "darkness": 8,
    "speed": 4,
    "margin_customer": 0.80,
    "margin_dealer": 0.40,
    "auth_enabled": False,
    "auth_password": "sdm@admin123"
}

LABEL_PRESETS = {
    "50x30": {"width": 50, "height": 30},
    "38x25": {"width": 38, "height": 25},
    "50x25": {"width": 50, "height": 25},
    "100x50": {"width": 100, "height": 50}
}


def load_settings() -> dict:
    settings = DEFAULT_SETTINGS.copy()
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception:
            pass
    # Allow environment variable override for auth
    if "SDM_AUTH_ENABLED" in os.environ:
        settings["auth_enabled"] = os.environ["SDM_AUTH_ENABLED"].lower() in ("1", "true", "yes")
    if "SDM_AUTH_PASSWORD" in os.environ:
        settings["auth_password"] = os.environ["SDM_AUTH_PASSWORD"]
    return settings


def save_settings(new_settings: dict) -> dict:
    current = load_settings()
    current.update(new_settings)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return current


# Authentication
AUTH_ENABLED = os.getenv("SDM_AUTH_ENABLED", "false").lower() in ("1", "true", "yes")
AUTH_PASSWORD = os.getenv("SDM_AUTH_PASSWORD", "sdm@admin123")
SECRET_KEY = os.getenv("SDM_SECRET_KEY", "sdm-motors-secret-key-2026")
