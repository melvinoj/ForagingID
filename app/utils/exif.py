import io
import logging
import struct
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

import exifread
from PIL import Image

# Suppress piexif/exifread noise about missing EXIF in PNGs
logging.getLogger("exifread").setLevel(logging.CRITICAL)


@dataclass
class ExifData:
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude_m: Optional[float] = None
    taken_at: Optional[datetime] = None
    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


def _dms_to_decimal(dms_values, ref: str) -> Optional[float]:
    """Convert degrees/minutes/seconds to decimal degrees."""
    try:
        d = float(dms_values[0].num) / float(dms_values[0].den)
        m = float(dms_values[1].num) / float(dms_values[1].den)
        s = float(dms_values[2].num) / float(dms_values[2].den)
        decimal = d + (m / 60.0) + (s / 3600.0)
        if ref in ("S", "W"):
            decimal = -decimal
        return decimal
    except (IndexError, ZeroDivisionError, AttributeError, TypeError):
        return None


def extract_exif(file_path: Path) -> ExifData:
    data = ExifData()

    try:
        with open(file_path, "rb") as f:
            tags = exifread.process_file(f, stop_tag="GPS GPSLongitude", details=False)

        # GPS
        lat_tag = tags.get("GPS GPSLatitude")
        lat_ref = tags.get("GPS GPSLatitudeRef")
        lon_tag = tags.get("GPS GPSLongitude")
        lon_ref = tags.get("GPS GPSLongitudeRef")
        alt_tag = tags.get("GPS GPSAltitude")

        if lat_tag and lat_ref and lon_tag and lon_ref:
            data.latitude = _dms_to_decimal(lat_tag.values, str(lat_ref))
            data.longitude = _dms_to_decimal(lon_tag.values, str(lon_ref))

        if alt_tag and alt_tag.values:
            try:
                v = alt_tag.values[0]
                data.altitude_m = float(v.num) / float(v.den)
            except (ZeroDivisionError, AttributeError):
                pass

        # Timestamp
        dt_tag = tags.get("EXIF DateTimeOriginal") or tags.get("Image DateTime")
        if dt_tag:
            try:
                data.taken_at = datetime.strptime(str(dt_tag), "%Y:%m:%d %H:%M:%S")
            except ValueError:
                pass

        # Camera
        make_tag = tags.get("Image Make")
        model_tag = tags.get("Image Model")
        if make_tag:
            data.camera_make = str(make_tag).strip()
        if model_tag:
            data.camera_model = str(model_tag).strip()

    except Exception:
        pass

    # Image dimensions via Pillow (works even without EXIF)
    try:
        with Image.open(file_path) as img:
            data.width, data.height = img.size
    except Exception:
        pass

    return data
