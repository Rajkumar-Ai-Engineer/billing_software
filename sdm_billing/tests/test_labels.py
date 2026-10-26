import pytest
from services.labels import (
    build_tspl,
    build_zpl,
    build_epl,
    build_label_commands
)


def test_tspl_battery_label():
    label = {
        "type": "battery",
        "serial": "SDM0025",
        "battery_type": "LFP",
        "voltage": 48.0,
        "ah": 30.0
    }
    cmd = build_tspl(label, width_mm=50, height_mm=30, gap_mm=3, copies=2)
    assert "SIZE 50 mm, 30 mm" in cmd
    assert "GAP 3 mm, 0 mm" in cmd
    assert "DIRECTION 1" in cmd
    assert "CLS" in cmd
    assert "SDM0025" in cmd
    assert "LFP 48.0V 30.0Ah" in cmd
    assert 'BARCODE 20, 108, "128"' in cmd
    assert 'QRCODE 260, 20' in cmd
    assert "PRINT 2, 1" in cmd


def test_tspl_product_label():
    label = {
        "type": "product",
        "part_no": "SDM-MOT-250",
        "product_name": "EV Motor 250W",
        "cost_price": 5000.0,
        "show_price": True
    }
    cmd = build_tspl(label, width_mm=50, height_mm=30, gap_mm=3, copies=1)
    assert "SIZE 50 mm, 30 mm" in cmd
    assert "SDM-MOT-250" in cmd
    assert "EV Motor 250W" in cmd
    assert "MRP:" in cmd
    assert "PRINT 1, 1" in cmd


def test_zpl_label():
    label = {
        "type": "battery",
        "serial": "SDM0010",
        "battery_type": "Li-Ion",
        "voltage": 60.0,
        "ah": 24.0
    }
    cmd = build_zpl(label, width_mm=50, height_mm=30, copies=3)
    assert "^XA" in cmd
    assert "^PW400" in cmd  # 50mm * 8 dots
    assert "^LL240" in cmd  # 30mm * 8 dots
    assert "^FDSDM0010^FS" in cmd
    assert "^BCN,48,Y,N,N" in cmd
    assert "^BQN,2,4" in cmd
    assert "^PQ3" in cmd
    assert "^XZ" in cmd


def test_epl_label():
    label = {
        "type": "invoice",
        "invoice_no": "SDM/SP/2026/001"
    }
    cmd = build_epl(label, width_mm=50, height_mm=30, gap_mm=3, copies=1)
    assert "N" in cmd
    assert "q400" in cmd
    assert "Q240,24" in cmd
    assert "INV: SDM/SP/2026/001" in cmd
    assert 'B20,80,0,1,2,2,55,B,"SDM/SP/2026/001"' in cmd
    assert "P1" in cmd


def test_build_label_commands_dispatcher():
    item = {"type": "test"}
    tspl = build_label_commands(item, language="TSPL")
    assert "SIZE 50 mm, 30 mm" in tspl

    zpl = build_label_commands(item, language="ZPL")
    assert "^XA" in zpl

    epl = build_label_commands(item, language="EPL")
    assert "N" in epl


def test_labels_with_missing_or_none_fields():
    # Verify that None fields do not raise TypeError or crash
    null_label = {
        "type": "product",
        "part_no": None,
        "name": "Bulb",
        "product_name": None,
        "cost_price": None,
        "price": None,
        "show_price": False
    }
    tspl = build_label_commands(null_label, language="TSPL")
    assert "Bulb" in tspl
    assert "CLS" in tspl

    zpl = build_label_commands(null_label, language="ZPL")
    assert "^XA" in zpl

    epl = build_label_commands(null_label, language="EPL")
    assert "N" in epl


def test_labels_api_print_endpoint():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app)

    # Test printing with simulated printer
    res = client.post("/api/labels/print", json={
        "mode": "raw",
        "printer_name": "TVS LP 46 (Simulated)",
        "width_mm": 50,
        "height_mm": 30,
        "copies": 1,
        "items": [{
            "type": "product",
            "part_no": "A1",
            "name": "LED Bulb",
            "cost_price": 100.0,
            "price": 180.0,
            "show_price": False
        }]
    })
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True

    # Test printer settings endpoint
    res_printers = client.get("/api/labels/printers")
    assert res_printers.status_code == 200
    assert "printers" in res_printers.json()

    # Cleanup print log
    from database import SessionLocal
    from models import LabelPrintLog
    db = SessionLocal()
    db.query(LabelPrintLog).delete()
    db.commit()
    db.close()

