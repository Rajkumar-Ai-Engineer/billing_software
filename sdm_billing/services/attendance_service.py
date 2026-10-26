import calendar
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import extract

from models import Worker, Attendance, SalaryAdvance


ALLOWED_PAID_LEAVES = 1.0  # 1 Paid Leave per month as per shop policy


def seed_default_workers(db: Session) -> List[Worker]:
    """
    Seeds initial workers if none exist in the database.
    Includes A1 and A2 from the specification notes.
    """
    existing_count = db.query(Worker).count()
    if existing_count == 0:
        sample_workers = [
            Worker(name="A1 (Senior Mechanic)", phone="9344885449", role="Senior Mechanic", monthly_salary=18000.0, active=True),
            Worker(name="A2 (EV Technician)", phone="8428544972", role="EV Technician", monthly_salary=15000.0, active=True),
            Worker(name="Kumar (Battery Specialist)", phone="9876543210", role="Battery Specialist", monthly_salary=16000.0, active=True),
            Worker(name="Suresh (Helper)", phone="9123456780", role="Helper", monthly_salary=12000.0, active=True),
        ]
        db.add_all(sample_workers)
        db.commit()
    return db.query(Worker).filter(Worker.active == True).order_by(Worker.id).all()


def get_day_name(target_date: date) -> str:
    """Returns day name e.g. 'Thursday'"""
    return target_date.strftime("%A")


def save_daily_attendance(
    target_date: date,
    records: List[Dict[str, Any]],
    db: Session
) -> List[Attendance]:
    """
    Saves or updates daily attendance for a list of workers for the given date.
    records: [{'worker_id': int, 'status': 'P'|'A'|'HD', 'notes': str}]
    """
    day_name = get_day_name(target_date)
    saved_records = []

    for item in records:
        w_id = item["worker_id"]
        status = item.get("status", "P").upper()
        if status not in ("P", "A", "HD"):
            status = "P"
        notes = item.get("notes", "")

        existing = db.query(Attendance).filter(
            Attendance.worker_id == w_id,
            Attendance.date == target_date
        ).first()

        if existing:
            existing.status = status
            existing.day_name = day_name
            existing.notes = notes
            saved_records.append(existing)
        else:
            new_att = Attendance(
                worker_id=w_id,
                date=target_date,
                day_name=day_name,
                status=status,
                notes=notes
            )
            db.add(new_att)
            saved_records.append(new_att)

    db.commit()
    return saved_records


def get_daily_attendance_register(target_date: date, db: Session) -> List[Dict[str, Any]]:
    """
    Returns the attendance register for all active workers on a given date.
    If no record exists for a worker on that date, defaults status to 'P' (or unrecorded).
    """
    workers = db.query(Worker).filter(Worker.active == True).order_by(Worker.id).all()
    records = db.query(Attendance).filter(Attendance.date == target_date).all()
    record_map = {r.worker_id: r for r in records}
    day_name = get_day_name(target_date)

    result = []
    for idx, w in enumerate(workers, start=1):
        att = record_map.get(w.id)
        result.append({
            "s_no": idx,
            "worker_id": w.id,
            "worker_name": w.name,
            "role": w.role,
            "phone": w.phone,
            "monthly_salary": float(w.monthly_salary),
            "date": str(target_date),
            "day_name": day_name,
            "status": att.status if att else "P",
            "is_marked": att is not None,
            "notes": att.notes if att else ""
        })
    return result


def calculate_worker_salary(
    worker: Worker,
    year: int,
    month: int,
    db: Session,
    standard_30_days: bool = False
) -> Dict[str, Any]:
    """
    Calculates overall monthly salary for a worker based on the shop attendance policy:
    1. Base pay with 1 day paid leave allowed per month:
       - Present in 30 days (0 leave): Salary is full (same).
       - Present in 29 days (1 leave): Salary is full (same - 1 day paid leave).
    2. 2+ days leave reduces 1 day salary per extra leave day:
       - 2 days leave: 1 day salary reduced (deductible days = 2 - 1 = 1).
       - 3 days leave: 2 days salary reduced (deductible days = 3 - 1 = 2).
       - N days leave: (N - 1) days salary reduced.
    """
    days_in_month = calendar.monthrange(year, month)[1]
    divisor_days = 30 if standard_30_days else days_in_month

    start_date = date(year, month, 1)
    end_date = date(year, month, days_in_month)

    # Query attendance records in the month
    records = db.query(Attendance).filter(
        Attendance.worker_id == worker.id,
        Attendance.date >= start_date,
        Attendance.date <= end_date
    ).all()

    present_count = 0.0
    absent_count = 0.0
    half_day_count = 0

    for r in records:
        if r.status == "P":
            present_count += 1.0
        elif r.status == "A":
            absent_count += 1.0
        elif r.status == "HD":
            present_count += 0.5
            absent_count += 0.5
            half_day_count += 1

    total_marked_days = len(records)

    # Exact Paid Leave Formula:
    # 1 day paid leave per month is allowed without salary deduction.
    if absent_count <= ALLOWED_PAID_LEAVES:
        paid_leaves_used = absent_count
        deductible_leave_days = 0.0
    else:
        paid_leaves_used = ALLOWED_PAID_LEAVES
        deductible_leave_days = absent_count - ALLOWED_PAID_LEAVES

    # Daily wage rate
    daily_wage = round(worker.monthly_salary / divisor_days, 2)

    # Salary deduction for unpaid leaves
    deduction_amount = round(deductible_leave_days * daily_wage, 2)

    # Query salary advances in this month
    advances = db.query(SalaryAdvance).filter(
        SalaryAdvance.worker_id == worker.id,
        SalaryAdvance.date >= start_date,
        SalaryAdvance.date <= end_date
    ).all()
    total_advances = round(sum(adv.amount for adv in advances), 2)

    # Net payable salary
    gross_salary = worker.monthly_salary
    salary_after_leaves = max(0.0, round(gross_salary - deduction_amount, 2))
    net_payable_salary = max(0.0, round(salary_after_leaves - total_advances, 2))

    # Determine status tag / rule explanation
    if absent_count == 0:
        rule_tag = "Full Salary (0 Leaves)"
        status_color = "success"
    elif absent_count <= 1:
        rule_tag = "Full Salary (1 Paid Leave Applied)"
        status_color = "info"
    elif absent_count == 2:
        rule_tag = "1 Day Reduced (2 Leaves)"
        status_color = "warning"
    else:
        rule_tag = f"{int(deductible_leave_days)} Days Reduced ({int(absent_count)} Leaves)"
        status_color = "danger"

    return {
        "worker_id": worker.id,
        "worker_name": worker.name,
        "phone": worker.phone,
        "role": worker.role,
        "monthly_salary": float(worker.monthly_salary),
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "days_in_month": days_in_month,
        "divisor_days": divisor_days,
        "total_marked_days": total_marked_days,
        "present_days": present_count,
        "absent_days": absent_count,
        "half_day_count": half_day_count,
        "allowed_paid_leaves": ALLOWED_PAID_LEAVES,
        "paid_leaves_used": paid_leaves_used,
        "deductible_leave_days": deductible_leave_days,
        "daily_wage": daily_wage,
        "deduction_amount": deduction_amount,
        "total_advances": total_advances,
        "net_payable_salary": net_payable_salary,
        "rule_tag": rule_tag,
        "status_color": status_color
    }


def calculate_monthly_payroll(
    year: int,
    month: int,
    db: Session,
    standard_30_days: bool = False
) -> Dict[str, Any]:
    """
    Calculates monthly payroll summary for all active workers.
    """
    workers = db.query(Worker).filter(Worker.active == True).order_by(Worker.id).all()
    worker_salaries = []

    total_gross = 0.0
    total_deductions = 0.0
    total_advances = 0.0
    total_net_payout = 0.0

    for idx, w in enumerate(workers, start=1):
        sal = calculate_worker_salary(w, year, month, db, standard_30_days=standard_30_days)
        sal["s_no"] = idx
        worker_salaries.append(sal)

        total_gross += sal["monthly_salary"]
        total_deductions += sal["deduction_amount"]
        total_advances += sal["total_advances"]
        total_net_payout += sal["net_payable_salary"]

    days_in_month = calendar.monthrange(year, month)[1]

    return {
        "year": year,
        "month": month,
        "month_name": calendar.month_name[month],
        "days_in_month": days_in_month,
        "workers_count": len(workers),
        "worker_salaries": worker_salaries,
        "total_gross_payroll": round(total_gross, 2),
        "total_leave_deductions": round(total_deductions, 2),
        "total_advances": round(total_advances, 2),
        "total_net_payroll": round(total_net_payout, 2)
    }
