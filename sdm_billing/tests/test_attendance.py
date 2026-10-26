import pytest
from datetime import date
from fastapi.testclient import TestClient

from main import app
from database import SessionLocal, init_db
from models import Worker, Attendance, SalaryAdvance
from services.attendance_service import (
    seed_default_workers,
    save_daily_attendance,
    get_daily_attendance_register,
    calculate_worker_salary,
    calculate_monthly_payroll,
    ALLOWED_PAID_LEAVES
)


@pytest.fixture(scope="module")
def client():
    init_db()
    with TestClient(app) as c:
        yield c
    db = SessionLocal()
    db.query(Attendance).delete()
    db.query(SalaryAdvance).delete()
    db.commit()
    db.close()


@pytest.fixture
def db():
    init_db()
    session = SessionLocal()
    def cleanup():
        test_workers = session.query(Worker).filter(Worker.name.like("Test %")).all()
        w_ids = [w.id for w in test_workers]
        if w_ids:
            session.query(Attendance).filter(Attendance.worker_id.in_(w_ids)).delete(synchronize_session=False)
            session.query(SalaryAdvance).filter(SalaryAdvance.worker_id.in_(w_ids)).delete(synchronize_session=False)
            session.query(Worker).filter(Worker.id.in_(w_ids)).delete(synchronize_session=False)
        session.query(Attendance).filter(Attendance.date == date(2026, 10, 8)).delete(synchronize_session=False)
        session.commit()
    cleanup()
    try:
        yield session
    finally:
        cleanup()
        session.close()


def test_seed_workers(db):
    workers = seed_default_workers(db)
    assert len(workers) >= 2
    names = [w.name for w in workers]
    assert any("A1" in n for n in names)
    assert any("A2" in n for n in names)


def test_daily_attendance_save_and_retrieve(db):
    workers = seed_default_workers(db)
    w1 = workers[0]
    w2 = workers[1]

    target_date = date(2026, 10, 8)
    records = [
        {"worker_id": w1.id, "status": "P", "notes": "On time"},
        {"worker_id": w2.id, "status": "A", "notes": "Medical leave"}
    ]
    saved = save_daily_attendance(target_date, records, db)
    assert len(saved) == 2

    # Retrieve
    reg = get_daily_attendance_register(target_date, db)
    reg_map = {r["worker_id"]: r for r in reg}
    assert reg_map[w1.id]["status"] == "P"
    assert reg_map[w2.id]["status"] == "A"
    assert reg_map[w2.id]["notes"] == "Medical leave"


def test_salary_rule_a1_present_30_days_salary_is_same(db):
    """
    User Note Spec: 'A1 as Present in 30 Days but the Salary is Same OK'
    0 Leaves => Full monthly salary.
    """
    worker = Worker(name="Test A1", monthly_salary=30000.0, role="Mechanic", active=True)
    db.add(worker)
    db.commit()
    db.refresh(worker)

    # Mark 30 days present in April (30 days month)
    year, month = 2026, 4
    records = []
    for day in range(1, 31):
        records.append(Attendance(
            worker_id=worker.id,
            date=date(year, month, day),
            day_name="Weekday",
            status="P"
        ))
    db.add_all(records)
    db.commit()

    sal = calculate_worker_salary(worker, year, month, db)
    assert sal["present_days"] == 30.0
    assert sal["absent_days"] == 0.0
    assert sal["deductible_leave_days"] == 0.0
    assert sal["deduction_amount"] == 0.0
    assert sal["net_payable_salary"] == 30000.0
    assert "Full Salary" in sal["rule_tag"]


def test_salary_rule_a2_present_29_days_1_leave_salary_is_same(db):
    """
    User Note Spec: 'in ther as oneday for worker an Pay with Leave
    (ex: A2 as Present in 29 Days Salary is Same)'
    1 Leave => Paid leave applied, 0 deduction => Full monthly salary.
    """
    worker = Worker(name="Test A2", monthly_salary=30000.0, role="Mechanic", active=True)
    db.add(worker)
    db.commit()
    db.refresh(worker)

    # Mark 29 days present, 1 day absent in April
    year, month = 2026, 4
    records = []
    for day in range(1, 30):
        records.append(Attendance(
            worker_id=worker.id,
            date=date(year, month, day),
            day_name="Weekday",
            status="P"
        ))
    records.append(Attendance(
        worker_id=worker.id,
        date=date(year, month, 30),
        day_name="Weekday",
        status="A"
    ))
    db.add_all(records)
    db.commit()

    sal = calculate_worker_salary(worker, year, month, db)
    assert sal["present_days"] == 29.0
    assert sal["absent_days"] == 1.0
    assert sal["paid_leaves_used"] == 1.0
    assert sal["deductible_leave_days"] == 0.0
    assert sal["deduction_amount"] == 0.0
    assert sal["net_payable_salary"] == 30000.0
    assert "1 Paid Leave Applied" in sal["rule_tag"]


def test_salary_rule_2_days_leave_reduces_1_day_salary(db):
    """
    User Note Spec: 'when the worker as take 2 Days Leave it will be Reduce 1 Day Salary OK'
    2 Leaves => 1 day paid leave, 1 day deducted => Salary reduced by 1 day wage!
    """
    worker = Worker(name="Test A3", monthly_salary=30000.0, role="Mechanic", active=True)
    db.add(worker)
    db.commit()
    db.refresh(worker)

    # 30 days in April => Daily rate = 30000 / 30 = 1000.0
    year, month = 2026, 4
    records = []
    for day in range(1, 29):
        records.append(Attendance(
            worker_id=worker.id,
            date=date(year, month, day),
            day_name="Weekday",
            status="P"
        ))
    # 2 days absent
    records.append(Attendance(worker_id=worker.id, date=date(year, month, 29), day_name="Weekday", status="A"))
    records.append(Attendance(worker_id=worker.id, date=date(year, month, 30), day_name="Weekday", status="A"))
    db.add_all(records)
    db.commit()

    sal = calculate_worker_salary(worker, year, month, db)
    assert sal["present_days"] == 28.0
    assert sal["absent_days"] == 2.0
    assert sal["paid_leaves_used"] == 1.0
    assert sal["deductible_leave_days"] == 1.0
    assert sal["daily_wage"] == 1000.0
    assert sal["deduction_amount"] == 1000.0
    # Net salary reduced by exactly 1 day salary (30000 - 1000 = 29000)
    assert sal["net_payable_salary"] == 29000.0
    assert "1 Day Reduced" in sal["rule_tag"]


def test_salary_rule_3_days_leave_reduces_2_days_salary(db):
    """
    3 Leaves => 1 day paid leave, 2 days deducted.
    """
    worker = Worker(name="Test A4", monthly_salary=30000.0, role="Mechanic", active=True)
    db.add(worker)
    db.commit()
    db.refresh(worker)

    year, month = 2026, 4
    records = []
    for day in range(1, 28):
        records.append(Attendance(worker_id=worker.id, date=date(year, month, day), day_name="Weekday", status="P"))
    # 3 days absent
    for day in [28, 29, 30]:
        records.append(Attendance(worker_id=worker.id, date=date(year, month, day), day_name="Weekday", status="A"))
    db.add_all(records)
    db.commit()

    sal = calculate_worker_salary(worker, year, month, db)
    assert sal["absent_days"] == 3.0
    assert sal["deductible_leave_days"] == 2.0
    assert sal["daily_wage"] == 1000.0
    assert sal["deduction_amount"] == 2000.0
    assert sal["net_payable_salary"] == 28000.0


def test_advance_deduction(db):
    worker = Worker(name="Test Advance", monthly_salary=20000.0, role="Helper", active=True)
    db.add(worker)
    db.commit()
    db.refresh(worker)

    # 1 advance of 2000 in April
    adv = SalaryAdvance(worker_id=worker.id, date=date(2026, 4, 15), amount=2000.0, notes="Emergency")
    db.add(adv)
    db.commit()

    sal = calculate_worker_salary(worker, 2026, 4, db)
    assert sal["total_advances"] == 2000.0
    assert sal["net_payable_salary"] == 18000.0


def test_api_attendance_endpoints(client):
    # GET /attendance page
    res = client.get("/attendance")
    assert res.status_code == 200
    assert "Worker Attendance" in res.text
    assert "Daily Attendance Register" in res.text

    # POST /api/attendance/daily
    post_res = client.post("/api/attendance/daily", json={
        "date": "2026-10-08",
        "records": [
            {"worker_id": 1, "status": "P", "notes": "Test Note"}
        ]
    })
    assert post_res.status_code == 200
    assert post_res.json()["success"] is True

    # GET /api/attendance/daily
    get_res = client.get("/api/attendance/daily?date_str=2026-10-08")
    assert get_res.status_code == 200
    assert len(get_res.json()["records"]) > 0

    # GET /api/attendance/payroll
    pay_res = client.get("/api/attendance/payroll?year=2026&month=10")
    assert pay_res.status_code == 200
    data = pay_res.json()
    assert "total_net_payroll" in data
    assert "worker_salaries" in data

    # GET /api/attendance/export
    exp_res = client.get("/api/attendance/export?year=2026&month=10")
    assert exp_res.status_code == 200
    assert "text/csv" in exp_res.headers["content-type"]
    assert b"Worker Name" in exp_res.content

    # GET /attendance/pay-slip/1
    slip_res = client.get("/attendance/pay-slip/1?year=2026&month=10")
    assert slip_res.status_code == 200
    assert "PAY SLIP" in slip_res.text
