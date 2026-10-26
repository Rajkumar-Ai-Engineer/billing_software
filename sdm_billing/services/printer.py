"""
Printer service for TVS LP 46 (and other label printers).
Communicates with Windows Spooler via win32print for RAW command delivery.
"""
import sys
from typing import List, Tuple

try:
    import win32print
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False


def get_installed_printers() -> List[str]:
    """
    Returns list of printer names available on the system.
    """
    if not WIN32_AVAILABLE or sys.platform != "win32":
        return ["TVS LP 46 (Simulated)", "Default System Printer"]

    printers = []
    try:
        flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
        for p in win32print.EnumPrinters(flags):
            name = p[2]
            printers.append(name)
    except Exception as e:
        print(f"Error enumerating printers: {e}")
    return printers or ["TVS LP 46"]


def send_raw_to_printer(printer_name: str, raw_commands: str, doc_name: str = "SDM Label") -> Tuple[bool, str]:
    """
    Sends raw string commands (TSPL / ZPL / EPL) directly to the Windows printer spooler.
    """
    if sys.platform != "win32":
        return False, "Raw printing requires a Windows operating system."

    if not WIN32_AVAILABLE:
        return False, "pywin32 library is not available in the current environment."

    if not printer_name:
        return False, "Printer name is required."

    raw_bytes = raw_commands.encode("utf-8")

    if "simulated" in str(printer_name).lower():
        return True, f"Simulated print successful ({len(raw_bytes)} bytes to '{printer_name}')."

    h_printer = None
    try:
        h_printer = win32print.OpenPrinter(printer_name)
        # Start document with RAW datatype
        win32print.StartDocPrinter(h_printer, 1, (doc_name, None, "RAW"))
        win32print.StartPagePrinter(h_printer)
        win32print.WritePrinter(h_printer, raw_bytes)
        win32print.EndPagePrinter(h_printer)
        win32print.EndDocPrinter(h_printer)
        return True, f"Successfully sent {len(raw_bytes)} bytes to '{printer_name}'."
    except Exception as e:
        err_msg = str(e)
        if "1801" in err_msg or "printer name is invalid" in err_msg.lower():
            return False, f"Printer '{printer_name}' not found. Please verify printer name in Printer Settings."
        return False, f"Printing error: {err_msg}"
    finally:
        if h_printer:
            try:
                win32print.ClosePrinter(h_printer)
            except Exception:
                pass
