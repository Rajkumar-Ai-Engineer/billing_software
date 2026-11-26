import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
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
if DATABASE_URL:
    is_placeholder = any(p in DATABASE_URL.lower() for p in ["your_", "your-", "[your", "example.com", "your-project"])

if DATABASE_URL and not is_placeholder:
    try:
        url_normalized = DATABASE_URL
        if url_normalized.startswith("postgres://"):
            url_normalized = url_normalized.replace("postgres://", "postgresql+psycopg2://", 1)
        elif url_normalized.startswith("postgresql://"):
            # SQLAlchemy 2.x defaults postgresql:// to psycopg (v3), while
            # this deployment installs psycopg2-binary.
            url_normalized = url_normalized.replace("postgresql://", "postgresql+psycopg2://", 1)
        engine = create_engine(
            url_normalized,
            pool_pre_ping=True,
            pool_recycle=300,
            pool_size=5,
            max_overflow=10,
            connect_args={"connect_timeout": 30, "sslmode": "require"}
        )
        # Test connection
        with engine.connect() as test_conn:
            pass
        print("[Database] Connected successfully to Supabase PostgreSQL database.")
    except Exception as e:
        if IS_VERCEL and os.getenv("ALLOW_SQLITE_FALLBACK", "false").lower() not in ("1", "true", "yes"):
            raise RuntimeError(
                "Production database connection failed; refusing to use ephemeral SQLite on Vercel. "
                "Verify DATABASE_URL is a valid Supabase PostgreSQL URL and that its password is URL-encoded."
            ) from e
        print(f"[Database] Warning connecting to PostgreSQL ({e}). Falling back to local SQLite.")
        engine = None

if engine is None:
    if IS_VERCEL and os.getenv("ALLOW_SQLITE_FALLBACK", "false").lower() not in ("1", "true", "yes"):
        raise RuntimeError(
            "DATABASE_URL is missing in Vercel production; refusing to use ephemeral SQLite. "
            "Configure the Supabase PostgreSQL connection string before serving the application."
        )
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
    print(f"[Database] Using local SQLite database at {DB_PATH}")

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
