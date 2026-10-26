import re
import io
from datetime import datetime, date
from typing import Dict, Any, List, Tuple
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session
from models import Product, Invoice, InvoiceItem, StockMovement
import config


def clean_int_str(val: Any) -> str:
    """Cleans '8507.0' or 8507 into '8507'."""
    if pd.isna(val) or val is None or str(val).strip() == "":
        return ""
    try:
        f = float(val)
        return str(int(f))
    except (ValueError, TypeError):
        return str(val).strip()


def clean_mobile_str(val: Any) -> str:
    """Cleans phone numbers like '9876543210.0' to '9876543210'."""
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    if s.endswith(".0"):
        s = s[:-2]
    digits = "".join(filter(str.isdigit, s))
    if digits.startswith("91") and len(digits) == 12:
        return digits[2:]
    return digits


def clean_part_no(raw_part: Any) -> str:
    """
    Cleans Part No and strips accidental email prefixes like SDMORTRS@GMAIL.COM0011 -> SDM0011
    """
    if pd.isna(raw_part) or raw_part is None:
        return ""
    s = str(raw_part).strip()
    if "@" in s:
        # e.g., SDMORTRS@GMAIL.COM0011 -> SDM0011
        m = re.search(r"@.*?(?:\.COM|\.IN|\.ORG|\.NET)?(\d+)$", s, re.IGNORECASE)
        if m:
            digits = m.group(1)
            return f"SDM{digits}"
        # Alternative pattern: strip everything before digits
        m_dig = re.search(r"(\d+)$", s)
        if m_dig:
            return f"SDM{m_dig.group(1)}"
    return s


def run_first_run_import(db: Session) -> Dict[str, Any]:
    """
    Imports products_master.csv and invoices.csv on initial startup if tables are empty.
    Applies all cleaning and business rules from Section 11.
    """
    report = {
        "products_imported": 0,
        "products_skipped": 0,
        "products_flagged": [],
        "invoices_imported": 0,
        "invoices_skipped": 0,
        "messages": []
    }

    # 1. Product Master Import
    prod_count = db.query(Product).count()
    prod_csv_path = config.DATA_DIR / "products_master.csv"

    if prod_count == 0 and prod_csv_path.exists():
        try:
            df_prods = pd.read_csv(prod_csv_path)
            seen_parts = {}

            for idx, row in df_prods.iterrows():
                raw_part = row.get("Part No")
                if pd.isna(raw_part) or str(raw_part).strip() == "" or str(raw_part).strip().lower() == "nan":
                    report["products_skipped"] += 1
                    continue

                part_no = clean_part_no(raw_part)
                # Skip test row
                if part_no.lower() in ("nnn", "test", "xxx"):
                    report["products_skipped"] += 1
                    report["messages"].append(f"Skipped test row: {raw_part}")
                    continue

                name = str(row.get("Product Name", "")).strip()
                if not name or name.lower() == "nan":
                    name = f"Item {part_no}"

                # Cost price is source of truth
                cost_val = row.get("Cost Price")
                if pd.isna(cost_val) or cost_val == "":
                    cost_val = row.get("Price", 0.0)
                try:
                    cost_price = float(cost_val) if not pd.isna(cost_val) else 0.0
                except ValueError:
                    cost_price = 0.0

                # Stock qty handling - negative stock imported as 0
                raw_stock = row.get("Stock Qty", 0)
                try:
                    stock_qty = int(float(raw_stock)) if not pd.isna(raw_stock) else 0
                except (ValueError, TypeError):
                    stock_qty = 0

                if stock_qty < 0:
                    report["products_flagged"].append(
                        f"Product '{part_no}' ({name}) had negative stock ({stock_qty}). Imported as 0 for manual correction."
                    )
                    stock_qty = 0

                # Check duplicate part numbers
                if part_no in seen_parts:
                    report["products_flagged"].append(
                        f"Duplicate Part No detected: '{part_no}' (original raw: '{raw_part}'). Skipped duplicate row instead of merging."
                    )
                    report["products_skipped"] += 1
                    continue

                seen_parts[part_no] = True

                hsn = clean_int_str(row.get("HSN"))
                category = str(row.get("Category", "Spare Parts")).strip()
                if not category or category.lower() == "nan":
                    category = "Spare Parts"

                gst_pct = 18.0
                try:
                    raw_gst = row.get("GST %")
                    if not pd.isna(raw_gst):
                        gst_pct = float(raw_gst)
                except ValueError:
                    gst_pct = 18.0

                vehicle_type = None

                product = Product(
                    part_no=part_no,
                    name=name,
                    hsn=hsn,
                    cost_price=cost_price,
                    gst_percent=gst_pct,
                    category=category,
                    vehicle_type=vehicle_type,
                    stock_qty=stock_qty
                )
                db.add(product)
                report["products_imported"] += 1

            db.commit()
            report["messages"].append(f"Successfully imported {report['products_imported']} products.")
        except Exception as e:
            db.rollback()
            report["messages"].append(f"Error importing products_master.csv: {e}")

    # 2. Invoices Import
    inv_count = db.query(Invoice).count()
    inv_csv_path = config.DATA_DIR / "invoices.csv"

    if inv_count == 0 and inv_csv_path.exists():
        try:
            df_inv = pd.read_csv(inv_csv_path)
            for idx, row in df_inv.iterrows():
                inv_no = str(row.get("Invoice No", "")).strip()
                if not inv_no or inv_no.lower() == "nan":
                    report["invoices_skipped"] += 1
                    continue

                raw_date = row.get("Date")
                inv_date = date.today()
                if not pd.isna(raw_date):
                    try:
                        inv_date = datetime.strptime(str(raw_date).strip(), "%Y-%m-%d").date()
                    except ValueError:
                        inv_date = date.today()

                category = str(row.get("Category", "Spare Parts")).strip()
                customer_name = str(row.get("Customer", "")).strip()
                if customer_name.lower() == "nan":
                    customer_name = ""

                buyer_type = str(row.get("Type", "Customer")).strip()
                if not buyer_type or buyer_type.lower() == "nan":
                    buyer_type = "Customer"

                gst_mode = str(row.get("GST Mode", "With GST (Tax Invoice)")).strip()
                if not gst_mode or gst_mode.lower() == "nan":
                    gst_mode = "With GST (Tax Invoice)"

                mobile = clean_mobile_str(row.get("Mobile"))
                address = str(row.get("Address", "")).strip()
                if address.lower() == "nan":
                    address = ""
                gstin = str(row.get("GSTIN", "")).strip()
                if gstin.lower() == "nan":
                    gstin = ""

                def safe_float(v):
                    try:
                        return float(v) if not pd.isna(v) else 0.0
                    except (ValueError, TypeError):
                        return 0.0

                base_total = safe_float(row.get("Base Total"))
                gst_amount = safe_float(row.get("GST Amount"))
                grand_total = safe_float(row.get("Grand Total"))

                inv = Invoice(
                    invoice_no=inv_no,
                    date=inv_date,
                    time="10:00 AM",
                    category=category,
                    buyer_type=buyer_type,
                    gst_mode=gst_mode,
                    customer_name=customer_name,
                    mobile=mobile,
                    address=address,
                    gstin=gstin,
                    base_total=base_total,
                    gst_amount=gst_amount,
                    grand_total=grand_total,
                    is_legacy=True  # Legacy invoice without stored line items
                )
                db.add(inv)
                report["invoices_imported"] += 1

            db.commit()
            report["messages"].append(f"Successfully imported {report['invoices_imported']} legacy invoices.")
        except Exception as e:
            db.rollback()
            report["messages"].append(f"Error importing invoices.csv: {e}")

    return report


def parse_upload_preview(file_bytes: bytes, filename: str) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Parses uploaded CSV or Excel file and returns preview rows along with validation error notes.
    """
    errors = []
    items = []

    try:
        if filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(file_bytes))
        elif filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            return [], ["Unsupported file format. Please upload .csv or .xlsx"]
    except Exception as e:
        return [], [f"Failed to read file: {e}"]

    # Required column aliases mapping
    col_map = {}
    for col in df.columns:
        c_clean = str(col).strip().lower().replace("_", " ")
        if "part" in c_clean or "code" in c_clean:
            col_map["part_no"] = col
        elif "product" in c_clean or "name" in c_clean or "desc" in c_clean:
            col_map["name"] = col
        elif "hsn" in c_clean:
            col_map["hsn"] = col
        elif "cost" in c_clean:
            col_map["cost_price"] = col
        elif "gst" in c_clean or "tax" in c_clean:
            col_map["gst_percent"] = col
        elif "cat" in c_clean:
            col_map["category"] = col
        elif "stock" in c_clean or "qty" in c_clean:
            col_map["stock_qty"] = col
        elif "veh" in c_clean:
            col_map["vehicle_type"] = col

    if "part_no" not in col_map:
        return [], ["Missing required column: 'Part No'"]

    for row_idx, row in df.iterrows():
        raw_part = row[col_map["part_no"]]
        if pd.isna(raw_part) or str(raw_part).strip() == "":
            continue

        part_no = clean_part_no(raw_part)
        raw_name = row[col_map["name"]] if "name" in col_map else f"Item {part_no}"
        name = str(raw_name).strip() if not pd.isna(raw_name) else f"Item {part_no}"

        # Cost Price
        raw_cost = row[col_map["cost_price"]] if "cost_price" in col_map else 0.0
        try:
            cost_price = float(raw_cost) if not pd.isna(raw_cost) else 0.0
        except ValueError:
            cost_price = 0.0
            errors.append(f"Row {row_idx + 2}: Invalid Cost Price for '{part_no}', default to 0.0")

        # GST %
        raw_gst = row[col_map["gst_percent"]] if "gst_percent" in col_map else 18.0
        try:
            gst_percent = float(raw_gst) if not pd.isna(raw_gst) else 18.0
        except ValueError:
            gst_percent = 18.0

        # Stock Qty
        raw_qty = row[col_map["stock_qty"]] if "stock_qty" in col_map else 0
        try:
            stock_qty = int(float(raw_qty)) if not pd.isna(raw_qty) else 0
            if stock_qty < 0:
                errors.append(f"Row {row_idx + 2}: Negative stock for '{part_no}' adjusted to 0")
                stock_qty = 0
        except ValueError:
            stock_qty = 0

        hsn = clean_int_str(row[col_map["hsn"]]) if "hsn" in col_map else ""
        category = str(row[col_map["category"]]).strip() if "category" in col_map and not pd.isna(row[col_map["category"]]) else "Spare Parts"
        v_type = str(row[col_map["vehicle_type"]]).strip() if "vehicle_type" in col_map and not pd.isna(row[col_map["vehicle_type"]]) else ""

        items.append({
            "part_no": part_no,
            "name": name,
            "hsn": hsn,
            "cost_price": cost_price,
            "gst_percent": gst_percent,
            "category": category,
            "vehicle_type": v_type,
            "stock_qty": stock_qty
        })

    return items, errors


def commit_upload_items(db: Session, items: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Commits items to database: match on part_no, update if exists, insert if not.
    """
    inserted = 0
    updated = 0

    for item in items:
        part_no = item["part_no"]
        existing = db.query(Product).filter(Product.part_no == part_no).first()
        if existing:
            existing.name = item["name"]
            existing.hsn = item["hsn"]
            existing.cost_price = item["cost_price"]
            existing.gst_percent = item["gst_percent"]
            existing.category = item["category"]
            if item.get("vehicle_type"):
                existing.vehicle_type = item["vehicle_type"]
            existing.stock_qty = item["stock_qty"]
            updated += 1
        else:
            new_prod = Product(
                part_no=part_no,
                name=item["name"],
                hsn=item["hsn"],
                cost_price=item["cost_price"],
                gst_percent=item["gst_percent"],
                category=item["category"],
                vehicle_type=item.get("vehicle_type"),
                stock_qty=item["stock_qty"]
            )
            db.add(new_prod)
            inserted += 1

    db.commit()
    return {"inserted": inserted, "updated": updated}
