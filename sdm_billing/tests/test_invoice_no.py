import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database import Base
from models import Invoice
from services.invoice_no import generate_invoice_no, get_prefix_for_category


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


def test_invoice_prefixes():
    assert get_prefix_for_category("Spare Parts") == "SDM"
    assert get_prefix_for_category("Service") == "SDM"
    assert get_prefix_for_category("Vehicle Sales") == "SDM"


def test_first_invoice_number(test_db):
    no_spare = generate_invoice_no(test_db, "Spare Parts")
    assert no_spare == "SDM0001"

    no_service = generate_invoice_no(test_db, "Service")
    assert no_service == "SDM0001"


def test_incrementing_invoice_number(test_db):
    inv1 = Invoice(
        invoice_no="SDM0001",
        category="Spare Parts",
        customer_name="Test Cust",
        mobile="9876543210"
    )
    test_db.add(inv1)
    test_db.commit()

    next_no = generate_invoice_no(test_db, "Spare Parts")
    assert next_no == "SDM0002"

    inv2 = Invoice(
        invoice_no="SDM0020",
        category="Spare Parts",
        customer_name="Test Cust 2",
        mobile="9876543210"
    )
    test_db.add(inv2)
    test_db.commit()

    next_no_jump = generate_invoice_no(test_db, "Spare Parts")
    assert next_no_jump == "SDM0021"
