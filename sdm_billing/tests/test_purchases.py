import pytest
from datetime import date
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import PurchaseInvoice


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    # Cleanup any test created purchase invoices
    db = SessionLocal()
    db.query(PurchaseInvoice).filter(
        (PurchaseInvoice.invoice_no == "GST-PUR-2026-0042") |
        (PurchaseInvoice.invoice_no == "SUP-B-9901") |
        (PurchaseInvoice.invoice_no.like("TEMP-PUR%"))
    ).delete(synchronize_session=False)
    db.commit()
    db.close()


def test_purchases_page_render(client):
    r = client.get("/purchases")
    assert r.status_code == 200
    assert "Inward Purchases & Bulk GST Bills" in r.text
    assert "Invoice / Bill Number" in r.text
    assert "Total Number of Quantity" in r.text


def test_create_purchase_full(client):
    payload = {
        "invoice_no": "GST-PUR-2026-0042",
        "received_date": str(date.today()),
        "price": 185000.0,
        "total_qty": 50,
        "notes": "Bulk EV Scooter Spares & Hub Motors"
    }
    r = client.post("/api/purchases", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["invoice_no"] == "GST-PUR-2026-0042"
    assert data["price"] == 185000.0
    assert data["total_qty"] == 50
    assert data["received_date"] == str(date.today())


def test_create_purchase_default_date(client):
    payload = {
        "invoice_no": "SUP-B-9901",
        "price": 42000.0,
        "total_qty": 20
    }
    r = client.post("/api/purchases", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["invoice_no"] == "SUP-B-9901"
    assert data["received_date"] == str(date.today())


def test_create_purchase_validation(client):
    # Empty invoice_no
    payload = {
        "invoice_no": "",
        "price": 1000.0,
        "total_qty": 5
    }
    r = client.post("/api/purchases", json=payload)
    assert r.status_code in (400, 422)


def test_list_and_delete_purchase(client):
    r = client.post("/api/purchases", json={
        "invoice_no": "TEMP-PUR-DEL-01",
        "price": 5000.0,
        "total_qty": 10
    })
    assert r.status_code == 200
    pur_id = r.json()["id"]

    # Search
    r_list = client.get("/api/purchases?q=TEMP-PUR-DEL")
    assert r_list.status_code == 200
    assert any(p["id"] == pur_id for p in r_list.json())

    # Delete
    r_del = client.delete(f"/api/purchases/{pur_id}")
    assert r_del.status_code == 200
    assert r_del.json()["success"] is True

    # 404 test
    r_del_404 = client.delete("/api/purchases/99999999")
    assert r_del_404.status_code == 404


def test_export_purchases_csv(client):
    r = client.get("/api/purchases/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "Invoice / Bill No" in r.text
