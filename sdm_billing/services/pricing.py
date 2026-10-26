from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List
import config


def to_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0.00")
    return Decimal(str(value))


def round_cur(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_selling_price(cost_price: float, buyer_type: str = "Customer", margin_percent: float = None) -> float:
    """
    Selling price = Cost Price + margin
    If margin_percent is provided: Cost * (1 + margin_percent / 100)
    Otherwise:
    Customer: Cost * 1.80 (80% margin)
    Dealer: Cost * 1.40 (40% margin)
    """
    cost = to_decimal(cost_price)
    if margin_percent is not None:
        margin = Decimal(str(margin_percent)) / Decimal("100")
    else:
        settings = config.load_settings()
        margin_cust = Decimal(str(settings.get("margin_customer", config.MARGIN_CUSTOMER)))
        margin_deal = Decimal(str(settings.get("margin_dealer", config.MARGIN_DEALER)))
        margin = margin_deal if buyer_type.strip().lower() == "dealer" else margin_cust

    selling_price = cost + (cost * margin)
    return float(round_cur(selling_price))


def calculate_line_item(
    cost_price: float,
    qty: int,
    gst_percent: float,
    is_gst_bill: bool = True,
    buyer_type: str = "Customer",
    unit_price_override: float = None,
    margin_percent: float = None
) -> Dict[str, Any]:
    """
    Calculates unit price, subtotal, GST amount and total for a single item row.
    """
    if unit_price_override is not None and unit_price_override > 0:
        unit_price = to_decimal(unit_price_override)
    else:
        unit_price = to_decimal(calculate_selling_price(cost_price, buyer_type, margin_percent=margin_percent))

    q = Decimal(str(qty))
    subtotal = round_cur(unit_price * q)

    if is_gst_bill:
        gst_pct = to_decimal(gst_percent)
        gst_amount = round_cur(subtotal * (gst_pct / Decimal("100")))
    else:
        gst_pct = Decimal("0.00")
        gst_amount = Decimal("0.00")

    total = round_cur(subtotal + gst_amount)

    return {
        "unit_price": float(round_cur(unit_price)),
        "qty": int(qty),
        "subtotal": float(subtotal),
        "gst_percent": float(gst_pct),
        "gst_amount": float(gst_amount),
        "total": float(total)
    }


def calculate_totals(items: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Summarizes base total, total GST amount, and grand total from line items.
    """
    base_total = Decimal("0.00")
    gst_amount = Decimal("0.00")

    for item in items:
        base_total += to_decimal(item.get("subtotal", 0.0))
        gst_amount += to_decimal(item.get("gst_amount", 0.0))

    base_total = round_cur(base_total)
    gst_amount = round_cur(gst_amount)
    grand_total = round_cur(base_total + gst_amount)

    return {
        "base_total": float(base_total),
        "gst_amount": float(gst_amount),
        "grand_total": float(grand_total)
    }


def format_inr(number: float) -> str:
    """
    Formats float into Indian currency style: e.g. 1234567.5 -> ₹ 12,34,567.50
    """
    try:
        dec = to_decimal(number)
        rounded = round_cur(dec)
        parts = str(rounded).split(".")
        integer_part = parts[0]
        decimal_part = parts[1] if len(parts) > 1 else "00"

        is_neg = integer_part.startswith("-")
        if is_neg:
            integer_part = integer_part[1:]

        if len(integer_part) <= 3:
            res = integer_part
        else:
            last_three = integer_part[-3:]
            remaining = integer_part[:-3]
            # Group by 2 digits for remaining
            grouped = []
            while remaining:
                grouped.append(remaining[-2:])
                remaining = remaining[:-2]
            grouped.reverse()
            res = ",".join(grouped) + "," + last_three

        if is_neg:
            res = "-" + res

        return f"₹ {res}.{decimal_part}"
    except Exception:
        return f"₹ {number:.2f}"
