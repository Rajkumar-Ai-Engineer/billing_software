import pytest
from datetime import date
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import DailyExpense


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    # Cleanup any test created expenses
    db = SessionLocal()
    db.query(DailyExpense).filter(
        (DailyExpense.bill_no == "BILL-1001") |
        (DailyExpense.product_name.like("%Staff%")) |
        (DailyExpense.product_name.like("%Delete Item%"))
    ).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_expenses_page_render(client):
    r = client.get("/expenses")
    assert r.status_code == 200
    assert "Daily Expenses Tracker" in r.text
    assert "Bill Number" in r.text
    assert "Product / Description" in r.text


def test_create_expense_full(client):
    payload = {
        "date": str(date.today()),
        "bill_no": "BILL-1001",
        "product_name": "Shop Cleaning Liquid & Broom",
        "price": 250.0,
        "notes": "Paid by cash"
    }
    r = client.post("/api/expenses", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["bill_no"] == "BILL-1001"
    assert data["product_name"] == "Shop Cleaning Liquid & Broom"
    assert data["price"] == 250.0


def test_create_expense_without_bill_no(client):
    # Requirements specify bill number is strictly non-compulsory
    payload = {
        "product_name": "Tea & Evening Snacks for Staff",
        "price": 120.0
    }
    r = client.post("/api/expenses", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["bill_no"] == ""
    assert data["product_name"] == "Tea & Evening Snacks for Staff"
    assert data["price"] == 120.0
    assert data["date"] == str(date.today())  # auto-default to today


def test_create_expense_validation(client):
    # Completely empty entry without product, bill or price should be rejected
    payload = {
        "date": str(date.today()),
        "bill_no": "",
        "product_name": "",
        "price": 0.0
    }
    r = client.post("/api/expenses", json=payload)
    assert r.status_code == 400


def test_list_and_delete_expense(client):
    # Create an expense
    r = client.post("/api/expenses", json={"product_name": "Test Delete Item", "price": 45.0})
    assert r.status_code == 200
    exp_id = r.json()["id"]

    # Verify in list
    r_list = client.get("/api/expenses?q=Test+Delete")
    assert r_list.status_code == 200
    items = r_list.json()
    assert any(item["id"] == exp_id for item in items)

    # Delete
    r_del = client.delete(f"/api/expenses/{exp_id}")
    assert r_del.status_code == 200
    assert r_del.json()["success"] is True

    # Check 404 on deleting non-existent
    r_del_404 = client.delete("/api/expenses/99999999")
    assert r_del_404.status_code == 404


def test_export_expenses_csv(client):
    r = client.get("/api/expenses/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "Product / Description" in r.text
