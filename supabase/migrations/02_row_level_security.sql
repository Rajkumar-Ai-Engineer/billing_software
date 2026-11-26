-- =============================================================================
-- SRI DHANAM MOTORS - Row Level Security (RLS) Policies
-- Migration: 02_row_level_security.sql
-- Description: Enforces table-level security ensuring only authenticated
--              Supabase users can read, insert, update, and delete records.
--              Service role key retains administrative access for background tasks.
-- =============================================================================

-- Enable Row Level Security on all tables
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.batteries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.stock_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.label_print_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.workers ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.salary_advances ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.purchase_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.app_settings ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if any
DO $$
DECLARE
    t text;
BEGIN
    FOR t IN 
        SELECT tablename FROM pg_tables WHERE schemaname = 'public' 
        AND tablename IN ('products', 'invoices', 'invoice_items', 'batteries', 
                          'stock_movements', 'label_print_logs', 'workers', 
                          'attendance', 'salary_advances', 'daily_expenses', 
                          'purchase_invoices', 'app_settings')
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS "auth_full_access" ON public.%I', t);
        EXECUTE format('DROP POLICY IF EXISTS "authenticated_select_policy" ON public.%I', t);
        EXECUTE format('DROP POLICY IF EXISTS "authenticated_insert_policy" ON public.%I', t);
        EXECUTE format('DROP POLICY IF EXISTS "authenticated_update_policy" ON public.%I', t);
        EXECUTE format('DROP POLICY IF EXISTS "authenticated_delete_policy" ON public.%I', t);
    END LOOP;
END $$;

-- -----------------------------------------------------------------------------
-- Create comprehensive authenticated access policies for each table
-- -----------------------------------------------------------------------------
-- 1. products
CREATE POLICY "auth_products_policy" ON public.products
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- 2. invoices
CREATE POLICY "auth_invoices_policy" ON public.invoices
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- 3. invoice_items
CREATE POLICY "auth_invoice_items_policy" ON public.invoice_items
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- 4. batteries
CREATE POLICY "auth_batteries_policy" ON public.batteries
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- 5. stock_movements
CREATE POLICY "auth_stock_movements_policy" ON public.stock_movements
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- 6. label_print_logs
CREATE POLICY "auth_label_logs_policy" ON public.label_print_logs
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- 7. workers
CREATE POLICY "auth_workers_policy" ON public.workers
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- 8. attendance
CREATE POLICY "auth_attendance_policy" ON public.attendance
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- 9. salary_advances
CREATE POLICY "auth_salary_advances_policy" ON public.salary_advances
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- 10. daily_expenses
CREATE POLICY "auth_daily_expenses_policy" ON public.daily_expenses
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- 11. purchase_invoices
CREATE POLICY "auth_purchase_invoices_policy" ON public.purchase_invoices
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');

-- 12. app_settings
CREATE POLICY "auth_app_settings_policy" ON public.app_settings
    FOR ALL
    TO authenticated
    USING (auth.role() = 'authenticated')
    WITH CHECK (auth.role() = 'authenticated');
