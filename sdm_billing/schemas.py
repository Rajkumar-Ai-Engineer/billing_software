import re
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict, model_validator


class ProductCreate(BaseModel):
    part_no: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    hsn: Optional[str] = ""
    cost_price: float = Field(..., ge=0.0)
    gst_percent: float = Field(18.0, ge=0.0)
    category: str = Field(...)  # Spare Parts, Service, Vehicle Sales
    vehicle_type: Optional[str] = None
    stock_qty: int = Field(0, ge=0)


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    hsn: Optional[str] = None
    cost_price: Optional[float] = None
    gst_percent: Optional[float] = None
    category: Optional[str] = None
    vehicle_type: Optional[str] = None
    stock_qty: Optional[int] = None


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    part_no: str
    name: str
    hsn: Optional[str] = ""
    cost_price: float
    gst_percent: float
    category: str
    vehicle_type: Optional[str] = None
    stock_qty: int


class InvoiceItemIn(BaseModel):
    part_no: str = Field(..., min_length=1)
    product_name: str = Field(..., min_length=1)
    price: float = Field(..., ge=0.0)
    qty: int = Field(..., ge=1)
    subtotal: float = Field(..., ge=0.0)
    gst_percent: float = Field(..., ge=0.0)
    gst_amount: float = Field(..., ge=0.0)
    total: float = Field(..., ge=0.0)


class InvoiceCreate(BaseModel):
    category: str = Field(..., min_length=1)  # Spare Parts, Service, Vehicle Sales
    buyer_type: str = Field("Customer")       # Customer or Dealer
    gst_mode: str = Field("With GST (Tax Invoice)")
    margin_percent: Optional[float] = None
    customer_name: str = Field(..., min_length=1)
    mobile: str = Field(..., min_length=10, max_length=15)
    address: Optional[str] = ""
    gstin: Optional[str] = ""
    items: List[InvoiceItemIn] = Field(..., min_length=1)

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, v: str) -> str:
        digits = "".join(filter(str.isdigit, str(v)))
        if len(digits) < 10:
            raise ValueError("Mobile number must be at least 10 digits")
        # Keep last 10 digits if longer (e.g. country code)
        if len(digits) > 10 and digits.startswith("91") and len(digits) == 12:
            return digits[2:]
        if len(digits) == 10:
            return digits
        return digits[-10:]

    @field_validator("gstin")
    @classmethod
    def validate_gstin(cls, v: Optional[str]) -> Optional[str]:
        if not v or not v.strip():
            return ""
        val = v.strip().upper()
        # 15 character standard Indian GSTIN format
        gstin_regex = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
        if not re.match(gstin_regex, val):
            # If not strict match, warn but permit or clean: check if alphanumeric 15 chars
            if len(val) != 15:
                raise ValueError("GSTIN must be a 15-character valid Indian GSTIN")
        return val


class BatteryCreate(BaseModel):
    type: str = Field(..., min_length=1)  # LFP or Li-Ion
    voltage: float = Field(..., gt=0)
    ah: float = Field(..., gt=0)
    create_product: bool = Field(True)


class StockAdjustmentIn(BaseModel):
    part_no: str = Field(..., min_length=1)
    change: int = Field(...)  # Can be positive or negative
    reason: Optional[str] = Field("Stock Adjustment")
    price: Optional[float] = Field(None, ge=0.0)


class LabelItemIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = "product"  # battery, product, invoice, test
    serial: Optional[str] = None
    part_no: Optional[str] = None
    name: Optional[str] = None
    product_name: Optional[str] = None
    cost_price: Optional[float] = None
    price: Optional[float] = None
    show_price: Optional[bool] = False
    battery_type: Optional[str] = None
    voltage: Optional[float] = None
    ah: Optional[float] = None
    invoice_no: Optional[str] = None
    copies: Optional[int] = 1

    @model_validator(mode="after")
    def sync_name_fields(self):
        if not self.product_name and self.name:
            self.product_name = self.name
        elif not self.name and self.product_name:
            self.name = self.product_name
        return self


class LabelPrintRequest(BaseModel):
    mode: str = Field("raw")  # "raw" or "driver_html"
    language: Optional[str] = "TSPL"  # "TSPL", "ZPL", "EPL"
    printer_name: Optional[str] = None
    width_mm: Optional[int] = 50
    height_mm: Optional[int] = 30
    gap_mm: Optional[int] = 3
    copies: int = Field(1, ge=1)
    items: List[LabelItemIn] = Field(..., min_length=1)


class SettingsUpdate(BaseModel):
    printer_name: Optional[str] = None
    print_mode: Optional[str] = None
    printer_language: Optional[str] = None
    label_width_mm: Optional[int] = None
    label_height_mm: Optional[int] = None
    label_gap_mm: Optional[int] = None
    margin_customer: Optional[float] = None
    margin_dealer: Optional[float] = None
    auth_enabled: Optional[bool] = None
    auth_password: Optional[str] = None


class WorkerCreate(BaseModel):
    name: str = Field(..., min_length=1)
    phone: Optional[str] = ""
    role: Optional[str] = "Technician"
    monthly_salary: float = Field(15000.0, ge=0.0)
    active: bool = True


class WorkerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    monthly_salary: Optional[float] = Field(None, ge=0.0)
    active: Optional[bool] = None


class WorkerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    role: str
    monthly_salary: float
    active: bool
    created_at: str


class AttendanceRecordIn(BaseModel):
    worker_id: int
    status: str = Field("P")  # 'P', 'A', 'HD'
    notes: Optional[str] = ""


class DailyAttendanceSaveIn(BaseModel):
    date: str  # YYYY-MM-DD
    records: List[AttendanceRecordIn]


class SalaryAdvanceIn(BaseModel):
    worker_id: int
    date: str
    amount: float = Field(..., gt=0.0)
    notes: Optional[str] = ""


class DailyExpenseCreate(BaseModel):
    date: Optional[str] = None  # YYYY-MM-DD, defaults to today
    bill_no: Optional[str] = ""
    product_name: Optional[str] = ""
    price: float = Field(0.0, ge=0.0)
    notes: Optional[str] = ""


class DailyExpenseUpdate(BaseModel):
    date: Optional[str] = None
    bill_no: Optional[str] = None
    product_name: Optional[str] = None
    price: Optional[float] = Field(None, ge=0.0)
    notes: Optional[str] = None


class DailyExpenseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: str
    bill_no: str
    product_name: str
    price: float
    notes: str
    created_at: str


class PurchaseInvoiceCreate(BaseModel):
    invoice_no: str = Field(..., min_length=1)
    received_date: Optional[str] = None  # YYYY-MM-DD, defaults to today
    price: float = Field(0.0, ge=0.0)
    total_qty: int = Field(0, ge=0)
    notes: Optional[str] = ""


class PurchaseInvoiceUpdate(BaseModel):
    invoice_no: Optional[str] = None
    received_date: Optional[str] = None
    price: Optional[float] = Field(None, ge=0.0)
    total_qty: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class PurchaseInvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_no: str
    received_date: str
    price: float
    total_qty: int
    notes: str
    created_at: str

