import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base, sessionmaker

# Ensure environment variables are loaded and paths are in sys.path
SDM_DIR = Path(__file__).resolve().parent
ROOT_DIR = SDM_DIR.parent
for p in (str(SDM_DIR), str(ROOT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

for env_path in [ROOT_DIR / ".env.local", ROOT_DIR / ".env", SDM_DIR / ".env.local", SDM_DIR / ".env"]:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)

try:
    from config import DB_PATH, IS_VERCEL
except ImportError:
    from sdm_billing.config import DB_PATH, IS_VERCEL

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL") or os.getenv("POSTGRES_URL")
if os.getenv("TESTING") == "1":
    DATABASE_URL = None

engine = None
is_placeholder = False
db_connection_error = None

if DATABASE_URL:
    is_placeholder = any(p in DATABASE_URL.lower() for p in ["your_", "your-", "[your", "example.com", "your-project"])

if DATABASE_URL and not is_placeholder:
    url_normalized = DATABASE_URL.strip()
    if url_normalized.startswith("postgres://"):
        url_normalized = url_normalized.replace("postgres://", "postgresql://", 1)

    engine_options = {
        "pool_pre_ping": True,
        "connect_args": {"connect_timeout": 30, "sslmode": "require"},
    }
    if IS_VERCEL:
        engine_options["poolclass"] = NullPool
    else:
        engine_options.update(pool_recycle=300, pool_size=5, max_overflow=10)

    candidates = [url_normalized]
    if "postgresql+psycopg://" in url_normalized:
        candidates.append(url_normalized.replace("postgresql+psycopg://", "postgresql+psycopg2://", 1))
        candidates.append(url_normalized.replace("postgresql+psycopg://", "postgresql://", 1))
    elif "postgresql+psycopg2://" in url_normalized:
        candidates.append(url_normalized.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1))
        candidates.append(url_normalized.replace("postgresql+psycopg2://", "postgresql://", 1))
    elif "postgresql://" in url_normalized and "+psycopg" not in url_normalized:
        candidates.append(url_normalized.replace("postgresql://", "postgresql+psycopg2://", 1))
        candidates.append(url_normalized.replace("postgresql://", "postgresql+psycopg://", 1))

    for candidate_url in candidates:
        try:
            eng = create_engine(candidate_url, **engine_options)
            with eng.connect() as test_conn:
                pass
            engine = eng
            print("[Database] Connected successfully to Supabase PostgreSQL database.")
            db_connection_error = None
            break
        except Exception as e:
            db_connection_error = str(e)
            engine = None

    if engine is None and db_connection_error:
        print(f"[Database] Warning connecting to PostgreSQL ({db_connection_error}). Falling back to local SQLite.")

if engine is None:
    if not DATABASE_URL or is_placeholder:
        db_connection_error = "DATABASE_URL is not configured in environment variables. Falling back to temporary SQLite."
        print("[Database] NOTICE: DATABASE_URL missing or placeholder. Add DATABASE_URL to Vercel Environment Variables to connect Supabase PostgreSQL.")
    else:
        print(f"[Database] Could not connect to PostgreSQL ({db_connection_error}). Using SQLite fallback.")

    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    print(f"[Database] Using local SQLite database at {DB_PATH}")


def is_postgres_connected() -> bool:
    return engine is not None and getattr(engine.dialect, "name", "") == "postgresql"


def get_db_status() -> dict:
    return {
        "is_postgres": is_postgres_connected(),
        "database_type": "Supabase PostgreSQL" if is_postgres_connected() else "Local SQLite Fallback",
        "has_database_url": bool(DATABASE_URL and not is_placeholder),
        "error": db_connection_error if not is_postgres_connected() else None
    }

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import models  # Ensure all models are registered

    if not engine:
        return

    if IS_VERCEL:
        if is_postgres_connected():
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                print("[Database] Verified Supabase PostgreSQL connectivity; runtime DDL skipped.")
            except Exception as e:
                print(f"[Database] PostgreSQL connectivity warning on Vercel: {e}")
            return
        # SQLite fallback mode on Vercel: ensure tables exist in /tmp
        try:
            Base.metadata.create_all(bind=engine)
            print("[Database] Initialized SQLite fallback schema on Vercel.")
        except Exception as e:
            print(f"[Database] SQLite schema initialization warning on Vercel: {e}")
        return

    Base.metadata.create_all(bind=engine)
    
    # Ensure all tables have updated_at column across both PostgreSQL and SQLite
    if engine:
        try:
            from sqlalchemy import text
            dialect_name = getattr(engine.dialect, "name", "")
            tables_to_ensure = [
                "products", "invoices", "batteries", "workers", "attendance",
                "daily_expenses", "purchase_invoices", "salary_advances",
                "invoice_items", "stock_movements", "label_print_logs", "app_settings"
            ]
            with engine.connect() as conn:
                if dialect_name == "postgresql":
                    for tbl in tables_to_ensure:
                        conn.execute(text(f"ALTER TABLE public.{tbl} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();"))
                    conn.execute(text("""
                        CREATE OR REPLACE FUNCTION update_updated_at_column()
                        RETURNS TRIGGER AS $$
                        BEGIN
                            BEGIN
                                NEW.updated_at = NOW();
                            EXCEPTION WHEN undefined_column THEN
                                NULL;
                            END;
                            RETURN NEW;
                        END;
                        $$ LANGUAGE plpgsql;
                    """))
                    conn.commit()
                elif dialect_name == "sqlite":
                    for tbl in tables_to_ensure:
                        try:
                            conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN updated_at DATETIME;"))
                            conn.commit()
                        except Exception:
                            pass
        except Exception as e:
            print(f"[Database] Warning ensuring updated_at columns: {e}")

    # Initialize default app settings if table is empty
    db = SessionLocal()
    try:
        existing_setting = db.query(models.AppSetting).filter(models.AppSetting.id == "default").first()
        if not existing_setting:
            import config
            defaults = config.DEFAULT_SETTINGS
            new_setting = models.AppSetting(
                id="default",
                printer_name=defaults.get("printer_name", "TVS LP 46"),
                print_mode=defaults.get("print_mode", "driver_html"),
                printer_language=defaults.get("printer_language", "EPL"),
                label_width_mm=defaults.get("label_width_mm", 50),
                label_height_mm=defaults.get("label_height_mm", 30),
                label_gap_mm=defaults.get("label_gap_mm", 3),
                dpi=defaults.get("dpi", 203),
                darkness=defaults.get("darkness", 8),
                speed=defaults.get("speed", 4),
                margin_customer=defaults.get("margin_customer", 0.80),
                margin_dealer=defaults.get("margin_dealer", 0.40)
            )
            db.add(new_setting)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"[Database] Warning initializing app settings: {e}")
    finally:
        db.close()
