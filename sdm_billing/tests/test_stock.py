import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException
from database import Base
from models import Product, Invoice, StockMovement
from schemas import InvoiceCreate, InvoiceItemIn
from routers.billing import save_invoice


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_stock_deduction_and_movement(test_db):
    prod = Product(
        part_no="TEST-P1",
        name="Test Part",
        cost_price=500.0,
        gst_percent=18.0,
        category="Spare Parts",
        stock_qty=10
    )
    test_db.add(prod)
    test_db.commit()

    inv_data = InvoiceCreate(
        category="Spare Parts",
        buyer_type="Customer",
        gst_mode="With GST (Tax Invoice)",
        customer_name="John Doe",
        mobile="9876543210",
        items=[
            InvoiceItemIn(
                part_no="TEST-P1",
                product_name="Test Part",
                price=900.0,
                qty=3,
                subtotal=2700.0,
                gst_percent=18.0,
                gst_amount=486.0,
                total=3186.0
            )
        ]
    )

    res = save_invoice(inv_data, test_db)
    assert res["success"] is True

    # Stock should now be 10 - 3 = 7
    refreshed_prod = test_db.query(Product).filter(Product.part_no == "TEST-P1").first()
    assert refreshed_prod.stock_qty == 7

    # Stock movement should be recorded
    mov = test_db.query(StockMovement).filter(StockMovement.part_no == "TEST-P1").first()
    assert mov is not None
    assert mov.change == -3


def test_insufficient_stock_error(test_db):
    prod = Product(
        part_no="TEST-P2",
        name="Low Stock Part",
        cost_price=100.0,
        gst_percent=18.0,
        category="Spare Parts",
        stock_qty=2
    )
    test_db.add(prod)
    test_db.commit()

    inv_data = InvoiceCreate(
        category="Spare Parts",
        customer_name="Jane Doe",
        mobile="9876543210",
        items=[
            InvoiceItemIn(
                part_no="TEST-P2",
                product_name="Low Stock Part",
                price=180.0,
                qty=5,  # Exceeds available stock of 2
                subtotal=900.0,
                gst_percent=18.0,
                gst_amount=162.0,
                total=1062.0
            )
        ]
    )

    with pytest.raises(HTTPException) as excinfo:
        save_invoice(inv_data, test_db)
    assert excinfo.value.status_code == 400
    assert "Not enough stock" in excinfo.value.detail

    # Stock should not have changed
    refreshed = test_db.query(Product).filter(Product.part_no == "TEST-P2").first()
    assert refreshed.stock_qty == 2
