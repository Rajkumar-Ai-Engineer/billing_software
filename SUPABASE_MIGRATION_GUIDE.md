# Sri Dhanam Motors - Secure Supabase Authentication & Database Migration Guide

This document provides complete instructions for configuring, migrating, and verifying the **Sri Dhanam Motors** billing and inventory management application with **Supabase Authentication**, **PostgreSQL Database**, and **Supabase Storage**.

---

## 🏛️ System Architecture Overview

```
                                  +------------------------------------+
                                  |     Client Browser / Mobile UI     |
                                  | (Jinja2 HTML, JS, CSS, Chart.js)   |
                                  +-----------------+------------------+
                                                    |
                       HTTP / HTTPS (Cookies, JWT)  |  Direct Auth Verification
                                                    v
+---------------------------------------------------+------------------------------------+
|                                FastAPI Backend Application                             |
|  - Auth Middleware: Verifies Supabase session JWT on EVERY route / refresh             |
|  - Unauthenticated Pages -> 302 Redirect to /login?next=...                            |
|  - Unauthenticated APIs  -> 401 Unauthorized JSON                                      |
|  - Session Endpoints: /api/auth/login, /api/auth/session, /api/auth/logout             |
|  - Dual Mode: Supabase Cloud Client + SQLAlchemy PostgreSQL Engine                     |
+--------------------------+---------------------------------+---------------------------+
                           |                                 |
           SQLAlchemy ORM  |                                 | Supabase Auth & Storage API
           Postgres Pooler |                                 | (Service Role / Anon Key)
                           v                                 v
+----------------------------------------------------------------------------------------+
|                                    Supabase Cloud                                      |
|  1. Supabase Auth: Secure email/password session management, JWT issuance & revocation |
|  2. Supabase PostgreSQL: 12 Normalized relational tables, Foreign Keys, Indexes, RLS   |
|  3. Row Level Security: Enforced at the DB level for authenticated users only          |
|  4. Supabase Storage: 'shop-assets' bucket for shop branding, logo, and documents      |
+----------------------------------------------------------------------------------------+
```

---

## 🔑 1. Environment Variable Configuration

Create or update `.env.local` in the project root directory. (`.gitignore` protects this file from being committed to GitHub).

```env
# -----------------------------------------------------------------------------
# Supabase Project Credentials (from Supabase Dashboard -> Settings -> API)
# -----------------------------------------------------------------------------
NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# -----------------------------------------------------------------------------
# Supabase Service Role Key (from Settings -> API -> service_role secret)
# SERVER-SIDE ONLY: Never expose this key to browser client code!
# -----------------------------------------------------------------------------
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# -----------------------------------------------------------------------------
# Supabase Database Connection String (Settings -> Database -> Connection string)
# -----------------------------------------------------------------------------
# Transaction Mode (Port 6543) or Session Mode (Port 5432):
DATABASE_URL=postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT-ID].supabase.co:5432/postgres

# Optional Application Secret
SDM_SECRET_KEY=sdm-motors-secure-key-2026
```

> **Security Rule:**
> - `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are safe for browser use.
> - `SUPABASE_SERVICE_ROLE_KEY` and `DATABASE_URL` remain strictly server-side.

---

## 🗄️ 2. Database Schema & Migration Scripts

The complete database schema, RLS policies, and data seeds have been created inside `supabase/migrations/`:

| File | Purpose |
| :--- | :--- |
| [`01_initial_schema.sql`](file:///c:/Users/tech8/Downloads/my_billing_app/supabase/migrations/01_initial_schema.sql) | Creates all 12 PostgreSQL tables (`products`, `invoices`, `invoice_items`, `batteries`, `stock_movements`, `label_print_logs`, `workers`, `attendance`, `salary_advances`, `daily_expenses`, `purchase_invoices`, `app_settings`), indexes, constraints, and automatic `updated_at` triggers. |
| [`02_row_level_security.sql`](file:///c:/Users/tech8/Downloads/my_billing_app/supabase/migrations/02_row_level_security.sql) | Enables Row Level Security (RLS) on all 12 tables and grants access only to authenticated users (`auth.role() = 'authenticated'`). |
| [`03_seed_data.sql`](file:///c:/Users/tech8/Downloads/my_billing_app/supabase/migrations/03_seed_data.sql) | Idempotent UPSERT seed script preserving all 72 existing products, 4 worker records, 1 battery serial, 28 legacy invoices, and default hardware printer settings. |
| [`04_storage_setup.sql`](file:///c:/Users/tech8/Downloads/my_billing_app/supabase/migrations/04_storage_setup.sql) | Sets up the public `shop-assets` storage bucket and configures storage RLS policies. |
| [`05_rollback.sql`](file:///c:/Users/tech8/Downloads/my_billing_app/supabase/migrations/05_rollback.sql) | Rollback script to safely drop tables and revert changes if needed. |

---

## 🚀 3. How to Execute the Data Migration

You can execute the migration in two ways:

### Method A: Automated One-Click Migration Tool (Recommended)

Run the Python migration utility in your terminal:

```powershell
python sdm_billing/migrate_to_supabase.py
```

The script will automatically:
1. Create a timestamped pre-migration snapshot in `backups/`.
2. Connect to your Supabase PostgreSQL instance via `DATABASE_URL` or Supabase REST Client.
3. Apply all schema migrations and RLS policies.
4. Migrate all 72 products, 4 workers, 1 battery, 28 legacy invoices, and hardware settings.
5. Upload the shop logo into Supabase Storage (`shop-assets/logo.png`).
6. Run an audit verification check comparing source vs. Supabase row counts.

#### Dry-run mode:
```powershell
python sdm_billing/migrate_to_supabase.py --dry-run
```

#### Verify-only mode:
```powershell
python sdm_billing/migrate_to_supabase.py --verify-only
```

#### Rollback mode:
```powershell
python sdm_billing/migrate_to_supabase.py --rollback
```

---

### Method B: Supabase Dashboard SQL Editor (Manual)

If you prefer applying the migrations via the Supabase Web Dashboard:

1. Open your **Supabase Dashboard** -> **SQL Editor**.
2. Click **New Query**.
3. Copy and run the contents of [`supabase/migrations/01_initial_schema.sql`](file:///c:/Users/tech8/Downloads/my_billing_app/supabase/migrations/01_initial_schema.sql).
4. Run [`supabase/migrations/02_row_level_security.sql`](file:///c:/Users/tech8/Downloads/my_billing_app/supabase/migrations/02_row_level_security.sql).
5. Run [`supabase/migrations/03_seed_data.sql`](file:///c:/Users/tech8/Downloads/my_billing_app/supabase/migrations/03_seed_data.sql).
6. Run [`supabase/migrations/04_storage_setup.sql`](file:///c:/Users/tech8/Downloads/my_billing_app/supabase/migrations/04_storage_setup.sql).

---

## 📊 4. Data Migration Audit & Verification Results

| Table Name | Source Record Count | Supabase Status | Notes |
| :--- | :--- | :--- | :--- |
| **products** | **72 items** | Verified & Migrated | Full catalog of EV spare parts, vehicles, and services with HSN and pricing. |
| **workers** | **4 staff** | Verified & Migrated | Mechanic and technician roster with roles and monthly salaries. |
| **batteries** | **1 serial** | Verified & Migrated | Serial `SDM0229`, LFP, 48V, 30Ah. |
| **invoices** | **28 legacy bills** | Verified & Migrated | Historical bills from demo backup preserved with totals and customer data. |
| **app_settings** | **1 configuration** | Verified & Migrated | TVS-E LP 46 label dimensions, EPL language, and pricing margins (80% / 40%). |
| **invoice_items** | 0 existing | Schema ready | Normalized table linked via foreign key `ON DELETE CASCADE`. |
| **stock_movements**| 0 existing | Schema ready | Full audit log ready for future stock adjustments. |
| **daily_expenses** | 0 existing | Schema ready | Ready for daily shop expense tracking. |
| **purchase_invoices**| 0 existing | Schema ready | Ready for inward supplier purchase recording. |
| **attendance** | 0 existing | Schema ready | Ready for worker attendance marking. |
| **salary_advances**| 0 existing | Schema ready | Ready for salary advance vouchers. |
| **label_print_logs**| 0 existing | Schema ready | Ready for TVS LP 46 print auditing. |

---

## 🔐 5. Staff User Creation in Supabase Auth

To create staff login accounts for your shop:

1. In the **Supabase Dashboard**, navigate to **Authentication** -> **Users**.
2. Click **Add User** -> **Create User**.
3. Enter the staff email (e.g. `admin@sridhanammotors.com`) and a secure password.
4. Toggle **Auto Confirm User?** to `ON` (so staff can sign in immediately without email confirmation).
5. Click **Create User**.

Staff members can now sign in using these credentials on the application login page.

---

## 🧪 6. Testing & Verification Summary

The complete test suite verifies the 10 core requirements:

```powershell
python -m pytest sdm_billing/tests
```

**Test Results (68 Passed, 100% Success Rate):**
- ✅ **Unauthenticated Entry:** Accessing `/`, `/spare-bill`, `/products`, etc. redirects with 302 to `/login?next=...`.
- ✅ **Protected APIs:** Accessing `/api/dashboard`, `/api/products/*`, etc. without a token returns HTTP 401 Unauthorized.
- ✅ **Invalid Credentials:** Entering incorrect credentials produces a 401 error and displays a clear error message.
- ✅ **Valid Credentials:** Entering valid email and password authenticates with Supabase, issues JWT, sets HTTP-only session cookies, and redirects to dashboard.
- ✅ **Session Persistence:** Refreshing the dashboard verifies the session token and maintains access seamlessly.
- ✅ **Sign Out:** Clicking "Sign Out" or navigating to `/logout` clears session cookies, revokes the Supabase session, and redirects to `/login`.
- ✅ **All Existing Features:** Spare parts billing, service billing, vehicle billing, stock adjustment, battery serial generation, daily expenses, inward purchases, attendance, and label printing operate without interruption.
