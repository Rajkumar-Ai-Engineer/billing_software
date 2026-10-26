import io
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import pandas as pd

from database import get_db
from models import Product, StockMovement, Invoice
from schemas import ProductCreate, ProductUpdate, StockAdjustmentIn
from services.importer import parse_upload_preview, commit_upload_items
from services.pricing import calculate_selling_price, format_inr
from services.excel_sync import sync_products_to_excel_files
import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


@router.get("/products", response_class=HTMLResponse)
def get_products_page(request: Request, db: Session = Depends(get_db)):
    products = db.query(Product).order_by(Product.name.asc()).all()
    categories = ["All", "Spare Parts", "Service", "Vehicle Sales"]

    prod_list = []
    for p in products:
        d = p.to_dict()
        d["selling_customer"] = calculate_selling_price(p.cost_price, "Customer")
        d["selling_dealer"] = calculate_selling_price(p.cost_price, "Dealer")
        prod_list.append(d)

    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={
            "active_page": "products",
            "products": prod_list,
            "categories": categories,
            "shop_name": config.SHOP_NAME,
            "format_inr": format_inr
        }
    )


@router.get("/api/products")
def list_products_api(
    category: Optional[str] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Product)
    if category and category.lower() != "all":
        query = query.filter(Product.category == category)
    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter((Product.part_no.ilike(term)) | (Product.name.ilike(term)))

    products = query.order_by(Product.name.asc()).all()
    res = []
    for p in products:
        d = p.to_dict()
        d["selling_customer"] = calculate_selling_price(p.cost_price, "Customer")
        d["selling_dealer"] = calculate_selling_price(p.cost_price, "Dealer")
        res.append(d)
    return res


@router.post("/api/products")
def create_product_api(payload: ProductCreate, db: Session = Depends(get_db)):
    existing = db.query(Product).filter(Product.part_no == payload.part_no.strip()).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Part No '{payload.part_no}' already exists.")

    new_prod = Product(
        part_no=payload.part_no.strip(),
        name=payload.name.strip(),
        hsn=payload.hsn.strip() if payload.hsn else "",
        cost_price=payload.cost_price,
        gst_percent=payload.gst_percent,
        category=payload.category,
        vehicle_type=payload.vehicle_type,
        stock_qty=payload.stock_qty
    )
    db.add(new_prod)

    # Log initial stock movement if > 0
    if payload.stock_qty > 0:
        movement = StockMovement(
            part_no=new_prod.part_no,
            change=payload.stock_qty,
            reason="Initial Stock Creation",
            ref="NEW_PRODUCT",
            timestamp=datetime.now()
        )
        db.add(movement)

    db.commit()
    # Synchronize to Excel and CSV files so next time it shows immediately
    sync_products_to_excel_files(db)
    return {"success": True, "product": new_prod.to_dict()}


@router.post("/api/products/quick-add")
def quick_add_stock_api(payload: StockAdjustmentIn, db: Session = Depends(get_db)):
    """
    Direct Quick Add action from the Products table:
    Increments store inventory and saves to Excel and CSV files in real time.
    """
    prod = db.query(Product).filter(Product.part_no == payload.part_no).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found.")

    if payload.change <= 0:
        raise HTTPException(status_code=400, detail="Add quantity must be greater than zero.")

    prod.stock_qty += payload.change
    movement = StockMovement(
        part_no=prod.part_no,
        change=payload.change,
        reason=payload.reason.strip() if payload.reason else "Quick Add to Store",
        ref="QUICK_ADD",
        timestamp=datetime.now()
    )
    db.add(movement)
    db.commit()

    # Synchronize to Excel and CSV files
    sync_products_to_excel_files(db)

    return {
        "success": True,
        "part_no": prod.part_no,
        "name": prod.name,
        "stock_qty": prod.stock_qty,
        "added": payload.change
    }


@router.post("/api/products/quick-reduce")
def quick_reduce_stock_api(payload: StockAdjustmentIn, db: Session = Depends(get_db)):
    """
    Direct Quick Reduce / Remove action from the Products table:
    Decrements store inventory and saves to Excel and CSV files in real time.
    """
    prod = db.query(Product).filter(Product.part_no == payload.part_no).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found.")

    if payload.change <= 0:
        raise HTTPException(status_code=400, detail="Reduce quantity must be greater than zero.")

    if prod.stock_qty - payload.change < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reduce by {payload.change}. Available stock is only {prod.stock_qty}."
        )

    prod.stock_qty -= payload.change
    movement = StockMovement(
        part_no=prod.part_no,
        change=-payload.change,
        reason=payload.reason.strip() if payload.reason else "Quick Reduce from Store",
        ref="QUICK_REDUCE",
        timestamp=datetime.now()
    )
    db.add(movement)
    db.commit()

    # Synchronize to Excel and CSV files
    sync_products_to_excel_files(db)

    return {
        "success": True,
        "part_no": prod.part_no,
        "name": prod.name,
        "stock_qty": prod.stock_qty,
        "reduced": payload.change
    }


@router.patch("/api/products/{part_no}")
def update_product_api(part_no: str, payload: ProductUpdate, db: Session = Depends(get_db)):
    prod = db.query(Product).filter(Product.part_no == part_no).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found.")

    old_stock = prod.stock_qty

    if payload.name is not None:
        prod.name = payload.name.strip()
    if payload.hsn is not None:
        prod.hsn = payload.hsn.strip()
    if payload.cost_price is not None:
        prod.cost_price = payload.cost_price
    if payload.gst_percent is not None:
        prod.gst_percent = payload.gst_percent
    if payload.category is not None:
        prod.category = payload.category
    if payload.vehicle_type is not None:
        prod.vehicle_type = payload.vehicle_type
    if payload.stock_qty is not None and payload.stock_qty != old_stock:
        diff = payload.stock_qty - old_stock
        prod.stock_qty = payload.stock_qty
        movement = StockMovement(
            part_no=prod.part_no,
            change=diff,
            reason="Inline Stock Update",
            ref="EDIT",
            timestamp=datetime.now()
        )
        db.add(movement)

    db.commit()
    # Synchronize to Excel and CSV files
    sync_products_to_excel_files(db)
    return {"success": True, "product": prod.to_dict()}


@router.delete("/api/products/{part_no}")
def delete_product_api(part_no: str, db: Session = Depends(get_db)):
    prod = db.query(Product).filter(Product.part_no == part_no).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found.")

    db.delete(prod)
    db.commit()
    # Synchronize to Excel and CSV files
    sync_products_to_excel_files(db)
    return {"success": True, "message": f"Product '{part_no}' deleted successfully."}


@router.post("/api/products/stock-adjust")
def adjust_stock_api(payload: StockAdjustmentIn, db: Session = Depends(get_db)):
    prod = db.query(Product).filter(Product.part_no == payload.part_no).first()
    if not prod:
        raise HTTPException(status_code=404, detail="Product not found.")

    new_stock = prod.stock_qty + payload.change
    if new_stock < 0:
        raise HTTPException(status_code=400, detail="Stock cannot be reduced below zero.")

    prod.stock_qty = new_stock

    # If price was provided, update cost_price
    if payload.price is not None:
        prod.cost_price = float(payload.price)

    reason_str = payload.reason.strip() if payload.reason else "Stock Adjustment"
    if payload.price is not None:
        reason_str += f" (Price: ₹{payload.price:.2f})"

    movement = StockMovement(
        part_no=prod.part_no,
        change=payload.change,
        reason=reason_str,
        ref="MANUAL_ADJUSTMENT",
        timestamp=datetime.now()
    )
    db.add(movement)
    db.commit()

    # Synchronize to Excel and CSV files
    sync_products_to_excel_files(db)

    return {"success": True, "stock_qty": prod.stock_qty, "cost_price": prod.cost_price, "part_no": prod.part_no}


@router.post("/api/products/upload-preview")
async def upload_preview_api(file: UploadFile = File(...)):
    contents = await file.read()
    items, errors = parse_upload_preview(contents, file.filename)
    return {
        "filename": file.filename,
        "total_items": len(items),
        "items": items,
        "errors": errors
    }


@router.post("/api/products/upload-commit")
def upload_commit_api(payload: dict, db: Session = Depends(get_db)):
    items = payload.get("items", [])
    if not items:
        raise HTTPException(status_code=400, detail="No valid items provided to commit.")

    result = commit_upload_items(db, items)
    # Synchronize to Excel and CSV files
    sync_products_to_excel_files(db)
    return {"success": True, "result": result}


@router.get("/api/products/export")
def export_products_api(format: str = "csv", db: Session = Depends(get_db)):
    products = db.query(Product).all()
    data = []
    for p in products:
        data.append({
            "Part No": p.part_no,
            "Product Name": p.name,
            "HSN": p.hsn or "",
            "Cost Price": p.cost_price,
            "GST %": p.gst_percent,
            "Category": p.category,
            "Vehicle Type": p.vehicle_type or "",
            "Stock Qty": p.stock_qty
        })

    df = pd.DataFrame(data)

    if format.lower() == "excel":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Products")
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=products_export.xlsx"}
        )
    else:
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        return StreamingResponse(
            io.BytesIO(stream.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=products_export.csv"}
        )


@router.get("/api/invoices/export")
def export_invoices_api(
    format: str = "csv",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Invoice)
    if start_date:
        try:
            d_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Invoice.date >= d_start)
        except ValueError:
            pass
    if end_date:
        try:
            d_end = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Invoice.date <= d_end)
        except ValueError:
            pass

    invoices = query.order_by(Invoice.date.desc(), Invoice.id.desc()).all()
    data = []
    for inv in invoices:
        data.append({
            "Invoice No": inv.invoice_no,
            "Date": str(inv.date),
            "Time": inv.time,
            "Category": inv.category,
            "Buyer Type": inv.buyer_type,
            "GST Mode": inv.gst_mode,
            "Customer Name": inv.customer_name,
            "Mobile": inv.mobile,
            "Address": inv.address,
            "GSTIN": inv.gstin or "",
            "Base Total": inv.base_total,
            "GST Amount": inv.gst_amount,
            "Grand Total": inv.grand_total,
            "Legacy": "Yes" if inv.is_legacy else "No"
        })

    df = pd.DataFrame(data)

    if format.lower() == "excel":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Invoices")
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=invoices_export.xlsx"}
        )
    else:
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        return StreamingResponse(
            io.BytesIO(stream.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=invoices_export.csv"}
        )
