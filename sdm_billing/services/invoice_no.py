import re
import threading
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Invoice
import config

_lock = threading.Lock()


def get_prefix_for_category(category: str = None) -> str:
    return getattr(config, "PREFIX_INVOICE", "SDM")


def generate_invoice_no(db: Session, category: str = None, year: int = None) -> str:
    """
    Generates next continuous unique serial invoice number atomically:
    Format: SDM0001, SDM0002, SDM0003, ...
    Increments by 1 every time a bill is created.
    """
    prefix = getattr(config, "PREFIX_INVOICE", "SDM").strip()
    pattern = rf"^{re.escape(prefix)}(\d+)$"

    with _lock:
        invoices = db.query(Invoice.invoice_no).all()
        max_seq = 0
        for (inv_no,) in invoices:
            if not inv_no:
                continue
            inv_str = str(inv_no).strip()
            m = re.match(pattern, inv_str, re.IGNORECASE)
            if m:
                try:
                    num = int(m.group(1))
                    if num > max_seq:
                        max_seq = num
                except ValueError:
                    pass

        next_seq = max_seq + 1
        return f"{prefix}{str(next_seq).zfill(4)}"
