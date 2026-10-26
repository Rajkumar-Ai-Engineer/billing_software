import pytest
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import Product, Invoice, Battery


@pytest.fixture(scope="module")
def client():
    db = SessionLocal()
    baseline_stocks = {p.part_no: p.stock_qty for p in db.query(Product).filter(Product.part_no.in_(["A1", "S1", "ALFA-R1"])).all()}
    db.close()

    with TestClient(app) as c:
        yield c

    db = SessionLocal()
    for part, qty in baseline_stocks.items():
        p = db.query(Product).filter(Product.part_no == part).first()
        if p:
            p.stock_qty = qty
    from models import StockMovement, LabelPrintLog
    db.query(StockMovement).delete()
    db.query(LabelPrintLog).delete()
    db.commit()
    from services.excel_sync import sync_products_to_excel_files
    sync_products_to_excel_files(db)
    db.close()


def test_homepage_and_routes(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Sri Dhanam Motors" in r.text

    r = client.get("/spare-bill")
    assert r.status_code == 200
    assert "Spare Bill" in r.text

    r = client.get("/service-bill")
    assert r.status_code == 200
    assert "Service Bill" in r.text

    r = client.get("/vehicle-bill")
    assert r.status_code == 200
    assert "Vehicle Bill" in r.text

    r = client.get("/battery-qr")
    assert r.status_code == 200
    assert "Battery Serial" in r.text

    r = client.get("/products")
    assert r.status_code == 200
    assert "Product & Stock" in r.text

    r = client.get("/printer-settings")
    assert r.status_code == 200
    assert "TVS-E LP 46" in r.text


def test_api_dashboard(client):
    r = client.get("/api/dashboard?period=daily")
    assert r.status_code == 200
    data = r.json()
    assert "total_sales" in data
    assert "categories" in data
    assert "chart" in data


def test_battery_generation_api(client):
    payload = {
        "type": "LFP",
        "voltage": 48.0,
        "ah": 30.0,
        "create_product": True
    }
    r = client.post("/api/batteries/generate", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["serial"].startswith("SDM")
    assert len(data["qr_base64"]) > 50
    assert len(data["barcode_base64"]) > 50

    # Clean up test battery and created product
    serial = data["serial"]
    db = SessionLocal()
    db.query(Battery).filter(Battery.serial == serial).delete()
    db.query(Product).filter(Product.part_no == serial).delete()
    db.commit()
    db.close()


def test_products_list_api(client):
    r = client.get("/api/products")
    assert r.status_code == 200
    products = r.json()
    assert isinstance(products, list)
    assert len(products) > 0


def test_quick_add_stock_and_excel_sync(client):
    # Check products page has the ➕ Add button and modal
    r_page = client.get("/products")
    assert r_page.status_code == 200
    assert "➕ Add" in r_page.text
    assert "quick-add-modal" in r_page.text

    # Test quick add API
    payload = {
        "part_no": "A1",
        "change": 5,
        "reason": "Test Quick Add"
    }
    r = client.post("/api/products/quick-add", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["added"] == 5

    # Check that Excel/CSV file was updated
    import pandas as pd
    import config
    csv_file = config.DATA_DIR / "products_master.csv"
    assert csv_file.exists()
    df = pd.read_csv(csv_file)
    row = df[df["Part No"] == "A1"]
    assert not row.empty
    assert int(row["Stock Qty"].values[0]) == data["stock_qty"]

    excel_file = config.DATA_DIR / "products_master.xlsx"
    assert excel_file.exists()


def test_quick_reduce_stock_and_excel_sync(client):
    # Check products page has the ➖ Reduce button and modal
    r_page = client.get("/products")
    assert r_page.status_code == 200
    assert "➖ Reduce" in r_page.text
    assert "quick-reduce-modal" in r_page.text

    # First add some stock to ensure A1 has enough
    client.post("/api/products/quick-add", json={"part_no": "A1", "change": 10, "reason": "Pre-stock"})
    r_pre = client.get("/api/products?q=A1")
    initial_stock = [p for p in r_pre.json() if p["part_no"] == "A1"][0]["stock_qty"]

    # Test quick reduce API
    payload = {
        "part_no": "A1",
        "change": 3,
        "reason": "Test Quick Reduce"
    }
    r = client.post("/api/products/quick-reduce", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["reduced"] == 3
    assert data["stock_qty"] == initial_stock - 3

    # Check that Excel/CSV file was updated
    import pandas as pd
    import config
    csv_file = config.DATA_DIR / "products_master.csv"
    assert csv_file.exists()
    df = pd.read_csv(csv_file)
    row = df[df["Part No"] == "A1"]
    assert not row.empty
    assert int(row["Stock Qty"].values[0]) == data["stock_qty"]

    # Test reduce exceeding stock returns 400
    r_err = client.post("/api/products/quick-reduce", json={"part_no": "A1", "change": 99999})
    assert r_err.status_code == 400
    assert "Available stock is only" in r_err.json()["detail"]

    # Test reduce zero or negative returns 400
    r_zero = client.post("/api/products/quick-reduce", json={"part_no": "A1", "change": 0})
    assert r_zero.status_code == 400


def test_stock_adjust_modal_updates_price_without_reason(client):
    # Verify HTML template: Reason/Note is removed, Price is added
    r_page = client.get("/products")
    assert r_page.status_code == 200
    assert "adj-price" in r_page.text
    assert "adj-reason" not in r_page.text

    # Adjust stock without providing reason, providing price
    payload = {
        "part_no": "A1",
        "change": 2,
        "price": 1050.0
    }
    r = client.post("/api/products/stock-adjust", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["cost_price"] == 1050.0

    # Reset A1
    client.post("/api/products/stock-adjust", json={"part_no": "A1", "change": -2, "price": 1000.0})


def test_create_product_and_excel_sync(client):
    unique_part = "SDM-TEST-EXCEL"
    # Ensure it doesn't already exist
    client.delete(f"/api/products/{unique_part}")

    payload = {
        "part_no": unique_part,
        "name": "Excel Sync Test Product",
        "category": "Spare Parts",
        "hsn": "8507",
        "cost_price": 1200.0,
        "gst_percent": 18.0,
        "stock_qty": 15
    }
    r = client.post("/api/products", json=payload)
    assert r.status_code == 200
    assert r.json()["success"] is True

    # Check Excel file now contains the new product
    import pandas as pd
    import config
    df = pd.read_excel(config.DATA_DIR / "products_master.xlsx")
    assert unique_part in df["Part No"].values

    # Clean up test product
    client.delete(f"/api/products/{unique_part}")


def test_print_invoice_with_slashes(client):
    db = SessionLocal()
    inv = db.query(Invoice).filter(Invoice.invoice_no == "SDM/SP/2026/001").first()
    created_here = False
    if not inv:
        inv = Invoice(
            invoice_no="SDM/SP/2026/001",
            category="Spare Parts",
            customer_name="Test Customer",
            mobile="9876543210",
            address="Harur",
            base_total=1000.0,
            gst_amount=180.0,
            grand_total=1180.0
        )
        db.add(inv)
        db.commit()
        created_here = True
    db.close()

    try:
        # Test path with unencoded slashes
        r1 = client.get("/invoice/SDM/SP/2026/001/print")
        assert r1.status_code == 200
        assert "SDM/SP/2026/001" in r1.text

        # Test path with encoded slashes
        r2 = client.get("/invoice/SDM%2FSP%2F2026%2F001/print")
        assert r2.status_code == 200
        assert "SDM/SP/2026/001" in r2.text
    finally:
        if created_here:
            db = SessionLocal()
            db.query(Invoice).filter(Invoice.invoice_no == "SDM/SP/2026/001").delete()
            db.commit()
            db.close()


def test_print_invoice_serial_format(client):
    db = SessionLocal()
    inv = db.query(Invoice).filter(Invoice.invoice_no == "SDM0001").first()
    created_here = False
    if not inv:
        inv = Invoice(
            invoice_no="SDM0001",
            category="Spare Parts",
            customer_name="Test Customer",
            mobile="9876543210",
            address="Harur",
            base_total=1000.0,
            gst_amount=180.0,
            grand_total=1180.0
        )
        db.add(inv)
        db.commit()
        created_here = True
    db.close()

    try:
        r = client.get("/invoice/SDM0001/print")
        assert r.status_code == 200
        assert "S:No:" in r.text
        assert "SDM0001" in r.text
        assert "Doc No:" not in r.text
        assert "Signature" in r.text
        assert "Authorized" not in r.text
        assert "For SRI DHANAM MOTORS" not in r.text
    finally:
        if created_here:
            db = SessionLocal()
            db.query(Invoice).filter(Invoice.invoice_no == "SDM0001").delete()
            db.commit()
            db.close()


def test_print_estimate_with_items(client):
    payload = {
        "category": "Spare Parts",
        "customer_name": "Test Customer",
        "mobile": "9876543210",
        "address": "Harur",
        "gstin": "",
        "invoice_no": "ESTIMATE-1234",
        "items": [
            {
                "part_no": "SDM-MOT-250",
                "product_name": "EV Motor 250W",
                "price": 9000.0,
                "unit_price": 9000.0,
                "qty": 2,
                "subtotal": 18000.0,
                "gst_percent": 18.0,
                "gst_amount": 3240.0,
                "total": 21240.0
            }
        ],
        "totals": {
            "base_total": 18000.0,
            "gst_amount": 3240.0,
            "grand_total": 21240.0
        }
    }
    r = client.post("/estimate/print", json=payload)
    assert r.status_code == 200
    assert "ESTIMATE" in r.text
    assert "QUOTE" not in r.text
    assert "Signature" in r.text
    assert "Authorized" not in r.text
    assert "EV Motor 250W" in r.text
    assert "Test Customer" in r.text


def test_vehicle_bill_page_ui(client):
    r = client.get("/vehicle-bill")
    assert r.status_code == 200
    assert "Profit Margin (%)" in r.text
    assert 'id="vehicle-profit-margin"' in r.text
    assert "Pricing Level" not in r.text
    assert '<select id="gst-mode"' not in r.text
    assert 'id="gst-mode" value="With GST (Tax Invoice)"' in r.text
    assert 'id="vehicle-type-select"' not in r.text
    assert "Vehicle Type" not in r.text


def test_vehicle_billing_margin_api(client):
    # Default 15% margin on vehicle products
    r1 = client.get("/api/billing/products?category=Vehicle Sales")
    assert r1.status_code == 200
    alfa_default = next(p for p in r1.json() if p["part_no"] == "ALFA-R1")
    # Cost 75000 + 15% = 86250.0
    assert alfa_default["selling_price"] == 86250.0

    # Custom 20% margin on vehicle products
    r2 = client.get("/api/billing/products?category=Vehicle Sales&margin_percent=20")
    assert r2.status_code == 200
    alfa_custom = next(p for p in r2.json() if p["part_no"] == "ALFA-R1")
    # Cost 75000 + 20% = 90000.0
    assert alfa_custom["selling_price"] == 90000.0

    # Test calculate endpoint with 15% margin
    calc_15 = client.post("/api/billing/calculate", json={
        "category": "Vehicle Sales",
        "margin_percent": 15.0,
        "items": [{
            "part_no": "ALFA-R1",
            "product_name": "ALFA R1",
            "cost_price": 75000.0,
            "gst_percent": 5.0,
            "qty": 1
        }]
    })
    assert calc_15.status_code == 200
    data_15 = calc_15.json()
    assert data_15["items"][0]["unit_price"] == 86250.0
    assert data_15["totals"]["base_total"] == 86250.0
    assert data_15["totals"]["gst_amount"] == 4312.50
    assert data_15["totals"]["grand_total"] == 90562.50

    # Test calculate endpoint with custom 20% margin
    calc_20 = client.post("/api/billing/calculate", json={
        "category": "Vehicle Sales",
        "margin_percent": 20.0,
        "items": [{
            "part_no": "ALFA-R1",
            "product_name": "ALFA R1",
            "cost_price": 75000.0,
            "gst_percent": 5.0,
            "qty": 1
        }]
    })
    assert calc_20.status_code == 200
    data_20 = calc_20.json()
    assert data_20["items"][0]["unit_price"] == 90000.0
    assert data_20["totals"]["base_total"] == 90000.0
    assert data_20["totals"]["gst_amount"] == 4500.0
    assert data_20["totals"]["grand_total"] == 94500.0


def test_vehicle_billing_save_with_margin(client):
    db = SessionLocal()
    p = db.query(Product).filter(Product.part_no == "ALFA-R1").first()
    orig_stock = p.stock_qty if p else 10
    if p:
        p.stock_qty = 10
        db.commit()
    db.close()

    save_payload = {
        "category": "Vehicle Sales",
        "buyer_type": "Customer",
        "gst_mode": "With GST (Tax Invoice)",
        "margin_percent": 15.0,
        "customer_name": "Vehicle Buyer",
        "mobile": "9876543210",
        "address": "Salem Main Road",
        "gstin": "",
        "items": [{
            "part_no": "ALFA-R1",
            "product_name": "ALFA R1",
            "price": 86250.0,
            "qty": 1,
            "subtotal": 86250.0,
            "gst_percent": 5.0,
            "gst_amount": 4312.50,
            "total": 90562.50
        }]
    }
    r = client.post("/api/billing/save", json=save_payload)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["grand_total"] == 90562.50

    # Clean up test invoice and restore stock
    inv_no = data["invoice_no"]
    db = SessionLocal()
    inv = db.query(Invoice).filter(Invoice.invoice_no == inv_no).first()
    if inv:
        db.delete(inv)
    from models import StockMovement
    db.query(StockMovement).filter(StockMovement.ref == inv_no).delete()
    p = db.query(Product).filter(Product.part_no == "ALFA-R1").first()
    if p:
        p.stock_qty = orig_stock
    db.commit()
    db.close()


def test_service_bill_page_ui(client):
    # Service Bill should NOT have Pricing Level or GST Mode dropdown
    r_serv = client.get("/service-bill")
    assert r_serv.status_code == 200
    assert "Pricing Level" not in r_serv.text
    assert '<select id="gst-mode"' not in r_serv.text
    assert 'id="gst-mode" value="With GST (Tax Invoice)"' in r_serv.text
    assert 'name="buyer_type" value="Customer"' in r_serv.text

    # Spare Bill should still have Pricing Level and GST Mode
    r_spare = client.get("/spare-bill")
    assert r_spare.status_code == 200
    assert "Pricing Level" in r_spare.text
    assert '<select id="gst-mode"' in r_spare.text


def test_service_billing_save(client):
    db = SessionLocal()
    p = db.query(Product).filter(Product.part_no == "S1").first()
    orig_stock = p.stock_qty if p else 10
    if p:
        p.stock_qty = 10
        db.commit()
    db.close()

    payload = {
        "category": "Service",
        "buyer_type": "Customer",
        "gst_mode": "With GST (Tax Invoice)",
        "customer_name": "Service Customer",
        "mobile": "9876543210",
        "address": "Harur",
        "gstin": "",
        "items": [{
            "part_no": "S1",
            "product_name": "General EV Service & Checkup",
            "price": 900.0,
            "qty": 1,
            "subtotal": 900.0,
            "gst_percent": 18.0,
            "gst_amount": 162.0,
            "total": 1062.0
        }]
    }
    r = client.post("/api/billing/save", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["success"] is True
    assert data["grand_total"] == 1062.0

    # Clean up test invoice and restore stock
    inv_no = data["invoice_no"]
    db = SessionLocal()
    inv = db.query(Invoice).filter(Invoice.invoice_no == inv_no).first()
    if inv:
        db.delete(inv)
    from models import StockMovement
    db.query(StockMovement).filter(StockMovement.ref == inv_no).delete()
    p = db.query(Product).filter(Product.part_no == "S1").first()
    if p:
        p.stock_qty = orig_stock
    db.commit()
    db.close()


def test_tick_case_billing_pages_ui(client):
    # 1. Spare Bill
    r_spare = client.get("/spare-bill")
    assert r_spare.status_code == 200
    assert "catalog-card" in r_spare.text
    assert "catalog-table" in r_spare.text
    assert "Tick (☑)" in r_spare.text
    assert "Add to Cart" not in r_spare.text

    # 2. Service Bill
    r_service = client.get("/service-bill")
    assert r_service.status_code == 200
    assert "catalog-card" in r_service.text
    assert "catalog-table" in r_service.text
    assert "Tick (☑)" in r_service.text
    assert "Add to Cart" not in r_service.text

    # 3. Vehicle Bill
    r_vehicle = client.get("/vehicle-bill")
    assert r_vehicle.status_code == 200
    assert "catalog-card" in r_vehicle.text
    assert "catalog-table" in r_vehicle.text
    assert "Tick (☑)" in r_vehicle.text
    assert "Add to Cart" not in r_vehicle.text
    assert "Add Vehicle" not in r_vehicle.text


def test_billing_cross_category_products_api(client):
    # Verify All returns products across Spare Parts, Vehicle Sales, and Service
    r_all = client.get("/api/billing/products?category=All")
    assert r_all.status_code == 200
    all_prods = r_all.json()
    assert len(all_prods) > 0
    categories = {p["category"] for p in all_prods}
    assert "Spare Parts" in categories
    assert "Vehicle Sales" in categories

    # Verify specific category filters
    r_spare = client.get("/api/billing/products?category=Spare Parts")
    assert r_spare.status_code == 200
    assert all(p["category"] == "Spare Parts" for p in r_spare.json())

    r_veh = client.get("/api/billing/products?category=Vehicle Sales")
    assert r_veh.status_code == 200
    assert all(p["category"] == "Vehicle Sales" for p in r_veh.json())


def test_billing_pages_category_filter_pills_ui(client):
    # 1. Spare Bill: only Spare Parts pill; NO Service or Vehicle Sales pills
    r_spare = client.get("/spare-bill")
    assert r_spare.status_code == 200
    assert "catalog-category-pills-bar" in r_spare.text
    assert 'data-cat="Spare Parts"' in r_spare.text
    assert 'data-cat="Service"' not in r_spare.text
    assert 'data-cat="Vehicle Sales"' not in r_spare.text
    assert "Quick search spare parts" in r_spare.text

    # 2. Service Bill: Service and Spare Parts pills; NO Vehicle Sales pill
    r_service = client.get("/service-bill")
    assert r_service.status_code == 200
    assert "catalog-category-pills-bar" in r_service.text
    assert 'data-cat="Service"' in r_service.text
    assert 'data-cat="Spare Parts"' in r_service.text
    assert 'data-cat="Vehicle Sales"' not in r_service.text
    assert "Quick search service & spare parts" in r_service.text

    # 3. Vehicle Bill: Vehicle Sales and Spare Parts pills; NO Service pill
    r_vehicle = client.get("/vehicle-bill")
    assert r_vehicle.status_code == 200
    assert "catalog-category-pills-bar" in r_vehicle.text
    assert 'data-cat="Vehicle Sales"' in r_vehicle.text
    assert 'data-cat="Spare Parts"' in r_vehicle.text
    assert 'data-cat="Service"' not in r_vehicle.text
    assert "Quick search vehicle or spare part name" in r_vehicle.text


def test_billing_products_by_bill_category_api(client):
    # Spare Bill: only Spare Parts
    r_sp = client.get("/api/billing/products?bill_category=Spare Parts")
    assert r_sp.status_code == 200
    sp_items = r_sp.json()
    assert len(sp_items) > 0
    assert all(p["category"] == "Spare Parts" for p in sp_items)

    # Service Bill: Service + Spare Parts, NO Vehicle Sales
    r_serv = client.get("/api/billing/products?bill_category=Service")
    assert r_serv.status_code == 200
    serv_items = r_serv.json()
    assert len(serv_items) > 0
    assert not any(p["category"] == "Vehicle Sales" for p in serv_items)

    # Vehicle Bill: Vehicle Sales + Spare Parts, NO Service
    r_veh = client.get("/api/billing/products?bill_category=Vehicle Sales")
    assert r_veh.status_code == 200
    veh_items = r_veh.json()
    assert len(veh_items) > 0
    assert not any(p["category"] == "Service" for p in veh_items)


def test_invoice_save_category_compatibility_validation(client):
    # Attempting to save a Service item on a Spare Parts bill must fail
    bad_spare = {
        "category": "Spare Parts",
        "buyer_type": "Customer",
        "gst_mode": "With GST (Tax Invoice)",
        "customer_name": "Test Cust",
        "mobile": "9876543210",
        "items": [{
            "part_no": "S1",
            "product_name": "General EV Service & Checkup",
            "price": 900.0,
            "qty": 1,
            "subtotal": 900.0,
            "gst_percent": 18.0,
            "gst_amount": 162.0,
            "total": 1062.0
        }]
    }
    r1 = client.post("/api/billing/save", json=bad_spare)
    assert r1.status_code == 400
    assert "Spare Bills can only contain Spare Parts" in r1.json()["detail"]

    # Attempting to save a Vehicle Sales item on a Service bill must fail
    bad_service = {
        "category": "Service",
        "buyer_type": "Customer",
        "gst_mode": "With GST (Tax Invoice)",
        "customer_name": "Test Cust",
        "mobile": "9876543210",
        "items": [{
            "part_no": "ALFA-R1",
            "product_name": "ALFA R1",
            "price": 86250.0,
            "qty": 1,
            "subtotal": 86250.0,
            "gst_percent": 5.0,
            "gst_amount": 4312.50,
            "total": 90562.50
        }]
    }
    r2 = client.post("/api/billing/save", json=bad_service)
    assert r2.status_code == 400
    assert "Cannot add" in r2.json()["detail"] and "Service Bill" in r2.json()["detail"]

    # Attempting to save a Service item on a Vehicle bill must fail
    bad_vehicle = {
        "category": "Vehicle Sales",
        "buyer_type": "Customer",
        "gst_mode": "With GST (Tax Invoice)",
        "margin_percent": 15.0,
        "customer_name": "Test Cust",
        "mobile": "9876543210",
        "items": [{
            "part_no": "S1",
            "product_name": "General EV Service & Checkup",
            "price": 900.0,
            "qty": 1,
            "subtotal": 900.0,
            "gst_percent": 18.0,
            "gst_amount": 162.0,
            "total": 1062.0
        }]
    }
    r3 = client.post("/api/billing/save", json=bad_vehicle)
    assert r3.status_code == 400
    assert "Cannot add" in r3.json()["detail"] and "Vehicle Bill" in r3.json()["detail"]


def test_cross_category_bill_calculation_and_save(client):
    # Restock a spare part and service item
    client.post("/api/products/quick-add", json={"part_no": "A1", "change": 10, "reason": "Restock"})

    calc_payload = {
        "items": [
            {"part_no": "A1", "product_name": "Spare Part A1", "cost_price": 500.0, "qty": 1, "gst_percent": 18.0, "category": "Spare Parts"},
            {"part_no": "SDM-VEH-01", "product_name": "EV Scooter", "cost_price": 50000.0, "qty": 1, "gst_percent": 5.0, "category": "Vehicle Sales"}
        ],
        "buyer_type": "Customer",
        "gst_mode": "With GST (Tax Invoice)"
    }
    r_calc = client.post("/api/billing/calculate", json=calc_payload)
    assert r_calc.status_code == 200
    data = r_calc.json()
    assert len(data["items"]) == 2
    assert data["totals"]["grand_total"] > 0




