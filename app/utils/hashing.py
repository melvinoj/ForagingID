import hashlib
from pathlib import Path
from typing import Optional

import imagehash
from PIL import Image


def file_sha256(path: Path, chunk_size: int = 65536) -> str:
    """Fast SHA-256 of file bytes — used for exact duplicate detection."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def perceptual_hash(path: Path) -> Optional[str]:
    """Average hash of image content — detects near-duplicate photos."""
    try:
        with Image.open(path) as img:
            return str(imagehash.average_hash(img))
    except Exception:
        return None
