import io
from pathlib import Path
import pandas as pd
from sqlalchemy.orm import Session
from models import Product
import config


def sync_products_to_excel_files(db: Session) -> dict:
    """
    Synchronizes all products from SQLite database to CSV and Excel files:
    - sdm_billing/data/products_master.csv
    - sdm_billing/data/products_master.xlsx
    - root products_master.csv
    - root products_master.xlsx
    Ensures that when products or stock are added in the website,
    they are permanently stored in the Excel files so next time they will show.
    """
    products = db.query(Product).order_by(Product.name.asc()).all()
    rows = []
    for p in products:
        cost = float(p.cost_price) if p.cost_price is not None else 0.0
        gst = float(p.gst_percent) if p.gst_percent is not None else 18.0
        stock = int(p.stock_qty) if p.stock_qty is not None else 0
        rows.append({
            "Part No": p.part_no,
            "Product Name": p.name,
            "HSN": p.hsn or "",
            "Cost Price": cost,
            "Price": cost,
            "GST %": gst,
            "Category": p.category or "Spare Parts",
            "Vehicle Type": p.vehicle_type or "",
            "Stock Qty": stock
        })

    df = pd.DataFrame(rows)

    targets = [
        config.DATA_DIR / "products_master.csv",
        config.DATA_DIR / "products_master.xlsx",
        config.BASE_DIR.parent / "products_master.csv",
        config.BASE_DIR.parent / "products_master.xlsx"
    ]

    saved_paths = []
    for target in targets:
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if str(target).lower().endswith(".xlsx"):
                with pd.ExcelWriter(target, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name="Products")
            else:
                df.to_csv(target, index=False, encoding="utf-8")
            saved_paths.append(str(target))
        except Exception as e:
            print(f"Warning: could not sync to {target}: {e}")

    return {
        "total_products": len(rows),
        "synced_targets": saved_paths
    }
