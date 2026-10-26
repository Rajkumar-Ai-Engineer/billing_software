import re
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db
from models import Battery, Product
from schemas import BatteryCreate
from services.qr import generate_qr_base64, generate_barcode_base64
from services.excel_sync import sync_products_to_excel_files
import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


def get_next_battery_serial(db: Session) -> str:
    """
    Finds highest existing serial number matching SDM[0-9]+ across batteries and products,
    then returns next incremented serial formatted as SDM0021 style (zero padded to at least 4 digits).
    """
    max_num = 0

    # Check batteries
    batts = db.query(Battery.serial).all()
    for (s,) in batts:
        m = re.match(r"^SDM(\d+)$", s, re.IGNORECASE)
        if m:
            max_num = max(max_num, int(m.group(1)))

    # Check products
    prods = db.query(Product.part_no).filter(Product.part_no.like("SDM%")).all()
    for (p,) in prods:
        m = re.match(r"^SDM(\d+)$", p, re.IGNORECASE)
        if m:
            max_num = max(max_num, int(m.group(1)))

    next_num = max(max_num + 1, 1)
    # Format e.g. SDM0021
    return f"SDM{str(next_num).zfill(4)}"


@router.get("/battery-qr", response_class=HTMLResponse)
def get_battery_page(request: Request, db: Session = Depends(get_db)):
    batteries = db.query(Battery).order_by(Battery.id.desc()).all()
    next_serial = get_next_battery_serial(db)

    return templates.TemplateResponse(
        request=request,
        name="battery.html",
        context={
            "active_page": "battery-qr",
            "next_serial": next_serial,
            "batteries": [b.to_dict() for b in batteries],
            "shop_name": config.SHOP_NAME
        }
    )


@router.get("/api/batteries")
def list_batteries_api(db: Session = Depends(get_db)):
    batteries = db.query(Battery).order_by(Battery.id.desc()).all()
    return [b.to_dict() for b in batteries]


@router.post("/api/batteries/generate")
def generate_battery_qr(payload: BatteryCreate, db: Session = Depends(get_db)):
    serial = get_next_battery_serial(db)

    # 1. Save Battery record
    battery = Battery(
        serial=serial,
        type=payload.type,
        voltage=payload.voltage,
        ah=payload.ah,
        created_at=datetime.now(),
        sold=False
    )
    db.add(battery)

    # 2. Optionally link / create in Product table with stock 1
    if payload.create_product:
        existing_prod = db.query(Product).filter(Product.part_no == serial).first()
        if not existing_prod:
            prod_name = f"{payload.type} {int(payload.voltage)}V {int(payload.ah)}Ah Battery Pack"
            new_prod = Product(
                part_no=serial,
                name=prod_name,
                hsn="8507",
                cost_price=15000.0,
                gst_percent=18.0,
                category="Spare Parts",
                stock_qty=1
            )
            db.add(new_prod)

    db.commit()

    # Sync to Excel & CSV files if a product was created
    if payload.create_product:
        sync_products_to_excel_files(db)

    # 3. Generate QR & Barcode base64
    qr_data = f"SN:{serial}|{payload.type}|{payload.voltage}V|{payload.ah}Ah|{config.SHOP_NAME}"
    qr_b64 = generate_qr_base64(qr_data)
    bc_b64 = generate_barcode_base64(serial)

    return {
        "success": True,
        "serial": serial,
        "type": payload.type,
        "voltage": payload.voltage,
        "ah": payload.ah,
        "qr_base64": qr_b64,
        "barcode_base64": bc_b64,
        "battery": battery.to_dict()
    }
