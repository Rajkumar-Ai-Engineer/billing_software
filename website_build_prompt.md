# PROMPT: Build the "Sri Dhanam Motors" Billing & Inventory Website (FastAPI)

You are a senior full-stack Python developer. Build a complete, runnable billing and inventory website for **Sri Dhanam Motors**, an EV shop (Sales, Services & Spares). It replaces an existing Streamlit prototype (`app.py`) and follows my hand-drawn layouts, which are described page by page below.

Deliver working code for every file, not pseudo-code, plus a README with run steps.

---

## 1. Tech stack (fixed)

- **Backend:** FastAPI + Uvicorn, with Jinja2 server-rendered templates. Use `APIRouter` per module.
- **Frontend:** HTML + CSS + vanilla JavaScript (`fetch` for the cart and live totals). Chart.js from a CDN for graphs. No React or build step.
- **Database:** SQLite through SQLAlchemy. It is the main store, with CSV/Excel import and export (Section 8).
- **Libraries:** `qrcode`, `python-barcode`, `pandas`, `openpyxl`, `python-multipart`, `Pillow`, plus `pywin32` (Windows only, for raw printing to the TVS printer) and `pyserial` (optional, only if the printer is on the serial port).
- **Run command:** `uvicorn main:app --reload`. It must work on Windows with a plain `pip install -r requirements.txt`.
- **Responsive:** the shop staff may use a phone, so every page must be usable at 360px width.

### Project structure

```
sdm_billing/
├── main.py                 # app creation, router includes, startup
├── config.py               # shop details, margins, prefixes (all editable in one place)
├── database.py             # engine, session, Base
├── models.py               # SQLAlchemy models
├── schemas.py              # Pydantic models
├── routers/
│   ├── dashboard.py
│   ├── billing.py          # spare / service / vehicle bills (shared logic)
│   ├── battery.py
│   ├── labels.py           # barcode label preview / print / test-print endpoints
│   └── products.py
├── services/
│   ├── pricing.py          # selling price + GST calculation
│   ├── invoice_no.py       # invoice numbering
│   ├── qr.py               # QR / barcode base64 helpers
│   ├── labels.py           # label layout + TSPL / ZPL / EPL command builders
│   ├── printer.py          # sends raw commands to the TVS LP 46 (Windows spooler / USB / serial)
│   └── importer.py         # CSV/Excel import, cleaning, export
├── templates/              # base.html + one template per page + print_invoice.html
├── static/                 # css/, js/, img/logo.png
├── data/                   # sdm.db, original CSVs for first-run import
└── requirements.txt
```

---

## 2. Shop details (put in `config.py`, use in the header and the printed invoice)

- **Name:** SRI DHANAM MOTORS
- **Tagline:** ⚡ SALES, SERVICES & SPARES. For vehicle bills the printed subtitle is "AUTHORIZED JHEV MOTORS DEALER".
- **Address:** Near RTO Office Mobirippatti, Harur (Tk), Dharmapuri (Dt) - 636903
- **Phone:** +91 9344885449, +91 8428544972
- **GSTIN:** Applied (A/F)
- **Logo:** `static/img/logo.png` (use my uploaded `logo.jpg.png`)
- **Website URL for invoice QR:** `https://www.sridhanammotors.com`
- **Brand colours:** green `#2E7D32` for the shop name, navy `#1A365D` for headings and nav, blue `#2B6CB0` for the tagline.

---

## 3. Global layout (from sketch 1)

**Header on every page:** logo on the left, then shop name with address and phone lines under it.

**Navigation bar under the header** (boxed buttons, active page highlighted):

`Dashboard | Spare Bill | Service Bill | Vehicle Bill | Battery QR | Product & Stock`

```
┌──────────────────────────────────────────────────────────────┐
│ [LOGO]   SRI DHANAM MOTORS                                   │
│          ⚡ Sales, Services & Spares                          │
│          📍 address  📞 phones  GSTIN                         │
├──────────────────────────────────────────────────────────────┤
│ [Dashboard] [Spare Bill] [Service Bill] [Vehicle Bill]       │
│ [Battery QR] [Product & Stock]                               │
├──────────────────────────────────────────────────────────────┤
│                     page content                             │
└──────────────────────────────────────────────────────────────┘
```

Put the header and nav in `base.html`. On mobile the nav collapses to a horizontally scrollable bar.

---

## 4. Page: Dashboard (sketch 1)

Reports with a **Daily / Weekly / Monthly** switch. The default is Daily. Also support a custom date range if it is cheap to add.

Content:
1. **Summary cards** for the selected period: total sales (grand total), GST collected, number of invoices, and the same totals split by **Spare**, **Service**, and **Vehicle Sales**.
2. **Graph** (Chart.js): sales over time, with one series per category (Spare, Service, Vehicle Sales). Daily shows hourly or per-day points, Weekly shows 7 days, Monthly shows days of the month. Add a small pie or doughnut for the category split.
3. **Recent invoices table:** Invoice No, Date, Category, Customer, Grand Total, and a "Reprint" link.
4. **Low stock alert** list of products with stock ≤ 3.

API: `GET /api/dashboard?period=daily|weekly|monthly&date=YYYY-MM-DD` returns JSON. The page loads it with `fetch` and re-renders when the switch changes.

---

## 5. Pages: Spare Bill and Service Bill (sketch 2)

Both pages use the **same template and the same router logic**, parameterised by category (`Spare Parts` or `Service`).

### Layout

```
Spare Bill  (or Service Bill)

[ Customer Name        ]      ( ) Dealer   ( ) Customer
[ Address              ]      [ Customer Mobile No ]
[ GST mode: With GST / Without GST ]   [ GSTIN (optional) ]

[ Select Product or Part No ▼ ]  [ Qty ]  [ + Add ]

S.No | Part No | Product Name | Price | Qty | Subtotal | GST | Total | Remove Item
 ...rows...

                                   Subtotal :  ₹
                                   GST Amount: ₹
                                   Grand Total: ₹

[ Reset ]   [ Save and Print ]   [ Print Estimate ]
```

### Fields and behaviour

- **Customer Name, Address, Customer Mobile No:** text inputs. Mobile must be 10 digits (validate).
- **Dealer / Customer** is a radio choice that sets the price level (see pricing rules).
- **GST mode:** `With GST (Tax Invoice)` or `Without GST (Estimate / Cash)`. **GSTIN** is an optional, uppercase field.
- **Product selector:** a searchable dropdown (type to filter by Part No or Product Name) showing `PartNo - Name (Stock: n)`, filtered to the page's category.
- **Cart table:** adds a row per product. Adding the same Part No again increases its quantity. Each row has a **Remove Item** button. Subtotal, GST Amount and Grand Total update live as items are added or removed.
- **Lock rule (from my old code):** after the first item is added, the Dealer/Customer radio is disabled so prices don't change mid-bill. It unlocks when the cart is emptied or on Reset.
- **Stock check:** refuse to add more than the available stock (including quantity already in the cart). Show a clear error for "out of stock" and for "not enough stock".
- **Buttons:**
  - **Reset:** clears the cart and the customer fields.
  - **Save and Print:** saves the invoice, **deducts stock**, then opens the printable invoice and triggers `window.print()`.
  - **Print Estimate:** prints an "ESTIMATE / QUOTE" without saving and **without touching stock**.
  - Also keep **Save & Share WhatsApp** from my old app. It saves, deducts stock, and opens `https://wa.me/91<mobile>?text=...` with the message: "Hello {name}, Thank you for shopping at Sri Dhanam Motors! Invoice No: {no} Grand Total: ₹{total} Visit us again!"

---

## 6. Page: Vehicle Bill (sketch 3)

Same structure as the Spare Bill page, with these differences:

- Fields: **Customer Name, Address, Customer Mobile No, GST** (GST mode and optional GSTIN), plus **Select Vehicle Type**.
- **Vehicle Type** dropdown (for example Scooter, Cycle, Loader; make the list editable from the Product page). Choosing it filters the **Vehicle Name** dropdown (products in category `Vehicle Sales`).
- Cart columns: **Vehicle Type, Vehicle Name**, Price, Qty, Subtotal, GST, Total, Remove.
- Same totals, buttons, stock deduction, and Dealer/Customer logic as Section 5. Vehicle GST is usually 5%, taken from the product record.
- The printed invoice subtitle is "AUTHORIZED JHEV MOTORS DEALER".

---

## 7. Page: Battery QR (sketch 4)

A label generator for battery packs.

```
Battery QR

[ Battery Type ▼ ]     [ Voltage ]      [ Ah ]
  LFP                    (typing)         (typing)
  Li-Ion

[ Generate QR ]   [ Print Label ]
```

- **Battery Type:** dropdown with `LFP` and `Li-Ion`. **Voltage** and **Ah** are numeric typed inputs.
- On Generate, create an **auto serial number** with the `SDM0021`-style pattern (next number after the highest existing serial), and show a QR code (plus a Code128 barcode) encoding: serial, type, voltage, Ah, shop name.
- Save each generated battery in a `batteries` table (serial, type, voltage, Ah, created_at, sold flag). Show a table of generated batteries below with search and a Reprint button.
- **Print Label** sends the battery label to the TVS LP 46 label printer (see Section 12). It shows a preview first, with a quantity box for multiple copies.

> My old app named this tab "BATTERY SERIAL QR". Each battery serial also exists as a product row (for example `SDM0010`, stock 1) so it can be sold on a Spare Bill. Keep that link: generating a serial can optionally create the matching product row with stock 1.

---

## 8. Page: Product & Stock (bottom of sketch 4)

Manage products and stock, with file download/upload and easy editing.

Requirements:
- Table of all products: Part No, Product Name, HSN, Cost Price, GST %, Category, Stock Qty.
- **Easy to edit:** click a cell to edit inline and save with one click (or Enter). Add a **New Product** form and a delete button with confirmation.
- Search and filter by category.
- **Download** products as CSV and as Excel. **Upload** CSV or Excel to add or update products. Upload must show a **preview with validation errors** before committing, and match on Part No (update if it exists, insert if not).
- **Stock adjustment** (add stock / correct stock) with a reason, logged in a `stock_movements` table.
- Also allow downloading the **invoices** list as CSV/Excel with a date filter.
- **Print Label** button on every product row, and a bulk option to print labels for the selected rows, using the TVS LP 46 (see Section 12).

---

## 9. Business rules (copied from my working prototype, keep exactly)

**Selling price** = Cost Price + margin:
- **Customer:** Cost × 1.80 (80% margin)
- **Dealer:** Cost × 1.40 (40% margin)

Make both margins editable in `config.py`.

**GST:**
- With GST: `gst_amt = subtotal × gst% / 100`, where the GST % comes from the product record (for example 18% for parts and services, 5% for vehicles).
- Without GST: GST is 0 and the document title is "ESTIMATE / QUOTE" instead of "TAX INVOICE".
- Per line: `Subtotal = price × qty`; `Total = Subtotal + GST amt`.
- Footer: `Subtotal`, `GST Amount`, `Grand Total`.
- Use `Decimal` and round to 2 places. Show amounts as ₹ with Indian number grouping where practical.

**Invoice numbers:** `SDM/SP/<year>/<NNN>` for spares, `SDM/SER/<year>/<NNN>` for service, `SDM/VEH/<year>/<NNN>` for vehicles. Use a 3-digit sequence per prefix per year, starting at 001. Generate it server-side inside the save transaction so two users never get the same number.

**Stock:** deduct only on Save (Save and Print, or Save and Share). Never allow stock to go below 0. Log every deduction in `stock_movements`.

**Printed invoice** (`print_invoice.html`, A4, black on white, print-friendly CSS):
- Header with logo, shop name, subtitle, address, phones, GSTIN, and a QR code (right side) pointing to `{WEBSITE_URL}?invoice={invoice_no}`.
- "Billed To" box (name, phone, address, GSTIN or N/A) and a box with Doc No, Date and time, Category.
- Items table: S.No, Part No, Product Name, Price, Qty, Sub Total, GST %, GST Amt, Total.
- Bottom: Signature on the left, summary box (Base Amount, GST Amount, Grand Total) on the right.

---

## 10. Database models

- `Product`: part_no (unique), name, hsn, cost_price, gst_percent, category (`Spare Parts` | `Service` | `Vehicle Sales`), vehicle_type (nullable), stock_qty
- `Invoice`: invoice_no (unique), date, time, category, buyer_type, gst_mode, customer_name, mobile, address, gstin, base_total, gst_amount, grand_total
- `InvoiceItem`: invoice_id, part_no, product_name, price, qty, subtotal, gst_percent, gst_amount, total (**store the line items**; my old CSV only stored totals, so old invoices cannot be reprinted)
- `Battery`: serial, type, voltage, ah, created_at, sold
- `StockMovement`: part_no, change, reason, ref (invoice no), timestamp

---

## 11. First-run data import

On first startup, if the database is empty, import `data/products_master.csv` and `data/invoices.csv` (I will supply both). Clean the data while importing and print a report of what was fixed or skipped:

- Skip fully blank rows and obvious test rows (for example Part No `nnn`).
- The `Price` column is mostly empty. Use **Cost Price** as the source of truth and ignore `Price`.
- Several Part Nos are accidentally prefixed with an email address (`SDMORTRS@GMAIL.COM0011`). Strip that prefix and de-duplicate against `SDM0011`. Flag duplicates instead of silently merging stock.
- One product has **negative stock** (`EV Battery Pack 48V`, -7). Import it as 0 and flag it for manual correction.
- Old invoices have missing columns (Type, GST Mode, Mobile, etc.). Import with blanks and mark them "legacy, no line items".
- Convert HSN and Mobile values like `8507.0` or `9876543210.0` to clean integer strings.

---

## 12. Barcode & label printing (TVS LP 46)

My label printer is a **TVS-E LP 46** thermal barcode printer. Build printing support for it, used by the Battery QR page, the Product & Stock page, and optionally the invoice page (to print a small barcode of the invoice number).

### Printer facts to design around

- 4-inch desktop thermal printer, **203 dpi (8 dots/mm)**, maximum print width **108 mm**, media width about 19 to 120 mm. Supports direct thermal and thermal transfer.
- Connects by **USB** (the Neo model also has a serial port).
- Supports Code 128, Code 39, EAN-13, EAN-8, UPC and similar 1D codes, and 2D codes including **QR Code**, so the printer can draw barcodes and QR codes natively.
- The LP 46 Lite is documented as TSPL-EZ with EPL / ZPL / ZPL II compatibility. I am not sure which language my unit uses, so **make the language selectable** and ship a working test button (below).

### Settings (in `config.py` and editable on a small "Printer Settings" panel)

- `PRINTER_NAME`: the exact Windows printer name (default `"TVS LP 46"`). Provide a dropdown of installed printers, read with `win32print.EnumPrinters`.
- `PRINT_MODE`: `"driver_html"` or `"raw"` (see below).
- `PRINTER_LANGUAGE`: `"TSPL"`, `"ZPL"` or `"EPL"` (used in raw mode).
- `LABEL_WIDTH_MM`, `LABEL_HEIGHT_MM`: default **50 × 30 mm**; also provide presets for 38×25, 50×25 and 100×50.
- `LABEL_GAP_MM`: default 3. `DPI`: 203. `DARKNESS`: 8. `SPEED`: 4.

### Two print modes (build both)

**Mode 1: `driver_html` (simplest, works with the normal Windows driver)**
- `GET /labels/preview` returns a page sized exactly to the label with `@page { size: 50mm 30mm; margin: 0 }` and print-friendly CSS.
- The page embeds the QR and Code128 as images and calls `window.print()`. Tell the user to pick the TVS LP 46 printer, set paper size to the same label size, and set margins to None.
- Add a visible tip box with those three steps.

**Mode 2: `raw` (fast, exact, one click, no print dialog)**
- `services/labels.py` builds the printer command text for the chosen language. Required builders:
  - `build_tspl(label)`: `SIZE`, `GAP`, `DIRECTION`, `CLS`, `TEXT`, `BARCODE`, `QRCODE`, `PRINT n`
  - `build_zpl(label)`: `^XA ... ^XZ` with `^FO`, `^A0`, `^BC`, `^BQ`
  - `build_epl(label)`: `N`, `q`, `Q`, `A`, `B`, `b` (QR), `P n`
- `services/printer.py` sends the bytes to the printer with `win32print.OpenPrinter` / `StartDocPrinter` (datatype `"RAW"`) / `WritePrinter`. On non-Windows, fall back to writing to a configurable device path or return a clear "raw printing needs Windows" error.
- Endpoint `POST /api/labels/print` with a JSON body `{type, items:[{...}], copies}` returns success or a readable error (printer not found, offline, and so on).

### Label designs (all fit the default 50×30 mm)

1. **Battery label:** the shop name (small), serial number (large), "LFP 48V 30Ah" style spec line, and a QR code carrying serial, type, voltage and Ah. Also show a Code128 of the serial if there is room.
2. **Product label:** Part No (Code128 barcode), product name (up to 2 lines), and price (selling price at the Customer level). Price printing is a checkbox, default off.
3. **Invoice barcode (optional):** a small label with the Code128 of the invoice number.

Wherever the label shows a price, calculate it with the same pricing function as the bills; never duplicate the formula.

### UI

- A reusable **"Print Label"** modal with: label type, copies, label size preset, language / mode (read from settings), a **live preview**, and a Print button.
- A **Test Print** button on the Printer Settings panel that prints one sample label ("SDM TEST 1234567") so I can confirm the language, label size and alignment before real use.
- After printing, show a toast with "Sent to printer" or the exact error.
- Keep a `label_print_log` table (timestamp, label type, reference, copies, mode, success flag).

### Accuracy notes for the builder

- Convert mm to dots with `dots = mm × 8` for 203 dpi.
- Keep at least a 2 mm quiet zone around barcodes and make sure Code128 fits inside the label width; shrink the module width instead of letting it overflow.
- Do not hard-code the printer name or label size anywhere except `config.py`.

---

## 13. Quality requirements

- Validate on both client and server: required name, 10-digit mobile, valid GSTIN pattern if provided, quantity ≥ 1.
- Wrap save operations in a DB transaction so an invoice and its stock deduction succeed or fail together.
- Friendly error and success messages (toasts), no raw stack traces in the UI.
- Add `GET /docs` (FastAPI's built-in docs) and keep route names clean: `/`, `/spare-bill`, `/service-bill`, `/vehicle-bill`, `/battery-qr`, `/products`, `/invoice/{invoice_no}/print`.
- Write a few `pytest` tests for pricing (dealer vs customer, with and without GST), invoice numbering, stock-limit enforcement, and label command builders (check that the TSPL, ZPL and EPL output contains the expected size, barcode and print-count commands).
- Authentication is not in the sketches. Add a simple single-user login (password from an environment variable) behind a flag in `config.py`, off by default.

## 14. Output order

1. Short file tree.
2. `requirements.txt`.
3. Backend files, in the order: `config.py`, `database.py`, `models.py`, `schemas.py`, `services/*` (including `labels.py` and `printer.py`), `routers/*`, `main.py`.
4. Templates, CSS, JS.
5. Tests.
6. README with setup, first-run import, how to change margins, shop details, and categories, and **how to install the TVS LP 46 driver, set the printer name and label size, and run the Test Print**.

If any requirement is ambiguous, state your assumption in one line and continue rather than stopping to ask.
