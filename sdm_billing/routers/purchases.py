import io
from datetime import date, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import pandas as pd

from database import get_db
from models import PurchaseInvoice
from schemas import PurchaseInvoiceCreate, PurchaseInvoiceUpdate
from services.pricing import format_inr
import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


@router.get("/purchases", response_class=HTMLResponse)
def get_purchases_page(
    request: Request,
    target_date: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    today = date.today()
    if target_date:
        try:
            selected_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    calc_year = year or selected_date.year
    calc_month = month or selected_date.month

    # Query all purchases
    all_purchases = db.query(PurchaseInvoice).order_by(PurchaseInvoice.received_date.desc(), PurchaseInvoice.id.desc()).all()
    
    total_amount = sum(p.price for p in all_purchases)
    total_qty = sum(p.total_qty for p in all_purchases)
    total_bills = len(all_purchases)

    # This month's purchases
    start_of_month = date(calc_year, calc_month, 1)
    if calc_month == 12:
        end_of_month = date(calc_year + 1, 1, 1)
    else:
        end_of_month = date(calc_year, calc_month + 1, 1)
    
    month_purchases = db.query(PurchaseInvoice).filter(
        PurchaseInvoice.received_date >= start_of_month,
        PurchaseInvoice.received_date < end_of_month
    ).order_by(PurchaseInvoice.received_date.desc(), PurchaseInvoice.id.desc()).all()
    month_amount = sum(p.price for p in month_purchases)
    month_qty = sum(p.total_qty for p in month_purchases)

    return templates.TemplateResponse(
        request=request,
        name="purchases.html",
        context={
            "active_page": "purchases",
            "shop_name": config.SHOP_NAME,
            "today_date": str(today),
            "selected_date": str(selected_date),
            "calc_year": calc_year,
            "calc_month": calc_month,
            "purchases": [p.to_dict() for p in all_purchases],
            "total_amount": total_amount,
            "total_qty": total_qty,
            "total_bills": total_bills,
            "month_amount": month_amount,
            "month_qty": month_qty,
            "format_inr": format_inr
        }
    )


@router.get("/api/purchases")
def list_purchases_api(
    target_date: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(PurchaseInvoice)
    if target_date:
        try:
            d = datetime.strptime(target_date, "%Y-%m-%d").date()
            query = query.filter(PurchaseInvoice.received_date == d)
        except ValueError:
            pass

    if month and year:
        start_of_month = date(year, month, 1)
        if month == 12:
            end_of_month = date(year + 1, 1, 1)
        else:
            end_of_month = date(year, month + 1, 1)
        query = query.filter(PurchaseInvoice.received_date >= start_of_month, PurchaseInvoice.received_date < end_of_month)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            (PurchaseInvoice.invoice_no.ilike(term)) |
            (PurchaseInvoice.notes.ilike(term))
        )

    records = query.order_by(PurchaseInvoice.received_date.desc(), PurchaseInvoice.id.desc()).all()
    return [r.to_dict() for r in records]


@router.post("/api/purchases")
def create_purchase_api(payload: PurchaseInvoiceCreate, db: Session = Depends(get_db)):
    inv_no = (payload.invoice_no or "").strip()
    if not inv_no:
        raise HTTPException(status_code=400, detail="Invoice / Bill number is required")

    rec_date = date.today()
    if payload.received_date:
        try:
            rec_date = datetime.strptime(payload.received_date, "%Y-%m-%d").date()
        except ValueError:
            rec_date = date.today()

    price_val = float(payload.price or 0.0)
    qty_val = int(payload.total_qty or 0)
    notes_val = (payload.notes or "").strip()

    new_purchase = PurchaseInvoice(
        invoice_no=inv_no,
        received_date=rec_date,
        price=price_val,
        total_qty=qty_val,
        notes=notes_val
    )
    db.add(new_purchase)
    db.commit()
    db.refresh(new_purchase)
    return new_purchase.to_dict()


@router.delete("/api/purchases/{purchase_id}")
def delete_purchase_api(purchase_id: int, db: Session = Depends(get_db)):
    purchase = db.query(PurchaseInvoice).filter(PurchaseInvoice.id == purchase_id).first()
    if not purchase:
        raise HTTPException(status_code=404, detail="Purchase invoice record not found")
    db.delete(purchase)
    db.commit()
    return {"success": True, "message": f"Purchase #{purchase_id} deleted"}


@router.get("/api/purchases/export")
def export_purchases_csv(
    target_date: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(PurchaseInvoice)
    if target_date:
        try:
            d = datetime.strptime(target_date, "%Y-%m-%d").date()
            query = query.filter(PurchaseInvoice.received_date == d)
        except ValueError:
            pass
    elif month and year:
        start_of_month = date(year, month, 1)
        if month == 12:
            end_of_month = date(year + 1, 1, 1)
        else:
            end_of_month = date(year, month + 1, 1)
        query = query.filter(PurchaseInvoice.received_date >= start_of_month, PurchaseInvoice.received_date < end_of_month)

    records = query.order_by(PurchaseInvoice.received_date.desc(), PurchaseInvoice.id.desc()).all()
    rows = []
    for r in records:
        rows.append({
            "ID": r.id,
            "Invoice / Bill No": r.invoice_no,
            "Date Received": str(r.received_date),
            "Price / Amount (₹)": r.price,
            "Total Quantity": r.total_qty,
            "Notes / Remarks": r.notes,
            "Recorded At": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
        })

    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    filename = f"purchase_invoices_{str(year) + '_' + str(month) if year else 'all'}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
