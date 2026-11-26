-- =============================================================================
-- SRI DHANAM MOTORS - Rollback Strategy Script
-- Migration: 05_rollback.sql
-- Description: Safely drops migrated tables and policies if rolling back.
-- CAUTION: This will drop all migrated Supabase tables.
-- =============================================================================

DROP TABLE IF EXISTS public.invoice_items CASCADE;
DROP TABLE IF EXISTS public.invoices CASCADE;
DROP TABLE IF EXISTS public.products CASCADE;
DROP TABLE IF EXISTS public.batteries CASCADE;
DROP TABLE IF EXISTS public.stock_movements CASCADE;
DROP TABLE IF EXISTS public.label_print_logs CASCADE;
DROP TABLE IF EXISTS public.attendance CASCADE;
DROP TABLE IF EXISTS public.salary_advances CASCADE;
DROP TABLE IF EXISTS public.workers CASCADE;
DROP TABLE IF EXISTS public.daily_expenses CASCADE;
DROP TABLE IF EXISTS public.purchase_invoices CASCADE;
DROP TABLE IF EXISTS public.app_settings CASCADE;

DROP FUNCTION IF EXISTS update_updated_at_column CASCADE;
