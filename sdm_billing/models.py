from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    part_no = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    hsn = Column(String(50), nullable=True)
    cost_price = Column(Float, default=0.0, nullable=False)
    gst_percent = Column(Float, default=18.0, nullable=False)
    category = Column(String(50), nullable=False, index=True)  # Spare Parts, Service, Vehicle Sales
    vehicle_type = Column(String(50), nullable=True)  # Scooter, Cycle, Loader, etc.
    stock_qty = Column(Integer, default=0, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "part_no": self.part_no,
            "name": self.name,
            "hsn": self.hsn or "",
            "cost_price": float(self.cost_price),
            "gst_percent": float(self.gst_percent),
            "category": self.category,
            "vehicle_type": self.vehicle_type or "",
            "stock_qty": int(self.stock_qty)
        }


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_no = Column(String(100), unique=True, index=True, nullable=False)
    date = Column(Date, default=date.today, nullable=False)
    time = Column(String(20), default="", nullable=False)
    category = Column(String(50), nullable=False, index=True)  # Spare Parts, Service, Vehicle Sales
    buyer_type = Column(String(50), default="Customer", nullable=False)  # Customer or Dealer
    gst_mode = Column(String(50), default="With GST (Tax Invoice)", nullable=False)
    customer_name = Column(String(255), default="", nullable=False)
    mobile = Column(String(20), default="", nullable=False)
    address = Column(Text, default="", nullable=False)
    gstin = Column(String(50), nullable=True)
    base_total = Column(Float, default=0.0, nullable=False)
    gst_amount = Column(Float, default=0.0, nullable=False)
    grand_total = Column(Float, default=0.0, nullable=False)
    is_legacy = Column(Boolean, default=False, nullable=False)

    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_no": self.invoice_no,
            "date": str(self.date),
            "time": self.time,
            "category": self.category,
            "buyer_type": self.buyer_type,
            "gst_mode": self.gst_mode,
            "customer_name": self.customer_name,
            "mobile": self.mobile,
            "address": self.address,
            "gstin": self.gstin or "",
            "base_total": float(self.base_total),
            "gst_amount": float(self.gst_amount),
            "grand_total": float(self.grand_total),
            "is_legacy": self.is_legacy,
            "items": [item.to_dict() for item in self.items]
        }


class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    part_no = Column(String(100), nullable=False)
    product_name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)  # Unit selling price
    qty = Column(Integer, default=1, nullable=False)
    subtotal = Column(Float, nullable=False)
    gst_percent = Column(Float, default=18.0, nullable=False)
    gst_amount = Column(Float, default=0.0, nullable=False)
    total = Column(Float, nullable=False)

    invoice = relationship("Invoice", back_populates="items")

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_id": self.invoice_id,
            "part_no": self.part_no,
            "product_name": self.product_name,
            "price": float(self.price),
            "qty": int(self.qty),
            "subtotal": float(self.subtotal),
            "gst_percent": float(self.gst_percent),
            "gst_amount": float(self.gst_amount),
            "total": float(self.total)
        }


class Battery(Base):
    __tablename__ = "batteries"

    id = Column(Integer, primary_key=True, index=True)
    serial = Column(String(100), unique=True, index=True, nullable=False)
    type = Column(String(50), nullable=False)  # LFP or Li-Ion
    voltage = Column(Float, nullable=False)
    ah = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    sold = Column(Boolean, default=False, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "serial": self.serial,
            "type": self.type,
            "voltage": float(self.voltage),
            "ah": float(self.ah),
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else "",
            "sold": self.sold
        }


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    part_no = Column(String(100), nullable=False, index=True)
    change = Column(Integer, nullable=False)  # Positive for additions, negative for sales
    reason = Column(String(255), nullable=False)
    ref = Column(String(100), nullable=True)  # Invoice No or Adjustment Ref
    timestamp = Column(DateTime, default=datetime.now, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "part_no": self.part_no,
            "change": int(self.change),
            "reason": self.reason,
            "ref": self.ref or "",
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else ""
        }


class LabelPrintLog(Base):
    __tablename__ = "label_print_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    label_type = Column(String(50), nullable=False)  # battery, product, invoice, test
    reference = Column(String(100), nullable=False)
    copies = Column(Integer, default=1, nullable=False)
    mode = Column(String(50), nullable=False)  # driver_html, raw
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.strftime("%Y-%m-%d %H:%M:%S") if self.timestamp else "",
            "label_type": self.label_type,
            "reference": self.reference,
            "copies": int(self.copies),
            "mode": self.mode,
            "success": self.success,
            "error_message": self.error_message or ""
        }


class Worker(Base):
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), default="", nullable=False)
    role = Column(String(100), default="Technician", nullable=False)
    monthly_salary = Column(Float, default=15000.0, nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    attendance_records = relationship("Attendance", back_populates="worker", cascade="all, delete-orphan")
    salary_advances = relationship("SalaryAdvance", back_populates="worker", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "role": self.role,
            "monthly_salary": float(self.monthly_salary),
            "active": self.active,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    day_name = Column(String(20), nullable=False)  # e.g. Thursday
    status = Column(String(10), nullable=False, default="P")  # 'P' = Present, 'A' = Absent, 'HD' = Half-Day
    notes = Column(String(255), default="", nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    worker = relationship("Worker", back_populates="attendance_records")

    __table_args__ = (
        UniqueConstraint("worker_id", "date", name="uq_worker_attendance_date"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "worker_id": self.worker_id,
            "worker_name": self.worker.name if self.worker else "",
            "date": str(self.date),
            "day_name": self.day_name,
            "status": self.status,
            "notes": self.notes or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }


class SalaryAdvance(Base):
    __tablename__ = "salary_advances"

    id = Column(Integer, primary_key=True, index=True)
    worker_id = Column(Integer, ForeignKey("workers.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(Date, nullable=False, default=date.today)
    amount = Column(Float, nullable=False, default=0.0)
    notes = Column(String(255), default="", nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    worker = relationship("Worker", back_populates="salary_advances")

    def to_dict(self):
        return {
            "id": self.id,
            "worker_id": self.worker_id,
            "worker_name": self.worker.name if self.worker else "",
            "date": str(self.date),
            "amount": float(self.amount),
            "notes": self.notes or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }


class DailyExpense(Base):
    __tablename__ = "daily_expenses"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, default=date.today, nullable=False, index=True)
    bill_no = Column(String(100), default="", nullable=True)
    product_name = Column(String(255), default="", nullable=True)
    price = Column(Float, default=0.0, nullable=False)
    notes = Column(Text, default="", nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "date": str(self.date),
            "bill_no": self.bill_no or "",
            "product_name": self.product_name or "",
            "price": float(self.price),
            "notes": self.notes or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }


class PurchaseInvoice(Base):
    __tablename__ = "purchase_invoices"

    id = Column(Integer, primary_key=True, index=True)
    invoice_no = Column(String(100), nullable=False, index=True)
    received_date = Column(Date, default=date.today, nullable=False, index=True)
    price = Column(Float, default=0.0, nullable=False)
    total_qty = Column(Integer, default=0, nullable=False)
    notes = Column(Text, default="", nullable=True)
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "invoice_no": self.invoice_no,
            "received_date": str(self.received_date),
            "price": float(self.price),
            "total_qty": int(self.total_qty),
            "notes": self.notes or "",
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S") if self.created_at else ""
        }

