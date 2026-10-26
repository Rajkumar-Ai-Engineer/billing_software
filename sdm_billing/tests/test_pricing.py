import pytest
from services.pricing import (
    calculate_selling_price,
    calculate_line_item,
    calculate_totals,
    format_inr
)


def test_customer_margin():
    # Customer gets 80% margin: 1000 + 800 = 1800
    price = calculate_selling_price(1000.0, buyer_type="Customer")
    assert price == 1800.0


def test_dealer_margin():
    # Dealer gets 40% margin: 1000 + 400 = 1400
    price = calculate_selling_price(1000.0, buyer_type="Dealer")
    assert price == 1400.0


def test_line_item_with_gst():
    # Cost 1000, Customer (1800/unit), Qty 2 -> Subtotal 3600
    # GST 18% -> 3600 * 0.18 = 648
    # Total = 4248
    item = calculate_line_item(
        cost_price=1000.0,
        qty=2,
        gst_percent=18.0,
        is_gst_bill=True,
        buyer_type="Customer"
    )
    assert item["unit_price"] == 1800.0
    assert item["qty"] == 2
    assert item["subtotal"] == 3600.0
    assert item["gst_percent"] == 18.0
    assert item["gst_amount"] == 648.0
    assert item["total"] == 4248.0


def test_line_item_without_gst():
    # Without GST, gst_amount is 0 and total equals subtotal
    item = calculate_line_item(
        cost_price=1000.0,
        qty=2,
        gst_percent=18.0,
        is_gst_bill=False,
        buyer_type="Customer"
    )
    assert item["unit_price"] == 1800.0
    assert item["subtotal"] == 3600.0
    assert item["gst_amount"] == 0.0
    assert item["total"] == 3600.0


def test_calculate_totals():
    items = [
        {"subtotal": 3600.0, "gst_amount": 648.0},
        {"subtotal": 1400.0, "gst_amount": 252.0}
    ]
    totals = calculate_totals(items)
    assert totals["base_total"] == 5000.0
    assert totals["gst_amount"] == 900.0
    assert totals["grand_total"] == 5900.0


def test_format_inr():
    formatted = format_inr(1234567.5)
    assert "12,34,567.50" in formatted


def test_vehicle_custom_margin():
    # Test 15% default margin: 50000 + 15% (7500) = 57500
    price_15 = calculate_selling_price(50000.0, margin_percent=15.0)
    assert price_15 == 57500.0

    # Test custom 20% margin: 50000 + 20% (10000) = 60000
    price_20 = calculate_selling_price(50000.0, margin_percent=20.0)
    assert price_20 == 60000.0

    # Test line item with 15% margin and 5% GST
    item = calculate_line_item(
        cost_price=50000.0,
        qty=1,
        gst_percent=5.0,
        is_gst_bill=True,
        margin_percent=15.0
    )
    assert item["unit_price"] == 57500.0
    assert item["subtotal"] == 57500.0
    assert item["gst_percent"] == 5.0
    assert item["gst_amount"] == 2875.0
    assert item["total"] == 60375.0
