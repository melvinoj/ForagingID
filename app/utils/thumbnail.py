"""
Thumbnail generation utility.

Design rules:
  - Always produces a valid JPEG RGB output regardless of input mode.
  - Handles ALL PIL modes: RGBA, LA, P, CMYK, L, I, F, YCbCr, HSV, etc.
  - Converts ICC color profiles (Display P3, AdobeRGB) → sRGB so iPhone /
    HEIC photos render with correct colours in any browser.
  - Applies EXIF orientation before resizing.
  - Skips re-generation only if an existing thumbnail is valid (>= MIN_THUMB_BYTES).
  - Cleans up partial writes on failure so a corrupt stub never blocks a retry.
  - force=True overrides the skip-if-valid check (used by regen_thumbnails.py).
"""

import io
from pathlib import Path
from typing import Optional

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    HEIC_SUPPORTED = False

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".tif", ".webp"}

# Thumbnails smaller than this are treated as corrupt / failed writes.
# 200 is conservative: even a 1×1 JPEG header is ~300 bytes, but solid-colour
# thumbnails (e.g. test placeholder images) can legitimately compress to ~700 bytes.
MIN_THUMB_BYTES = 200


def is_supported_image(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_FORMATS


def _to_rgb(img: "Image.Image") -> "Image.Image":
    """
    Convert any PIL image to sRGB RGB, ready for JPEG output.

    Priority order:
      1. ICC profile conversion (e.g. Display P3 from iPhones → sRGB)
      2. Mode-specific compositing / conversion:
           RGBA / LA  → composite over white (preserves edge anti-aliasing)
           P          → expand palette; composite if transparent, else convert
           CMYK       → PIL's inversion-aware CMYK→RGB
           L / I / F  → grayscale → RGB
           YCbCr etc  → generic .convert("RGB")
    """
    from PIL import Image, ImageCms
    # ── ICC profile (wide-gamut colour spaces) ────────────────────────────
    icc_bytes = img.info.get("icc_profile")
    if icc_bytes:
        try:
            src_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_bytes))
            srgb_profile = ImageCms.createProfile("sRGB")
            return ImageCms.profileToProfile(
                img, src_profile, srgb_profile, outputMode="RGB"
            )
        except Exception:
            pass  # fall through to mode conversion

    # ── Mode-specific paths ───────────────────────────────────────────────
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg

    if img.mode == "LA":
        img_rgba = img.convert("RGBA")
        bg = Image.new("RGB", img_rgba.size, (255, 255, 255))
        bg.paste(img_rgba, mask=img_rgba.split()[3])
        return bg

    if img.mode == "P":
        # Palette images may carry a transparency entry
        if "transparency" in img.info:
            img_rgba = img.convert("RGBA")
            bg = Image.new("RGB", img_rgba.size, (255, 255, 255))
            bg.paste(img_rgba, mask=img_rgba.split()[3])
            return bg
        return img.convert("RGB")

    if img.mode != "RGB":
        return img.convert("RGB")

    return img


def generate_thumbnail(
    source_path: Path,
    thumbnails_dir: Path,
    size: int = 300,
    force: bool = False,
) -> Optional[Path]:
    """
    Generate a JPEG thumbnail for *source_path*.

    Returns the thumbnail Path on success, None on failure.

    Args:
        source_path:    Original image file.
        thumbnails_dir: Directory to write thumbnails into.
        size:           Max width/height in pixels (aspect ratio preserved).
        force:          Regenerate even if a valid thumbnail already exists.
    """
    from PIL import Image, ImageOps
    thumbnails_dir.mkdir(parents=True, exist_ok=True)

    thumb_name = source_path.stem + "_thumb.jpg"
    thumb_path = thumbnails_dir / thumb_name

    # Skip only if the existing file is large enough to be a real JPEG
    if not force and thumb_path.exists():
        if thumb_path.stat().st_size >= MIN_THUMB_BYTES:
            return thumb_path
        # File exists but is suspiciously small — fall through and overwrite

    try:
        with Image.open(source_path) as img:
            img.load()  # force full decode; raises on truncated files
            img = ImageOps.exif_transpose(img)
            img.thumbnail((size, size), Image.LANCZOS)
            img = _to_rgb(img)
            img.save(thumb_path, "JPEG", quality=82, optimize=True)

        # Validate output size
        if thumb_path.stat().st_size < MIN_THUMB_BYTES:
            thumb_path.unlink(missing_ok=True)
            return None

        return thumb_path

    except Exception:
        # Clean up any partial write so the next attempt starts fresh
        if thumb_path.exists():
            thumb_path.unlink(missing_ok=True)
        return None
