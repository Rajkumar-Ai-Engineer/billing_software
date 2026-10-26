from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from database import get_db
from models import LabelPrintLog, Product
from schemas import LabelPrintRequest, SettingsUpdate
from services.labels import build_label_commands, build_tspl, build_zpl, build_epl
from services.printer import get_installed_printers, send_raw_to_printer
from services.qr import generate_qr_base64, generate_barcode_base64
from services.pricing import calculate_selling_price, format_inr
import config

router = APIRouter()
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))


@router.get("/labels/preview", response_class=HTMLResponse)
def get_label_preview(
    request: Request,
    type: str = "product",
    part_no: Optional[str] = "",
    name: Optional[str] = "",
    price: Optional[float] = None,
    show_price: Optional[bool] = False,
    serial: Optional[str] = "",
    battery_type: Optional[str] = "LFP",
    voltage: Optional[float] = 48.0,
    ah: Optional[float] = 30.0,
    invoice_no: Optional[str] = "",
    width_mm: int = 50,
    height_mm: int = 30,
    copies: int = 1
):
    """
    Renders printable HTML label view sized to exact mm with print tips.
    """
    settings = config.load_settings()
    w = width_mm or settings.get("label_width_mm", 50)
    h = height_mm or settings.get("label_height_mm", 30)

    # Generate QR and Barcode data
    qr_b64 = ""
    bc_b64 = ""

    if type == "battery":
        s = serial or "SDM0001"
        qr_text = f"SN:{s}|{battery_type}|{voltage}V|{ah}Ah|{config.SHOP_NAME}"
        qr_b64 = generate_qr_base64(qr_text, box_size=3)
        bc_b64 = generate_barcode_base64(s)
    elif type == "invoice":
        s = invoice_no or "INV-001"
        qr_text = f"{config.WEBSITE_URL}?invoice={s}"
        qr_b64 = generate_qr_base64(qr_text, box_size=3)
        bc_b64 = generate_barcode_base64(s)
    else:  # product
        s = part_no or "SDM-PART"
        bc_b64 = generate_barcode_base64(s)
        qr_b64 = generate_qr_base64(s, box_size=3)

    return templates.TemplateResponse(
        request=request,
        name="label_preview.html",
        context={
            "type": type,
            "part_no": part_no,
            "name": name,
            "price": price,
            "show_price": show_price,
            "serial": serial,
            "battery_type": battery_type,
            "voltage": voltage,
            "ah": ah,
            "invoice_no": invoice_no,
            "qr_b64": qr_b64,
            "barcode_b64": bc_b64,
            "width_mm": w,
            "height_mm": h,
            "copies": copies,
            "shop_name": config.SHOP_NAME,
            "format_inr": format_inr
        }
    )


@router.get("/printer-settings", response_class=HTMLResponse)
def get_printer_settings_page(request: Request, db: Session = Depends(get_db)):
    settings = config.load_settings()
    printers = get_installed_printers()
    logs = db.query(LabelPrintLog).order_by(LabelPrintLog.id.desc()).limit(15).all()

    return templates.TemplateResponse(
        request=request,
        name="printer_settings.html",
        context={
            "active_page": "printer-settings",
            "settings": settings,
            "printers": printers,
            "presets": config.LABEL_PRESETS,
            "logs": [l.to_dict() for l in logs],
            "shop_name": config.SHOP_NAME
        }
    )


@router.get("/api/labels/printers")
def list_printers_api():
    printers = get_installed_printers()
    settings = config.load_settings()
    return {
        "printers": printers,
        "current_settings": settings
    }


@router.post("/api/labels/settings")
def update_printer_settings_api(payload: SettingsUpdate):
    update_data = {k: v for k, v in payload.dict().items() if v is not None}
    saved = config.save_settings(update_data)
    return {"success": True, "settings": saved}


@router.post("/api/labels/print")
def print_labels_api(request_data: LabelPrintRequest, db: Session = Depends(get_db)):
    """
    Sends raw print commands to TVS LP 46.
    """
    try:
        settings = config.load_settings()
        printer_name = request_data.printer_name or settings.get("printer_name", "TVS LP 46")
        language = (request_data.language or settings.get("printer_language", "TSPL")).upper()
        width_mm = request_data.width_mm or settings.get("label_width_mm", 50)
        height_mm = request_data.height_mm or settings.get("label_height_mm", 30)
        gap_mm = request_data.gap_mm or settings.get("label_gap_mm", 3)
        copies = max(1, request_data.copies)

        all_commands = []
        first_ref = "Bulk" if len(request_data.items) > 1 else "Label"

        for item in request_data.items:
            item_dict = item.model_dump() if hasattr(item, "model_dump") else item.dict()
            first_ref = item.serial or item.part_no or item.invoice_no or item.product_name or item.name or "Label"
            cmd = build_label_commands(
                item_dict,
                language=language,
                width_mm=width_mm,
                height_mm=height_mm,
                gap_mm=gap_mm,
                copies=copies
            )
            all_commands.append(cmd)

        full_payload = "\r\n".join(all_commands)

        # Send to printer
        success, message = send_raw_to_printer(printer_name, full_payload, doc_name="SDM Label")

        # Log action
        log = LabelPrintLog(
            timestamp=datetime.now(),
            label_type=str(request_data.items[0].type if request_data.items else "product")[:50],
            reference=str(first_ref)[:100],
            copies=copies * len(request_data.items),
            mode="raw",
            success=success,
            error_message=None if success else str(message)
        )
        db.add(log)
        db.commit()

        if not success:
            return JSONResponse(
                status_code=400,
                content={"success": False, "message": message, "commands": full_payload}
            )

        return {"success": True, "message": message, "printer": printer_name}
    except Exception as e:
        db.rollback()
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Print failed: {str(e)}"}
        )


@router.post("/api/labels/test-print")
def test_print_api(payload: dict = Body(...), db: Session = Depends(get_db)):
    """
    Prints a sample test label ("SDM TEST 1234567") to verify TVS LP 46 language and alignment.
    """
    try:
        settings = config.load_settings()
        printer_name = payload.get("printer_name") or settings.get("printer_name", "TVS LP 46")
        language = (payload.get("language") or settings.get("printer_language", "TSPL")).upper()
        width_mm = payload.get("width_mm") or settings.get("label_width_mm", 50)
        height_mm = payload.get("height_mm") or settings.get("label_height_mm", 30)

        test_item = {"type": "test"}
        cmd = build_label_commands(test_item, language=language, width_mm=width_mm, height_mm=height_mm, copies=1)

        success, message = send_raw_to_printer(printer_name, cmd, doc_name="SDM Test Label")

        log = LabelPrintLog(
            timestamp=datetime.now(),
            label_type="test",
            reference="SDM TEST 1234567",
            copies=1,
            mode="raw",
            success=success,
            error_message=None if success else str(message)
        )
        db.add(log)
        db.commit()

        if not success:
            return JSONResponse(status_code=400, content={"success": False, "message": message, "commands": cmd})

        return {"success": True, "message": message, "printer": printer_name}
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"success": False, "message": f"Test print failed: {str(e)}"})
