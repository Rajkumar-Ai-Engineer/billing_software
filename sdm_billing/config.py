from pathlib import Path
import json
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent

# Load environment variables from .env.local first, then .env
for env_file in [ROOT_DIR / ".env.local", ROOT_DIR / ".env", BASE_DIR / ".env.local", BASE_DIR / ".env"]:
    if env_file.exists():
        load_dotenv(dotenv_path=env_file, override=False)

# Resilient static directory discovery across local and cloud environments (Manus, Vercel, Docker)
STATIC_DIR = BASE_DIR / "static"
for _candidate in [
    BASE_DIR / "static",
    BASE_DIR.parent / "public" / "static",
    BASE_DIR.parent / "static",
    BASE_DIR.parent / "public"
]:
    if _candidate.exists() and (_candidate / "css" / "style.css").exists():
        STATIC_DIR = _candidate
        break

TEMPLATES_DIR = BASE_DIR / "templates"

# In serverless environments (e.g. Vercel), local filesystem is read-only.
# We store mutable data and SQLite database in /tmp if DATABASE_URL is not set.
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
    "auth_enabled": True,  # Auth is required by default for security
    "auth_password": "sdm@admin123"
}

LABEL_PRESETS = {
    "50x30": {"width": 50, "height": 30},
    "38x25": {"width": 38, "height": 25},
    "50x25": {"width": 50, "height": 25},
    "100x50": {"width": 100, "height": 50}
}


def load_settings() -> dict:
    """
    Loads application settings, checking database app_settings first, then local settings.json.
    """
    settings = DEFAULT_SETTINGS.copy()
    try:
        from database import SessionLocal
        from models import AppSetting
        db = SessionLocal()
        try:
            db_setting = db.query(AppSetting).filter(AppSetting.id == "default").first()
            if db_setting:
                settings.update(db_setting.to_dict())
            elif SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    settings.update(saved)
        finally:
            db.close()
    except Exception:
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    settings.update(saved)
            except Exception:
                pass

    if "SDM_AUTH_ENABLED" in os.environ:
        settings["auth_enabled"] = os.environ["SDM_AUTH_ENABLED"].lower() in ("1", "true", "yes")
    if "SDM_AUTH_PASSWORD" in os.environ:
        settings["auth_password"] = os.environ["SDM_AUTH_PASSWORD"]
    return settings


def save_settings(new_settings: dict) -> dict:
    """
    Persists updated settings to both database app_settings and local settings.json.
    """
    current = load_settings()
    current.update(new_settings)
    
    # 1. Update database
    try:
        from database import SessionLocal
        from models import AppSetting
        db = SessionLocal()
        try:
            db_setting = db.query(AppSetting).filter(AppSetting.id == "default").first()
            if not db_setting:
                db_setting = AppSetting(id="default")
                db.add(db_setting)
            if "printer_name" in current: db_setting.printer_name = str(current["printer_name"])
            if "print_mode" in current: db_setting.print_mode = str(current["print_mode"])
            if "printer_language" in current: db_setting.printer_language = str(current["printer_language"])
            if "label_width_mm" in current: db_setting.label_width_mm = int(current["label_width_mm"])
            if "label_height_mm" in current: db_setting.label_height_mm = int(current["label_height_mm"])
            if "label_gap_mm" in current: db_setting.label_gap_mm = int(current["label_gap_mm"])
            if "dpi" in current: db_setting.dpi = int(current["dpi"])
            if "darkness" in current: db_setting.darkness = int(current["darkness"])
            if "speed" in current: db_setting.speed = int(current["speed"])
            if "margin_customer" in current: db_setting.margin_customer = float(current["margin_customer"])
            if "margin_dealer" in current: db_setting.margin_dealer = float(current["margin_dealer"])
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"[Settings] Warning saving to database: {e}")
        finally:
            db.close()
    except Exception as e:
        print(f"[Settings] DB session error: {e}")

    # 2. Update local file
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)
    except Exception as e:
        print(f"[Settings] Warning saving settings file: {e}")

    return current


# Authentication & Secrets
AUTH_ENABLED = True
AUTH_PASSWORD = os.getenv("SDM_AUTH_PASSWORD", "sdm@admin123")
SECRET_KEY = os.getenv("SDM_SECRET_KEY", "sdm-motors-secret-key-2026")
