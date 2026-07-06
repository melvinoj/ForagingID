"""
Connections API — helper endpoints for the Connect page.

GET /api/connections/qr?url=...  — returns a base64 PNG of a QR code for the given URL.
Uses the server-side `qrcode` library so the frontend has no external CDN dependency.
"""

import base64
import io
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

router = APIRouter(tags=["connections"])


@router.get("/api/connections/qr")
async def generate_qr(
    url: str = Query(..., description="URL to encode in the QR code"),
):
    """
    Generate a QR code PNG for `url` and return it as a base64 data URL.
    The client embeds the result directly as an <img src="data:image/png;base64,...">.
    """
    try:
        import qrcode
        from qrcode.image.pure import PyPNGImage
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="qrcode library not installed. Run: pip install qrcode[pil]",
        )

    qr = qrcode.QRCode(
        version=None,          # auto-size
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#2d5016", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    png_bytes = buf.read()

    b64 = base64.b64encode(png_bytes).decode("ascii")
    data_url = f"data:image/png;base64,{b64}"

    return {"data_url": data_url, "url": url}
