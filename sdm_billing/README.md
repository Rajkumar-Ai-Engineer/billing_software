# Sri Dhanam Motors - Billing & Inventory Management System

A high-performance, responsive full-stack billing and inventory management website built with **FastAPI**, **SQLAlchemy (SQLite)**, **Jinja2**, and **Vanilla JavaScript**. Designed for **Sri Dhanam Motors** (EV Sales, Services & Spares), replacing the Streamlit prototype with an enterprise-grade web application featuring native thermal barcode printing for the **TVS-E LP 46** thermal label printer.

---

## 1. Project Directory Structure

```
sdm_billing/
├── main.py                     # FastAPI application setup, middleware, lifecycle & routing
├── config.py                   # Shop metadata, margins, prefixes, and printer defaults
├── database.py                 # SQLite database engine, session factory & Base
├── models.py                   # SQLAlchemy ORM models (Product, Invoice, Item, Battery, etc.)
├── schemas.py                  # Pydantic validation schemas & request models
├── requirements.txt            # Python dependencies
├── routers/
│   ├── dashboard.py            # Analytics API & dashboard view (Daily, Weekly, Monthly)
│   ├── billing.py              # Spare, Service & Vehicle billing with atomic stock deduction
│   ├── battery.py              # Battery QR & Barcode generation with auto SDM serials
│   ├── labels.py               # Barcode label preview, settings & TVS LP 46 raw printing
│   ├── products.py             # Product catalog, inline edits, CSV/Excel upload/export
│   └── attendance.py           # Worker attendance register & month-end salary calculations
├── services/
│   ├── pricing.py              # Selling price, GST calculation & Indian currency formatting
│   ├── invoice_no.py           # Atomic sequential invoice numbering per category
│   ├── qr.py                   # High-resolution QR code & Code128 barcode generator
│   ├── labels.py               # TSPL, ZPL, and EPL command builders for TVS LP 46
│   ├── printer.py              # Windows Spooler raw printer service (pywin32)
│   ├── importer.py             # CSV/Excel cleaning, deduplication & validation preview
│   └── attendance_service.py   # 1-day paid leave formula, payroll summary & leave tracking
├── templates/
│   ├── base.html               # Global responsive layout (360px mobile ready)
│   ├── dashboard.html          # Performance analytics & Chart.js visualizations
│   ├── billing.html            # Spare & Service Bill layout with live cart & lock rule
│   ├── vehicle_billing.html    # Vehicle Bill layout with JHEV Motors dealer branding
│   ├── battery.html            # Battery serial QR generator & history
│   ├── products.html           # Product & Stock Master table with inline editing
│   ├── attendance.html         # Daily attendance register & month-end salary sheet
│   ├── pay_slip.html           # Printable staff salary voucher & WhatsApp slip
│   ├── print_invoice.html      # A4 print-optimized Tax Invoice / Estimate
│   ├── label_preview.html      # Exact mm thermal label preview with TVS print tips
│   ├── printer_settings.html   # TVS LP 46 configuration & hardware test print
│   └── login.html              # Optional staff authentication portal
├── static/
│   ├── css/style.css           # Brand styles (#2E7D32 Green, #1A365D Navy, #2B6CB0 Blue)
│   ├── js/
│   │   ├── main.js             # Toasts, modals, and universal label printing
│   │   ├── billing.js          # Cart state, stock validation, and WhatsApp sharing
│   │   ├── dashboard.js        # Dynamic Chart.js trends and date period switching
│   │   ├── products.js         # Inline editing, upload preview, and stock adjustments
│   │   └── battery.js          # Battery serial QR generation & printing
│   └── img/
│       └── logo.png            # Sri Dhanam Motors official logo
├── data/
│   ├── sdm.db                  # SQLite database file (created automatically)
│   ├── products_master.csv     # Source CSV for first-run data import
│   └── invoices.csv            # Legacy invoices CSV for first-run import
└── tests/
    ├── test_pricing.py         # Dealer vs Customer pricing & GST tests
    ├── test_invoice_no.py      # Sequential invoice numbering tests
    ├── test_stock.py           # Stock-limit enforcement & transaction tests
    ├── test_labels.py          # TSPL, ZPL, and EPL command generation tests
    └── test_api.py             # FastAPI TestClient endpoint integration tests
```

---

## 2. Quick Start & Run Steps

### Step 1: Install Dependencies
Open PowerShell or Command Prompt in the project folder and install the required packages:

```bash
cd sdm_billing
pip install -r requirements.txt
```
*(Or if using `uv`: `uv pip install -r requirements.txt`)*

### Step 2: Launch Application
Start the FastAPI server using Uvicorn:

```bash
uvicorn main:app --reload
```

The application will be live at:
- **Web Application:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Interactive API Docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 3. First-Run Data Import & Cleaning

On the very first application startup, the system automatically checks if the SQLite database (`data/sdm.db`) is initialized. If tables are empty, it loads and cleans `data/products_master.csv` and `data/invoices.csv`:

1. **Test Row Filtering:** Removes test artifacts such as `nnn` and blank rows.
2. **Email Prefix Stripping:** Strips accidental email prefixes (e.g. `SDMORTRS@GMAIL.COM0011` becomes clean `SDM0011`).
3. **Duplicate Detection:** Flags duplicate part numbers rather than silently merging stock.
4. **Negative Stock Correction:** Corrects products with negative stock (such as `-7`) to `0` and flags them for manual stock adjustment.
5. **Integer Formatting:** Normalizes floating-point strings like `8507.0` (HSN) and `9876543210.0` (Mobile) into clean numeric strings.
6. **Legacy Invoice Tagging:** Imports previous invoices and tags them as `is_legacy = True` since historical CSVs did not preserve itemized line items.

---

## 4. Configuration & Customization

All primary shop details, margins, prefixes, and printer settings are centrally managed in `config.py` and can also be adjusted via `data/settings.json` or the **Printer Settings** web page:

### Changing Shop Details (`config.py`)
```python
SHOP_NAME = "SRI DHANAM MOTORS"
SHOP_TAGLINE = "⚡ SALES, SERVICES & SPARES"
VEHICLE_SUBTITLE = "AUTHORIZED JHEV MOTORS DEALER"
SHOP_ADDRESS = "Near RTO Office Mobirippatti, Harur (Tk), Dharmapuri (Dt) - 636903"
SHOP_PHONES = "+91 9344885449, +91 8428544972"
SHOP_GSTIN = "Applied (A/F)"
WEBSITE_URL = "https://www.sridhanammotors.com"
```

### Changing Margins
- **Customer Margin:** Default is `0.80` (Cost × 1.80, 80% markup)
- **Dealer Margin:** Default is `0.40` (Cost × 1.40, 40% markup)
Adjust these in `config.py` or directly on the `/printer-settings` page without code changes.

### Invoice Number Prefixes
- Spares: `SDM/SP/<year>/<NNN>`
- Services: `SDM/SER/<year>/<NNN>`
- Vehicles: `SDM/VEH/<year>/<NNN>`

---

## 5. TVS-E LP 46 Label Printer Setup & Calibration

The system supports thermal barcode and QR code printing using the **TVS-E LP 46** thermal desktop printer across two distinct printing modes:

### Mode 1: Driver / HTML (`driver_html`)
Works with the standard Windows printer driver directly through any web browser:
1. When printing, select the **TVS LP 46** printer in your browser print dialog.
2. Under **Paper Size**, pick your label size (e.g., `50mm x 30mm`).
3. Set **Margins** to **None** and uncheck "Headers and Footers".

### Mode 2: Direct RAW Printing (`raw`)
Instant 1-click printing directly to the Windows Spooler without opening a browser print dialog:
- Generates native **TSPL** commands (`SIZE`, `GAP`, `DIRECTION`, `BARCODE`, `QRCODE`, `PRINT`).
- Also includes **ZPL II** and **EPL** command builders for units running Zebra or Eltron firmware emulation.

### How to Install TVS LP 46 Driver & Run Test Print
1. Connect the TVS LP 46 printer via USB.
2. Install the official TVS-E LP 46 printer driver for Windows. Ensure the printer appears in Windows Settings under **Printers & scanners** as `TVS LP 46`.
3. Open the web application and navigate to **Printer Settings** (`/printer-settings`).
4. In the **Target Printer** dropdown, select your installed TVS LP 46 printer.
5. Select the label size preset (default: `50 × 30 mm`, gap: `3 mm`).
6. Click **Send Test Print ("SDM TEST 1234567")**. The printer will feed and print a test barcode and QR label.

---

## 6. Page-by-Page Feature Overview

### 📊 Dashboard (`/`)
- Switch between **Daily**, **Weekly**, **Monthly**, or a custom calendar date.
- Summary cards showing Grand Total, GST collected, invoice count, and breakdowns for Spare Parts, Service, and Vehicles.
- **Chart.js** line chart displaying trends over time per category, plus a doughnut chart showing revenue share.
- Recent Invoices table with 1-click **Reprint** buttons.
- Low stock alert table listing products with stock $\le 3$.

### 🧾 Spare Bill (`/spare-bill`) & 🔧 Service Bill (`/service-bill`)
- Customer name and 10-digit mobile number validation.
- **Dealer vs. Customer** radio buttons automatically applying the 40% or 80% margin.
- **Lock Rule:** Buyer type is locked as soon as the first item is added to prevent inconsistent pricing.
- Searchable autocomplete dropdown displaying available stock.
- Real-time stock validation preventing out-of-stock or excessive quantities from being billed.
- **Save and Print:** Deducts stock atomically, records stock movement, and opens printable Tax Invoice.
- **Print Estimate:** Generates a draft estimate without deducting inventory.
- **Save & Share WhatsApp:** Deducts stock, creates invoice, and opens WhatsApp with a pre-filled thank-you message.

### 🛵 Vehicle Bill (`/vehicle-bill`)
- Dynamic **Vehicle Type** filter (Scooter, Cycle, Loader) cascading into the vehicle name selector.
- Printed subtitle displays **"AUTHORIZED JHEV MOTORS DEALER"**.
- Default vehicle GST rate of 5%.

### 🔋 Battery Serial & QR (`/battery-qr`)
- Select chemistry (`LFP` or `Li-Ion`), voltage, and capacity (Ah).
- Auto-generates serial numbers in sequence (`SDM0021`, etc.).
- Automatically creates a linked item in inventory with Stock = 1.
- Generates high-density QR code and Code128 barcode.
- 1-click label print to TVS LP 46.

### 📦 Product & Stock Master (`/products`)
- Complete product inventory table with category filter tabs and real-time search.
- **Inline Editing:** Click any product name, HSN, cost price, or GST rate to edit and press **Enter** to save instantly.
- **Stock Adjustment:** Log manual additions or stock corrections with a mandatory reason note.
- **Import CSV/Excel with Preview:** Upload a file and review errors/validation warnings before committing updates.
- **Export Data:** Download products or date-filtered invoices in CSV or Excel format.
- Individual and bulk barcode label printing.

### 👷 Worker Attendance & Month-End Salary (`/attendance`)
- **Daily Attendance Register:**
  - Standard columns: `S.No`, `Worker Name`, `A / P` (Present / Absent / Half-Day), `Date and Day` (e.g. `2026-10-08`, `Thursday`), and `Remarks/Notes`.
  - Quick 1-click **"Mark All Present"** and **"Mark All Absent"** buttons.
  - Interactive AJAX saving with instant status toast confirmation.
- **Shop Leave & Salary Policy:**
  - **1 Paid Leave Allowed Per Month:** Every worker receives 1 day paid leave per month without salary deduction (`A1 present 30 days → Full Salary`, `A2 present 29 days → Full Salary`).
  - **2+ Leaves Deduction Rule:** When a worker takes 2 days leave, 1 day salary is reduced (`Deductions = Leaves - 1`).
  - **Formula:** $\text{Daily Rate} = \frac{\text{Monthly Salary}}{\text{Days in Month}}$.
  - $\text{Salary Deducted} = \max(0, \text{Leaves} - 1) \times \text{Daily Rate}$.
  - $\text{Net Salary} = \max(0, \text{Monthly Salary} - \text{Deductions} - \text{Advances})$.
- **Month-End Payroll & Statements:**
  - Month & Year selector with summary KPI cards (Active Workers, Gross Payroll, Leave Deductions, Net Payout).
  - Export full monthly payroll register to CSV.
  - Printable official **Staff Salary Voucher / Pay Slip** (`/attendance/pay-slip/{worker_id}`).
  - **WhatsApp Share:** 1-click pre-filled salary statement sent directly to staff mobile numbers.
- **Staff Directory & Advance Payments:**
  - Add / edit / deactivate shop workers with designated roles and monthly base pay.
  - Track mid-month salary advance payouts with deduction from month-end payout.

---

## 7. Running the Automated Test Suite

Run the full pytest suite:

```bash
pytest sdm_billing/tests -v
```

Tests verify:
- Dealer vs Customer margin multipliers and GST calculations (`test_pricing.py`)
- Sequential invoice numbering and prefix formats (`test_invoice_no.py`)
- Stock limits, out-of-stock rejection, and atomic deductions (`test_stock.py`)
- TSPL, ZPL, and EPL printer command generation (`test_labels.py`)
- FastAPI endpoints, template responses, and APIs (`test_api.py`)
