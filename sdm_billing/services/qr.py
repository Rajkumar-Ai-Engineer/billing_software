import io
import base64
import qrcode
import barcode
from barcode.writer import ImageWriter


def generate_qr_base64(text: str, box_size: int = 4, border: int = 1) -> str:
    """
    Generates a base64 encoded PNG image for the given text as a QR code.
    """
    if not text:
        return ""
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=box_size,
            border=border
        )
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"QR code generation error: {e}")
        return ""


def generate_barcode_base64(code_text: str) -> str:
    """
    Generates a base64 encoded PNG image for Code128 barcode.
    """
    if not code_text:
        return ""
    try:
        clean_text = str(code_text).strip()
        code128 = barcode.get_barcode_class("code128")
        writer = ImageWriter()
        buffer = io.BytesIO()
        barcode_instance = code128(clean_text, writer=writer)
        barcode_instance.write(
            buffer,
            options={
                "write_text": True,
                "text_distance": 2.0,
                "quiet_zone": 2.0,
                "module_height": 8.0,
                "module_width": 0.2
            }
        )
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"Barcode generation error: {e}")
        return ""
