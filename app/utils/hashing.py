import hashlib
from pathlib import Path


def file_sha256(path: Path, chunk_size: int = 65536) -> str:
    """Fast SHA-256 of file bytes — used for exact duplicate detection."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()
