import io
import calendar
from datetime import date, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
import pandas as pd

from database import get_db
from models import Worker, Attendance, SalaryAdvance
from schemas import (
    WorkerCreate, WorkerUpdate, DailyAttendanceSaveIn, SalaryAdvanceIn
)
from services.attendance_service import (
    seed_default_workers,
    get_daily_attendance_register,
    save_daily_attendance,
    calculate_worker_salary,
    calculate_monthly_payroll,
    get_day_name,
    ALLOWED_PAID_LEAVES
)
import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


@router.get("/attendance", response_class=HTMLResponse)
def get_attendance_page(
    request: Request,
    target_date: Optional[str] = None,
    month: Optional[int] = None,
    year: Optional[int] = None,
    db: Session = Depends(get_db)
):
    # Seed workers if none exist
    seed_default_workers(db)

    # Determine date
    today = date.today()
    if target_date:
        try:
            selected_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    # Determine year & month for salary calculations
    calc_year = year or selected_date.year
    calc_month = month or selected_date.month

    # Get daily register
    daily_register = get_daily_attendance_register(selected_date, db)

    # Get payroll calculations for the month
    payroll_summary = calculate_monthly_payroll(calc_year, calc_month, db)

    # All active workers
    workers = db.query(Worker).filter(Worker.active == True).order_by(Worker.id).all()

    # Recent advances in this month
    start_m = date(calc_year, calc_month, 1)
    end_m = date(calc_year, calc_month, calendar.monthrange(calc_year, calc_month)[1])
    recent_advances = db.query(SalaryAdvance).filter(
        SalaryAdvance.date >= start_m,
        SalaryAdvance.date <= end_m
    ).order_by(SalaryAdvance.date.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="attendance.html",
        context={
            "active_page": "attendance",
            "selected_date": str(selected_date),
            "selected_day_name": get_day_name(selected_date),
            "calc_year": calc_year,
            "calc_month": calc_month,
            "calc_month_name": calendar.month_name[calc_month],
            "daily_register": daily_register,
            "payroll_summary": payroll_summary,
            "workers": [w.to_dict() for w in workers],
            "recent_advances": [a.to_dict() for a in recent_advances],
            "allowed_paid_leaves": int(ALLOWED_PAID_LEAVES),
            "shop_name": config.SHOP_NAME,
            "shop_tagline": config.SHOP_TAGLINE,
            "shop_address": config.SHOP_ADDRESS,
            "shop_phones": config.SHOP_PHONES,
        }
    )


@router.get("/attendance/pay-slip/{worker_id}", response_class=HTMLResponse)
def get_pay_slip_page(
    worker_id: int,
    request: Request,
    year: Optional[int] = None,
    month: Optional[int] = None,
    db: Session = Depends(get_db)
):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    today = date.today()
    calc_year = year or today.year
    calc_month = month or today.month

    salary_data = calculate_worker_salary(worker, calc_year, calc_month, db)

    # Advances list for details
    days_in_month = calendar.monthrange(calc_year, calc_month)[1]
    advances = db.query(SalaryAdvance).filter(
        SalaryAdvance.worker_id == worker.id,
        SalaryAdvance.date >= date(calc_year, calc_month, 1),
        SalaryAdvance.date <= date(calc_year, calc_month, days_in_month)
    ).all()

    return templates.TemplateResponse(
        request=request,
        name="pay_slip.html",
        context={
            "worker": worker.to_dict(),
            "salary": salary_data,
            "advances": [a.to_dict() for a in advances],
            "shop_name": config.SHOP_NAME,
            "shop_tagline": config.SHOP_TAGLINE,
            "shop_address": config.SHOP_ADDRESS,
            "shop_phones": config.SHOP_PHONES,
            "current_date": today.strftime("%d-%m-%Y")
        }
    )


# ---------------- API ENDPOINTS ----------------

@router.get("/api/attendance/daily")
def get_daily_attendance_api(
    date_str: str,
    db: Session = Depends(get_db)
):
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    seed_default_workers(db)
    register = get_daily_attendance_register(target_date, db)
    return {
        "date": str(target_date),
        "day_name": get_day_name(target_date),
        "records": register
    }


@router.post("/api/attendance/daily")
def save_daily_attendance_api(
    payload: DailyAttendanceSaveIn,
    db: Session = Depends(get_db)
):
    try:
        target_date = datetime.strptime(payload.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, use YYYY-MM-DD")

    records_data = [{"worker_id": r.worker_id, "status": r.status, "notes": r.notes} for r in payload.records]
    saved = save_daily_attendance(target_date, records_data, db)
    return {
        "success": True,
        "message": f"Attendance for {target_date} ({get_day_name(target_date)}) saved successfully!",
        "count": len(saved)
    }


@router.get("/api/attendance/payroll")
def get_monthly_payroll_api(
    year: int,
    month: int,
    standard_30: bool = False,
    db: Session = Depends(get_db)
):
    if not (1 <= month <= 12):
        raise HTTPException(status_code=400, detail="Invalid month")
    summary = calculate_monthly_payroll(year, month, db, standard_30_days=standard_30)
    return summary


@router.get("/api/attendance/workers")
def list_workers_api(db: Session = Depends(get_db)):
    workers = db.query(Worker).order_by(Worker.id).all()
    return [w.to_dict() for w in workers]


@router.post("/api/attendance/workers")
def create_worker_api(
    worker_in: WorkerCreate,
    db: Session = Depends(get_db)
):
    new_worker = Worker(
        name=worker_in.name.strip(),
        phone=worker_in.phone.strip(),
        role=worker_in.role.strip() if worker_in.role else "Worker",
        monthly_salary=float(worker_in.monthly_salary),
        active=worker_in.active
    )
    db.add(new_worker)
    db.commit()
    db.refresh(new_worker)
    return {"success": True, "worker": new_worker.to_dict()}


@router.put("/api/attendance/workers/{worker_id}")
def update_worker_api(
    worker_id: int,
    worker_in: WorkerUpdate,
    db: Session = Depends(get_db)
):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    if worker_in.name is not None:
        worker.name = worker_in.name.strip()
    if worker_in.phone is not None:
        worker.phone = worker_in.phone.strip()
    if worker_in.role is not None:
        worker.role = worker_in.role.strip()
    if worker_in.monthly_salary is not None:
        worker.monthly_salary = float(worker_in.monthly_salary)
    if worker_in.active is not None:
        worker.active = worker_in.active

    db.commit()
    db.refresh(worker)
    return {"success": True, "worker": worker.to_dict()}


@router.delete("/api/attendance/workers/{worker_id}")
def delete_worker_api(
    worker_id: int,
    db: Session = Depends(get_db)
):
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    worker.active = False
    db.commit()
    return {"success": True, "message": f"Worker '{worker.name}' deactivated."}


@router.post("/api/attendance/advance")
def add_salary_advance_api(
    advance_in: SalaryAdvanceIn,
    db: Session = Depends(get_db)
):
    try:
        adv_date = datetime.strptime(advance_in.date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date")

    worker = db.query(Worker).filter(Worker.id == advance_in.worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")

    adv = SalaryAdvance(
        worker_id=worker.id,
        date=adv_date,
        amount=float(advance_in.amount),
        notes=advance_in.notes or ""
    )
    db.add(adv)
    db.commit()
    db.refresh(adv)
    return {"success": True, "advance": adv.to_dict()}


@router.get("/api/attendance/export")
def export_payroll_csv(
    year: int,
    month: int,
    standard_30: bool = False,
    db: Session = Depends(get_db)
):
    payroll = calculate_monthly_payroll(year, month, db, standard_30_days=standard_30)
    month_name = payroll["month_name"]

    rows = []
    for s in payroll["worker_salaries"]:
        rows.append({
            "S.No": s["s_no"],
            "Worker Name": s["worker_name"],
            "Role": s["role"],
            "Monthly Salary (₹)": s["monthly_salary"],
            "Days in Month": s["days_in_month"],
            "Present Days": s["present_days"],
            "Absent/Leave Days": s["absent_days"],
            "Paid Leaves Allowed": s["allowed_paid_leaves"],
            "Paid Leaves Used": s["paid_leaves_used"],
            "Salary Deduction Days": s["deductible_leave_days"],
            "Daily Wage Rate (₹)": s["daily_wage"],
            "Salary Deduction (₹)": s["deduction_amount"],
            "Advance Paid (₹)": s["total_advances"],
            "Net Payable Salary (₹)": s["net_payable_salary"],
            "Rule Applied": s["rule_tag"]
        })

    df = pd.DataFrame(rows)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    csv_bytes = buf.getvalue().encode("utf-8")

    filename = f"SDM_Payroll_{month_name}_{year}.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
