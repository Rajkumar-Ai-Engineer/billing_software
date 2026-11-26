-- =============================================================================
-- SRI DHANAM MOTORS - Supabase PostgreSQL Schema Migration
-- Migration: 01_initial_schema.sql
-- Description: Full schema definition for products, invoices, line items,
--              batteries, stock movements, logs, workers, attendance,
--              expenses, purchases, and application settings.
-- =============================================================================

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Trigger function for updating updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- 1. Table: products (Inventory & Spares Catalog)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.products (
    id BIGSERIAL PRIMARY KEY,
    part_no VARCHAR(100) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    hsn VARCHAR(50),
    cost_price NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    gst_percent NUMERIC(5, 2) NOT NULL DEFAULT 18.00,
    category VARCHAR(50) NOT NULL,
    vehicle_type VARCHAR(50),
    stock_qty INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_products_part_no ON public.products(part_no);
CREATE INDEX IF NOT EXISTS idx_products_category ON public.products(category);
CREATE INDEX IF NOT EXISTS idx_products_name ON public.products(name);

DROP TRIGGER IF EXISTS trg_products_updated_at ON public.products;
CREATE TRIGGER trg_products_updated_at
BEFORE UPDATE ON public.products
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 2. Table: invoices (Sales & Billing Records)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.invoices (
    id BIGSERIAL PRIMARY KEY,
    invoice_no VARCHAR(100) UNIQUE NOT NULL,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    time VARCHAR(20) NOT NULL DEFAULT '',
    category VARCHAR(50) NOT NULL,
    buyer_type VARCHAR(50) NOT NULL DEFAULT 'Customer',
    gst_mode VARCHAR(50) NOT NULL DEFAULT 'With GST (Tax Invoice)',
    customer_name VARCHAR(255) NOT NULL DEFAULT '',
    mobile VARCHAR(20) NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    gstin VARCHAR(50),
    base_total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    gst_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    grand_total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    is_legacy BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoices_invoice_no ON public.invoices(invoice_no);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON public.invoices(date);
CREATE INDEX IF NOT EXISTS idx_invoices_category ON public.invoices(category);
CREATE INDEX IF NOT EXISTS idx_invoices_mobile ON public.invoices(mobile);

DROP TRIGGER IF EXISTS trg_invoices_updated_at ON public.invoices;
CREATE TRIGGER trg_invoices_updated_at
BEFORE UPDATE ON public.invoices
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 3. Table: invoice_items (Line Items for Invoices)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.invoice_items (
    id BIGSERIAL PRIMARY KEY,
    invoice_id BIGINT NOT NULL REFERENCES public.invoices(id) ON DELETE CASCADE,
    part_no VARCHAR(100) NOT NULL,
    product_name VARCHAR(255) NOT NULL,
    price NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    qty INTEGER NOT NULL DEFAULT 1,
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    gst_percent NUMERIC(5, 2) NOT NULL DEFAULT 18.00,
    gst_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice_id ON public.invoice_items(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_items_part_no ON public.invoice_items(part_no);

-- -----------------------------------------------------------------------------
-- 4. Table: batteries (Battery Serial & Specification Tracking)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.batteries (
    id BIGSERIAL PRIMARY KEY,
    serial VARCHAR(100) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL,
    voltage NUMERIC(8, 2) NOT NULL,
    ah NUMERIC(8, 2) NOT NULL,
    sold BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_batteries_serial ON public.batteries(serial);
CREATE INDEX IF NOT EXISTS idx_batteries_sold ON public.batteries(sold);

DROP TRIGGER IF EXISTS trg_batteries_updated_at ON public.batteries;
CREATE TRIGGER trg_batteries_updated_at
BEFORE UPDATE ON public.batteries
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 5. Table: stock_movements (Inventory Audit Trail)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.stock_movements (
    id BIGSERIAL PRIMARY KEY,
    part_no VARCHAR(100) NOT NULL,
    change INTEGER NOT NULL,
    reason VARCHAR(255) NOT NULL,
    ref VARCHAR(100),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stock_movements_part_no ON public.stock_movements(part_no);
CREATE INDEX IF NOT EXISTS idx_stock_movements_timestamp ON public.stock_movements(timestamp);

-- -----------------------------------------------------------------------------
-- 6. Table: label_print_logs (TVS LP 46 Print History)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.label_print_logs (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    label_type VARCHAR(50) NOT NULL,
    reference VARCHAR(100) NOT NULL,
    copies INTEGER NOT NULL DEFAULT 1,
    mode VARCHAR(50) NOT NULL DEFAULT 'driver_html',
    success BOOLEAN NOT NULL DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_label_logs_timestamp ON public.label_print_logs(timestamp);

-- -----------------------------------------------------------------------------
-- 7. Table: workers (Staff / Mechanic Roster)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.workers (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NOT NULL DEFAULT '',
    role VARCHAR(100) NOT NULL DEFAULT 'Technician',
    monthly_salary NUMERIC(12, 2) NOT NULL DEFAULT 15000.00,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_workers_active ON public.workers(active);
CREATE INDEX IF NOT EXISTS idx_workers_phone ON public.workers(phone);

DROP TRIGGER IF EXISTS trg_workers_updated_at ON public.workers;
CREATE TRIGGER trg_workers_updated_at
BEFORE UPDATE ON public.workers
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 8. Table: attendance (Daily Worker Attendance)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.attendance (
    id BIGSERIAL PRIMARY KEY,
    worker_id BIGINT NOT NULL REFERENCES public.workers(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    day_name VARCHAR(20) NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'P',
    notes VARCHAR(255) DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_worker_attendance_date UNIQUE(worker_id, date)
);

CREATE INDEX IF NOT EXISTS idx_attendance_worker_date ON public.attendance(worker_id, date);
CREATE INDEX IF NOT EXISTS idx_attendance_date ON public.attendance(date);

DROP TRIGGER IF EXISTS trg_attendance_updated_at ON public.attendance;
CREATE TRIGGER trg_attendance_updated_at
BEFORE UPDATE ON public.attendance
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 9. Table: salary_advances (Worker Advances)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.salary_advances (
    id BIGSERIAL PRIMARY KEY,
    worker_id BIGINT NOT NULL REFERENCES public.workers(id) ON DELETE CASCADE,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    notes VARCHAR(255) DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_salary_advances_worker ON public.salary_advances(worker_id);
CREATE INDEX IF NOT EXISTS idx_salary_advances_date ON public.salary_advances(date);

-- -----------------------------------------------------------------------------
-- 10. Table: daily_expenses (Daily Operating Expenses)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.daily_expenses (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL DEFAULT CURRENT_DATE,
    bill_no VARCHAR(100) DEFAULT '',
    product_name VARCHAR(255) DEFAULT '',
    price NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_expenses_date ON public.daily_expenses(date);

DROP TRIGGER IF EXISTS trg_daily_expenses_updated_at ON public.daily_expenses;
CREATE TRIGGER trg_daily_expenses_updated_at
BEFORE UPDATE ON public.daily_expenses
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 11. Table: purchase_invoices (Inward Supplier Purchases)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.purchase_invoices (
    id BIGSERIAL PRIMARY KEY,
    invoice_no VARCHAR(100) NOT NULL,
    received_date DATE NOT NULL DEFAULT CURRENT_DATE,
    price NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total_qty INTEGER NOT NULL DEFAULT 0,
    notes TEXT DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_purchase_invoices_no ON public.purchase_invoices(invoice_no);
CREATE INDEX IF NOT EXISTS idx_purchase_invoices_date ON public.purchase_invoices(received_date);

DROP TRIGGER IF EXISTS trg_purchase_invoices_updated_at ON public.purchase_invoices;
CREATE TRIGGER trg_purchase_invoices_updated_at
BEFORE UPDATE ON public.purchase_invoices
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- -----------------------------------------------------------------------------
-- 12. Table: app_settings (System & Hardware Preferences)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.app_settings (
    id VARCHAR(50) PRIMARY KEY DEFAULT 'default',
    printer_name VARCHAR(100) NOT NULL DEFAULT 'TVS LP 46',
    print_mode VARCHAR(50) NOT NULL DEFAULT 'driver_html',
    printer_language VARCHAR(50) NOT NULL DEFAULT 'EPL',
    label_width_mm INTEGER NOT NULL DEFAULT 50,
    label_height_mm INTEGER NOT NULL DEFAULT 30,
    label_gap_mm INTEGER NOT NULL DEFAULT 3,
    dpi INTEGER NOT NULL DEFAULT 203,
    darkness INTEGER NOT NULL DEFAULT 8,
    speed INTEGER NOT NULL DEFAULT 4,
    margin_customer NUMERIC(5, 2) NOT NULL DEFAULT 0.80,
    margin_dealer NUMERIC(5, 2) NOT NULL DEFAULT 0.40,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

DROP TRIGGER IF EXISTS trg_app_settings_updated_at ON public.app_settings;
CREATE TRIGGER trg_app_settings_updated_at
BEFORE UPDATE ON public.app_settings
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
