"""
Label layout and command generation for TVS-E LP 46 printer:
- TSPL
- ZPL
- EPL
"""
from typing import Dict, Any
from services.pricing import calculate_selling_price, format_inr
import config


def get_dots(mm: float, dpi: int = 203) -> int:
    return int(round(mm * (dpi / 25.4)))  # 203 dpi is ~8 dots/mm


def _clean_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    s = str(val).strip()
    return default if s.lower() == "none" else s


def _clean_num(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def build_tspl(label: Dict[str, Any], width_mm: int = 50, height_mm: int = 30, gap_mm: int = 3, copies: int = 1) -> str:
    """
    Builds TSPL command string for TVS LP 46 thermal printer.
    """
    lines = [
        f"SIZE {width_mm} mm, {height_mm} mm",
        f"GAP {gap_mm} mm, 0 mm",
        "DIRECTION 1",
        "CLS"
    ]

    label_type = _clean_str(label.get("type"), "product").lower()

    if label_type == "battery":
        serial = _clean_str(label.get("serial"), "SDM0001")
        b_type = _clean_str(label.get("battery_type"), "LFP")
        volts = label.get("voltage") if label.get("voltage") is not None else 48.0
        ah = label.get("ah") if label.get("ah") is not None else 30.0
        spec = f"{b_type} {volts}V {ah}Ah"
        qr_data = f"SN:{serial}|{b_type}|{volts}V|{ah}Ah|{config.SHOP_NAME}"

        lines.append(f'TEXT 20, 16, "2", 0, 1, 1, "{config.SHOP_NAME}"')
        lines.append(f'TEXT 20, 42, "3", 0, 1, 1, "{serial}"')
        lines.append(f'TEXT 20, 76, "2", 0, 1, 1, "{spec}"')
        lines.append(f'BARCODE 20, 108, "128", 50, 1, 0, 2, 2, "{serial}"')
        lines.append(f'QRCODE 260, 20, L, 4, A, 0, "{qr_data}"')

    elif label_type == "product":
        part_no = _clean_str(label.get("part_no"), "")
        name = _clean_str(label.get("product_name") or label.get("name"), "")[:35]
        show_price = bool(label.get("show_price", False))
        cost_price = _clean_num(label.get("cost_price"), 0.0)
        raw_price = label.get("price")
        if raw_price is not None and str(raw_price).strip() != "" and str(raw_price).strip().lower() != "none":
            selling_price = _clean_num(raw_price, 0.0)
        else:
            selling_price = calculate_selling_price(cost_price, "Customer")

        lines.append(f'TEXT 20, 16, "2", 0, 1, 1, "{config.SHOP_NAME}"')
        lines.append(f'TEXT 20, 42, "2", 0, 1, 1, "{name}"')
        lines.append(f'BARCODE 20, 72, "128", 55, 1, 0, 2, 2, "{part_no}"')
        if show_price:
            price_str = format_inr(selling_price)
            lines.append(f'TEXT 20, 165, "3", 0, 1, 1, "MRP: {price_str}"')

    elif label_type == "invoice":
        inv_no = _clean_str(label.get("invoice_no"), "")
        lines.append(f'TEXT 20, 16, "2", 0, 1, 1, "{config.SHOP_NAME}"')
        lines.append(f'TEXT 20, 42, "3", 0, 1, 1, "INVOICE: {inv_no}"')
        lines.append(f'BARCODE 20, 80, "128", 60, 1, 0, 2, 2, "{inv_no}"')

    else:  # test label
        lines.append(f'TEXT 20, 16, "3", 0, 1, 1, "{config.SHOP_NAME} - TEST"')
        lines.append(f'TEXT 20, 52, "2", 0, 1, 1, "TVS LP 46 TSPL SUCCESS"')
        lines.append('BARCODE 20, 88, "128", 55, 1, 0, 2, 2, "SDM TEST 1234567"')
        lines.append(f'QRCODE 270, 20, L, 4, A, 0, "{config.WEBSITE_URL}"')

    lines.append(f"PRINT {max(1, int(copies))}, 1\n")
    return "\r\n".join(lines)


def build_zpl(label: Dict[str, Any], width_mm: int = 50, height_mm: int = 30, copies: int = 1) -> str:
    """
    Builds ZPL (ZPL II) command string.
    """
    w_dots = get_dots(width_mm)
    h_dots = get_dots(height_mm)

    cmds = [
        "^XA",
        f"^PW{w_dots}",
        f"^LL{h_dots}"
    ]

    label_type = _clean_str(label.get("type"), "product").lower()

    if label_type == "battery":
        serial = _clean_str(label.get("serial"), "SDM0001")
        b_type = _clean_str(label.get("battery_type"), "LFP")
        volts = label.get("voltage") if label.get("voltage") is not None else 48.0
        ah = label.get("ah") if label.get("ah") is not None else 30.0
        spec = f"{b_type} {volts}V {ah}Ah"
        qr_data = f"SN:{serial}|{b_type}|{volts}V|{ah}Ah|{config.SHOP_NAME}"

        cmds.append(f"^FO20,16^A0N,20,20^FD{config.SHOP_NAME}^FS")
        cmds.append(f"^FO20,40^A0N,28,28^FD{serial}^FS")
        cmds.append(f"^FO20,72^A0N,22,22^FD{spec}^FS")
        cmds.append(f"^FO20,104^BCN,48,Y,N,N^FD{serial}^FS")
        cmds.append(f"^FO260,20^BQN,2,4^FDQA,{qr_data}^FS")

    elif label_type == "product":
        part_no = _clean_str(label.get("part_no"), "")
        name = _clean_str(label.get("product_name") or label.get("name"), "")[:35]
        show_price = bool(label.get("show_price", False))
        cost_price = _clean_num(label.get("cost_price"), 0.0)
        raw_price = label.get("price")
        if raw_price is not None and str(raw_price).strip() != "" and str(raw_price).strip().lower() != "none":
            selling_price = _clean_num(raw_price, 0.0)
        else:
            selling_price = calculate_selling_price(cost_price, "Customer")

        cmds.append(f"^FO20,16^A0N,20,20^FD{config.SHOP_NAME}^FS")
        cmds.append(f"^FO20,40^A0N,22,22^FD{name}^FS")
        cmds.append(f"^FO20,72^BCN,50,Y,N,N^FD{part_no}^FS")
        if show_price:
            price_str = format_inr(selling_price)
            cmds.append(f"^FO20,160^A0N,26,26^FDMRP: {price_str}^FS")

    elif label_type == "invoice":
        inv_no = _clean_str(label.get("invoice_no"), "")
        cmds.append(f"^FO20,16^A0N,20,20^FD{config.SHOP_NAME}^FS")
        cmds.append(f"^FO20,42^A0N,26,26^FDINV: {inv_no}^FS")
        cmds.append(f"^FO20,80^BCN,55,Y,N,N^FD{inv_no}^FS")

    else:  # test
        cmds.append(f"^FO20,16^A0N,24,24^FD{config.SHOP_NAME} - TEST^FS")
        cmds.append("^FO20,48^A0N,20,20^FDTVS LP 46 ZPL SUCCESS^FS")
        cmds.append('^FO20,80^BCN,50,Y,N,N^FDSDM TEST 1234567^FS')
        cmds.append(f"^FO270,20^BQN,2,4^FDQA,{config.WEBSITE_URL}^FS")

    cmds.append(f"^PQ{max(1, int(copies))}")
    cmds.append("^XZ\n")
    return "\r\n".join(cmds)


def build_epl(label: Dict[str, Any], width_mm: int = 50, height_mm: int = 30, gap_mm: int = 3, copies: int = 1) -> str:
    """
    Builds EPL (Eltron Programming Language) command string.
    """
    w_dots = get_dots(width_mm)
    h_dots = get_dots(height_mm)
    g_dots = get_dots(gap_mm)

    cmds = [
        "N",  # Clear image buffer
        f"q{w_dots}",
        f"Q{h_dots},{g_dots}"
    ]

    label_type = _clean_str(label.get("type"), "product").lower()

    if label_type == "battery":
        serial = _clean_str(label.get("serial"), "SDM0001")
        b_type = _clean_str(label.get("battery_type"), "LFP")
        volts = label.get("voltage") if label.get("voltage") is not None else 48.0
        ah = label.get("ah") if label.get("ah") is not None else 30.0
        spec = f"{b_type} {volts}V {ah}Ah"
        qr_data = f"SN:{serial}|{b_type}|{volts}V|{ah}Ah|{config.SHOP_NAME}"

        cmds.append(f'A20,16,0,2,1,1,N,"{config.SHOP_NAME}"')
        cmds.append(f'A20,40,0,3,1,1,N,"{serial}"')
        cmds.append(f'A20,72,0,2,1,1,N,"{spec}"')
        cmds.append(f'B20,104,0,1,2,2,45,B,"{serial}"')
        cmds.append(f'b260,20,Q,s4,"{qr_data}"')

    elif label_type == "product":
        part_no = _clean_str(label.get("part_no"), "")
        name = _clean_str(label.get("product_name") or label.get("name"), "")[:35]
        show_price = bool(label.get("show_price", False))
        cost_price = _clean_num(label.get("cost_price"), 0.0)
        raw_price = label.get("price")
        if raw_price is not None and str(raw_price).strip() != "" and str(raw_price).strip().lower() != "none":
            selling_price = _clean_num(raw_price, 0.0)
        else:
            selling_price = calculate_selling_price(cost_price, "Customer")

        cmds.append(f'A20,16,0,2,1,1,N,"{config.SHOP_NAME}"')
        cmds.append(f'A20,40,0,2,1,1,N,"{name}"')
        cmds.append(f'B20,72,0,1,2,2,50,B,"{part_no}"')
        if show_price:
            price_str = format_inr(selling_price)
            cmds.append(f'A20,155,0,3,1,1,N,"MRP: {price_str}"')

    elif label_type == "invoice":
        inv_no = _clean_str(label.get("invoice_no"), "")
        cmds.append(f'A20,16,0,2,1,1,N,"{config.SHOP_NAME}"')
        cmds.append(f'A20,42,0,3,1,1,N,"INV: {inv_no}"')
        cmds.append(f'B20,80,0,1,2,2,55,B,"{inv_no}"')

    else:  # test
        cmds.append(f'A20,16,0,3,1,1,N,"{config.SHOP_NAME} - TEST"')
        cmds.append('A20,50,0,2,1,1,N,"TVS LP 46 EPL SUCCESS"')
        cmds.append('B20,85,0,1,2,2,50,B,"SDM TEST 1234567"')
        cmds.append(f'b260,20,Q,s4,"{config.WEBSITE_URL}"')

    cmds.append(f"P{max(1, int(copies))}\n")
    return "\r\n".join(cmds)


def build_label_commands(
    label: Dict[str, Any],
    language: str = "TSPL",
    width_mm: int = 50,
    height_mm: int = 30,
    gap_mm: int = 3,
    copies: int = 1
) -> str:
    lang = (language or "TSPL").upper()
    if lang == "ZPL":
        return build_zpl(label, width_mm, height_mm, copies)
    elif lang == "EPL":
        return build_epl(label, width_mm, height_mm, gap_mm, copies)
    else:
        return build_tspl(label, width_mm, height_mm, gap_mm, copies)
