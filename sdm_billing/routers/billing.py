from datetime import datetime, date
from typing import Optional, List
from urllib.parse import unquote
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import Product, Invoice, InvoiceItem, StockMovement
from schemas import InvoiceCreate
from services.pricing import calculate_selling_price, calculate_line_item, calculate_totals, format_inr
from services.invoice_no import generate_invoice_no
from services.qr import generate_qr_base64
import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


@router.get("/spare-bill", response_class=HTMLResponse)
def get_spare_bill_page(request: Request, db: Session = Depends(get_db)):
    next_inv = generate_invoice_no(db, "Spare Parts")
    return templates.TemplateResponse(
        request=request,
        name="billing.html",
        context={
            "category": "Spare Parts",
            "page_title": "Spare Bill",
            "active_page": "spare-bill",
            "default_invoice_no": next_inv,
            "today_date": date.today().strftime("%Y-%m-%d"),
            "shop_name": config.SHOP_NAME
        }
    )


@router.get("/service-bill", response_class=HTMLResponse)
def get_service_bill_page(request: Request, db: Session = Depends(get_db)):
    next_inv = generate_invoice_no(db, "Service")
    return templates.TemplateResponse(
        request=request,
        name="billing.html",
        context={
            "category": "Service",
            "page_title": "Service Bill",
            "active_page": "service-bill",
            "default_invoice_no": next_inv,
            "today_date": date.today().strftime("%Y-%m-%d"),
            "shop_name": config.SHOP_NAME
        }
    )


@router.get("/vehicle-bill", response_class=HTMLResponse)
def get_vehicle_bill_page(request: Request, db: Session = Depends(get_db)):
    next_inv = generate_invoice_no(db, "Vehicle Sales")
    return templates.TemplateResponse(
        request=request,
        name="vehicle_billing.html",
        context={
            "category": "Vehicle Sales",
            "page_title": "Vehicle Bill",
            "active_page": "vehicle-bill",
            "default_invoice_no": next_inv,
            "today_date": date.today().strftime("%Y-%m-%d"),
            "shop_name": config.SHOP_NAME
        }
    )


@router.get("/api/billing/products")
def get_billing_products(
    category: Optional[str] = "All",
    vehicle_type: Optional[str] = None,
    buyer_type: str = "Customer",
    margin_percent: Optional[float] = None,
    bill_category: Optional[str] = None,
    exclude_category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Product)
    if bill_category:
        if bill_category == "Spare Parts":
            query = query.filter(Product.category == "Spare Parts")
        elif bill_category == "Service":
            query = query.filter(Product.category != "Vehicle Sales")
        elif bill_category == "Vehicle Sales":
            query = query.filter(Product.category != "Service")
    elif exclude_category:
        excludes = [x.strip() for x in exclude_category.split(",") if x.strip()]
        for ex in excludes:
            query = query.filter(Product.category != ex)

    if category and category.lower() != "all":
        query = query.filter(Product.category == category)
    if vehicle_type and vehicle_type.lower() != "all":
        query = query.filter(Product.vehicle_type == vehicle_type)

    products = query.order_by(Product.name.asc()).all()

    effective_margin = margin_percent
    if category == "Vehicle Sales" and effective_margin is None:
        effective_margin = 15.0

    result = []
    for p in products:
        item_margin = effective_margin
        if p.category == "Vehicle Sales" and item_margin is None:
            item_margin = 15.0
        elif p.category != "Vehicle Sales" and effective_margin is not None:
            item_margin = None
        selling_price = calculate_selling_price(p.cost_price, buyer_type, margin_percent=item_margin)
        result.append({
            "id": p.id,
            "part_no": p.part_no,
            "name": p.name,
            "hsn": p.hsn or "",
            "cost_price": float(p.cost_price),
            "selling_price": selling_price,
            "gst_percent": float(p.gst_percent),
            "stock_qty": int(p.stock_qty),
            "category": p.category or "Spare Parts",
            "vehicle_type": p.vehicle_type or ""
        })
    return result


@router.get("/api/billing/next-invoice-no")
def get_next_invoice_no_api(category: str, db: Session = Depends(get_db)):
    next_no = generate_invoice_no(db, category)
    return {"invoice_no": next_no}


@router.post("/api/billing/calculate")
def calculate_cart(payload: dict = Body(...)):
    """
    Calculates line items and totals given cart products, buyer_type, and gst_mode.
    """
    items = payload.get("items", [])
    buyer_type = payload.get("buyer_type", "Customer")
    gst_mode = payload.get("gst_mode", "With GST (Tax Invoice)")
    margin_percent = payload.get("margin_percent")
    if margin_percent is not None:
        try:
            margin_percent = float(margin_percent)
        except (ValueError, TypeError):
            margin_percent = None

    is_gst_bill = "with gst" in gst_mode.lower()

    calculated_items = []
    for item in items:
        cost = float(item.get("cost_price", 0.0))
        qty = int(item.get("qty", 1))
        gst_pct = float(item.get("gst_percent", 18.0))
        item_cat = item.get("category", "")
        item_marg = margin_percent
        if item_cat == "Vehicle Sales" and item_marg is None:
            item_marg = 15.0
        elif item_cat and item_cat != "Vehicle Sales" and margin_percent is not None:
            item_marg = None

        calc = calculate_line_item(cost, qty, gst_pct, is_gst_bill, buyer_type, margin_percent=item_marg)
        calc.update({
            "part_no": item.get("part_no"),
            "product_name": item.get("product_name"),
            "category": item_cat,
            "vehicle_type": item.get("vehicle_type", "")
        })
        calculated_items.append(calc)

    totals = calculate_totals(calculated_items)
    return {
        "items": calculated_items,
        "totals": totals
    }


@router.post("/api/billing/save")
def save_invoice(invoice_data: InvoiceCreate, db: Session = Depends(get_db)):
    """
    Transactional save of invoice and stock deduction.
    """
    if not invoice_data.items:
        raise HTTPException(status_code=400, detail="Cannot save invoice with empty cart.")

    is_gst_bill = "with gst" in invoice_data.gst_mode.lower()

    # Determine effective margin for Vehicle Sales
    item_margin = None
    if invoice_data.category == "Vehicle Sales":
        item_margin = invoice_data.margin_percent if invoice_data.margin_percent is not None else 15.0
    elif invoice_data.margin_percent is not None:
        item_margin = invoice_data.margin_percent

    # Begin transaction
    try:
        # 1. Validate stock availability and category compatibility for all items
        for item in invoice_data.items:
            product = db.query(Product).filter(Product.part_no == item.part_no).with_for_update().first()
            if not product:
                raise HTTPException(status_code=400, detail=f"Product with Part No '{item.part_no}' not found.")
            if invoice_data.category == "Spare Parts" and product.category != "Spare Parts":
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot add '{product.name}' ({product.category}) to a Spare Bill. Spare Bills can only contain Spare Parts."
                )
            if invoice_data.category == "Service" and product.category == "Vehicle Sales":
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot add '{product.name}' (Vehicle Sales) to a Service Bill."
                )
            if invoice_data.category == "Vehicle Sales" and product.category == "Service":
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot add '{product.name}' (Service) to a Vehicle Bill."
                )
            if product.stock_qty <= 0:
                raise HTTPException(
                    status_code=400,
                    detail=f"Product '{product.name}' ({product.part_no}) is OUT OF STOCK! (Available: 0)"
                )
            if item.qty > product.stock_qty:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough stock for '{product.name}'. Available: {product.stock_qty}, Requested: {item.qty}"
                )

        # 2. Generate Invoice Number inside transaction
        inv_no = generate_invoice_no(db, invoice_data.category)
        today = date.today()
        now_time = datetime.now().strftime("%I:%M %p")

        # 3. Calculate server-side verified totals
        line_records = []
        base_total = 0.0
        gst_total = 0.0

        for item in invoice_data.items:
            product = db.query(Product).filter(Product.part_no == item.part_no).first()
            # Calculate item using server-side formula to prevent tampering
            current_margin = item_margin
            if product.category == "Vehicle Sales" and current_margin is None:
                current_margin = 15.0
            elif product.category != "Vehicle Sales" and invoice_data.category == "Vehicle Sales":
                current_margin = None

            calc = calculate_line_item(
                product.cost_price,
                item.qty,
                product.gst_percent,
                is_gst_bill,
                invoice_data.buyer_type,
                margin_percent=current_margin
            )

            # Deduct stock
            product.stock_qty -= item.qty

            # Log stock movement
            movement = StockMovement(
                part_no=product.part_no,
                change=-item.qty,
                reason=f"Sale on Invoice {inv_no}",
                ref=inv_no,
                timestamp=datetime.now()
            )
            db.add(movement)

            base_total += calc["subtotal"]
            gst_total += calc["gst_amount"]

            line_records.append({
                "part_no": product.part_no,
                "product_name": product.name,
                "price": calc["unit_price"],
                "qty": item.qty,
                "subtotal": calc["subtotal"],
                "gst_percent": calc["gst_percent"],
                "gst_amount": calc["gst_amount"],
                "total": calc["total"]
            })

        grand_total = round(base_total + gst_total, 2)

        # 4. Create Invoice Record
        new_invoice = Invoice(
            invoice_no=inv_no,
            date=today,
            time=now_time,
            category=invoice_data.category,
            buyer_type=invoice_data.buyer_type,
            gst_mode=invoice_data.gst_mode,
            customer_name=invoice_data.customer_name.strip(),
            mobile=invoice_data.mobile.strip(),
            address=(invoice_data.address or "").strip(),
            gstin=(invoice_data.gstin or "").strip(),
            base_total=round(base_total, 2),
            gst_amount=round(gst_total, 2),
            grand_total=grand_total,
            is_legacy=False
        )
        db.add(new_invoice)
        db.flush()  # get new_invoice.id

        # 5. Create InvoiceItem records
        for lr in line_records:
            db_item = InvoiceItem(
                invoice_id=new_invoice.id,
                part_no=lr["part_no"],
                product_name=lr["product_name"],
                price=lr["price"],
                qty=lr["qty"],
                subtotal=lr["subtotal"],
                gst_percent=lr["gst_percent"],
                gst_amount=lr["gst_amount"],
                total=lr["total"]
            )
            db.add(db_item)

        db.commit()

        return {
            "success": True,
            "invoice_no": inv_no,
            "grand_total": grand_total,
            "customer_name": new_invoice.customer_name,
            "mobile": new_invoice.mobile
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database transaction error: {str(e)}")


@router.get("/invoice/{invoice_no:path}/print", response_class=HTMLResponse)
@router.get("/invoice/{invoice_no:path}", response_class=HTMLResponse)
@router.get("/invoice-print", response_class=HTMLResponse)
def print_invoice_view(request: Request, invoice_no: str = "", no: Optional[str] = None, db: Session = Depends(get_db)):
    target_no = unquote(no if no else invoice_no).strip()
    if target_no.endswith("/print"):
        target_no = target_no[:-6]

    invoice = db.query(Invoice).filter(Invoice.invoice_no == target_no).first()
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice '{target_no}' not found.")

    is_vehicle = invoice.category == "Vehicle Sales"
    subtitle = config.VEHICLE_SUBTITLE if is_vehicle else config.SHOP_TAGLINE
    doc_title = "TAX INVOICE" if "with gst" in invoice.gst_mode.lower() else "ESTIMATE"

    # Generate QR Code carrying invoice verification URL
    inv_url = f"{config.WEBSITE_URL}?invoice={invoice.invoice_no}"
    qr_b64 = generate_qr_base64(inv_url, box_size=3)

    return templates.TemplateResponse(
        request=request,
        name="print_invoice.html",
        context={
            "invoice": invoice,
            "items": invoice.items,
            "doc_title": doc_title,
            "brand_subtitle": subtitle,
            "qr_b64": qr_b64,
            "shop_name": config.SHOP_NAME,
            "shop_address": config.SHOP_ADDRESS,
            "shop_phones": config.SHOP_PHONES,
            "shop_gstin": config.SHOP_GSTIN,
            "format_inr": format_inr,
            "is_estimate": False
        }
    )


@router.post("/estimate/print", response_class=HTMLResponse)
def print_estimate_view(request: Request, payload: dict = Body(...)):
    """
    Renders print view for an Estimate WITHOUT saving to DB or deducting stock.
    """
    category = payload.get("category", "Spare Parts")
    is_vehicle = category == "Vehicle Sales"
    subtitle = config.VEHICLE_SUBTITLE if is_vehicle else config.SHOP_TAGLINE
    doc_no = payload.get("invoice_no", "ESTIMATE-DRAFT")

    raw_items = payload.get("items", [])
    formatted_items = []
    for it in raw_items:
        price_val = float(it.get("price", it.get("unit_price", 0.0)))
        qty_val = int(it.get("qty", 1))
        subtotal_val = float(it.get("subtotal", round(price_val * qty_val, 2)))
        gst_pct = float(it.get("gst_percent", 0.0))
        gst_amt = float(it.get("gst_amount", 0.0))
        tot_val = float(it.get("total", round(subtotal_val + gst_amt, 2)))

        formatted_items.append({
            "part_no": it.get("part_no", ""),
            "product_name": it.get("product_name", ""),
            "price": price_val,
            "qty": qty_val,
            "subtotal": subtotal_val,
            "gst_percent": gst_pct,
            "gst_amount": gst_amt,
            "total": tot_val
        })

    totals = payload.get("totals", {})

    dummy_invoice = {
        "invoice_no": doc_no,
        "date": date.today().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%I:%M %p"),
        "category": category,
        "customer_name": payload.get("customer_name", "Customer"),
        "mobile": payload.get("mobile", ""),
        "address": payload.get("address", ""),
        "gstin": payload.get("gstin", ""),
        "base_total": float(totals.get("base_total", 0.0)),
        "gst_amount": float(totals.get("gst_amount", 0.0)),
        "grand_total": float(totals.get("grand_total", 0.0))
    }

    inv_url = f"{config.WEBSITE_URL}?estimate={doc_no}"
    qr_b64 = generate_qr_base64(inv_url, box_size=3)

    return templates.TemplateResponse(
        request=request,
        name="print_invoice.html",
        context={
            "invoice": dummy_invoice,
            "items": formatted_items,
            "doc_title": "ESTIMATE",
            "brand_subtitle": subtitle,
            "qr_b64": qr_b64,
            "shop_name": config.SHOP_NAME,
            "shop_address": config.SHOP_ADDRESS,
            "shop_phones": config.SHOP_PHONES,
            "shop_gstin": config.SHOP_GSTIN,
            "format_inr": format_inr,
            "is_estimate": True
        }
    )
