import io
from datetime import date, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Form
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import pandas as pd

from database import get_db
from models import DailyExpense
from schemas import DailyExpenseCreate, DailyExpenseUpdate
from services.pricing import format_inr
import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


@router.get("/expenses", response_class=HTMLResponse)
def get_expenses_page(
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

    # Query today's expenses
    today_records = db.query(DailyExpense).filter(DailyExpense.date == selected_date).order_by(DailyExpense.id.desc()).all()
    today_total = sum(r.price for r in today_records)

    # Query this month's expenses
    start_of_month = date(calc_year, calc_month, 1)
    if calc_month == 12:
        end_of_month = date(calc_year + 1, 1, 1)
    else:
        end_of_month = date(calc_year, calc_month + 1, 1)
    
    month_records = db.query(DailyExpense).filter(
        DailyExpense.date >= start_of_month,
        DailyExpense.date < end_of_month
    ).order_by(DailyExpense.date.desc(), DailyExpense.id.desc()).all()
    month_total = sum(r.price for r in month_records)

    # Recent expenses (last 100)
    all_recent = db.query(DailyExpense).order_by(DailyExpense.date.desc(), DailyExpense.id.desc()).limit(100).all()
    all_time_total = sum(r.price for r in db.query(DailyExpense.price).all())

    return templates.TemplateResponse(
        request=request,
        name="expenses.html",
        context={
            "active_page": "expenses",
            "shop_name": config.SHOP_NAME,
            "today_date": str(today),
            "selected_date": str(selected_date),
            "calc_year": calc_year,
            "calc_month": calc_month,
            "today_expenses": [r.to_dict() for r in today_records],
            "today_total": today_total,
            "month_total": month_total,
            "all_time_total": all_time_total,
            "recent_expenses": [r.to_dict() for r in all_recent],
            "format_inr": format_inr
        }
    )


@router.get("/api/expenses")
def list_expenses_api(
    target_date: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(DailyExpense)
    if target_date:
        try:
            d = datetime.strptime(target_date, "%Y-%m-%d").date()
            query = query.filter(DailyExpense.date == d)
        except ValueError:
            pass

    if month and year:
        start_of_month = date(year, month, 1)
        if month == 12:
            end_of_month = date(year + 1, 1, 1)
        else:
            end_of_month = date(year, month + 1, 1)
        query = query.filter(DailyExpense.date >= start_of_month, DailyExpense.date < end_of_month)

    if q and q.strip():
        term = f"%{q.strip()}%"
        query = query.filter(
            (DailyExpense.bill_no.ilike(term)) |
            (DailyExpense.product_name.ilike(term)) |
            (DailyExpense.notes.ilike(term))
        )

    records = query.order_by(DailyExpense.date.desc(), DailyExpense.id.desc()).all()
    return [r.to_dict() for r in records]


@router.post("/api/expenses")
def create_expense_api(payload: DailyExpenseCreate, db: Session = Depends(get_db)):
    # Standard date: default to today if not provided or empty
    exp_date = date.today()
    if payload.date:
        try:
            exp_date = datetime.strptime(payload.date, "%Y-%m-%d").date()
        except ValueError:
            exp_date = date.today()

    bill_val = (payload.bill_no or "").strip()
    prod_val = (payload.product_name or "").strip()
    price_val = float(payload.price or 0.0)
    notes_val = (payload.notes or "").strip()

    # None of the fields are compulsory; user emphasized bill number is optional,
    # but at least an item name or amount should be given to avoid completely empty garbage.
    if not prod_val and price_val <= 0 and not bill_val:
        raise HTTPException(status_code=400, detail="Please enter at least an item name or amount.")

    new_expense = DailyExpense(
        date=exp_date,
        bill_no=bill_val,
        product_name=prod_val,
        price=price_val,
        notes=notes_val
    )
    db.add(new_expense)
    db.commit()
    db.refresh(new_expense)
    return new_expense.to_dict()


@router.delete("/api/expenses/{expense_id}")
def delete_expense_api(expense_id: int, db: Session = Depends(get_db)):
    expense = db.query(DailyExpense).filter(DailyExpense.id == expense_id).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense record not found")
    db.delete(expense)
    db.commit()
    return {"success": True, "message": f"Expense #{expense_id} deleted"}


@router.get("/api/expenses/export")
def export_expenses_csv(
    target_date: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(DailyExpense)
    if target_date:
        try:
            d = datetime.strptime(target_date, "%Y-%m-%d").date()
            query = query.filter(DailyExpense.date == d)
        except ValueError:
            pass
    elif month and year:
        start_of_month = date(year, month, 1)
        if month == 12:
            end_of_month = date(year + 1, 1, 1)
        else:
            end_of_month = date(year, month + 1, 1)
        query = query.filter(DailyExpense.date >= start_of_month, DailyExpense.date < end_of_month)

    records = query.order_by(DailyExpense.date.desc(), DailyExpense.id.desc()).all()
    rows = []
    for r in records:
        rows.append({
            "ID": r.id,
            "Date": str(r.date),
            "Bill No": r.bill_no,
            "Product / Description": r.product_name,
            "Price (₹)": r.price,
            "Notes": r.notes,
            "Created At": r.created_at.strftime("%Y-%m-%d %H:%M:%S") if r.created_at else ""
        })

    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)

    filename = f"daily_expenses_{target_date or (str(year) + '_' + str(month) if year else 'all')}.csv"
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
