"""
Whisper transcription — Phase 11a.4.

Server-side speech-to-text for encounter audio via the OpenAI Whisper REST API
(POST https://api.openai.com/v1/audio/transcriptions). Called directly with httpx
so no extra SDK dependency is added — matches the project's other integration
clients (PlantNet, iNaturalist, …).

Rules:
  - Requires OPENAI_API_KEY in settings (raises WhisperError if absent)
  - Transcription is a deliberate laptop-side step, never automatic on capture
  - Best-effort: connection/timeout failures raise a typed error the endpoint
    surfaces, rather than crashing
  - Cost estimate surfaced in the UI: ~£0.006 / minute of audio
"""

import logging
from pathlib import Path
from typing import Optional

import httpx

log = logging.getLogger(__name__)

_WHISPER_URL = "https://api.openai.com/v1/audio/transcriptions"

# Audio uploads can be minutes long — Whisper processing scales with duration,
# so a generous timeout (not the 8s fail-fast used for identification calls).
_TIMEOUT_S = 120.0

# Best-effort content-type hints by extension (Whisper infers from the filename
# too, but an explicit type avoids ambiguity for webm/m4a).
_CONTENT_TYPES = {
    ".webm": "audio/webm",
    ".ogg":  "audio/ogg",
    ".mp3":  "audio/mpeg",
    ".m4a":  "audio/mp4",
    ".wav":  "audio/wav",
    ".mp4":  "audio/mp4",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpeg",
}


class WhisperError(Exception):
    """Transcription failed. `is_connection_error` flags offline/timeout cases."""
    def __init__(self, message: str, is_connection_error: bool = False):
        super().__init__(message)
        self.is_connection_error = is_connection_error


async def transcribe_file(
    file_path: str,
    api_key: str,
    model: str = "whisper-1",
) -> str:
    """
    Transcribe an audio file to text via OpenAI Whisper.

    Raises WhisperError on missing key, missing file, connection failure, or a
    non-2xx API response. Returns the transcript text (stripped) on success.
    """
    if not api_key:
        raise WhisperError("OpenAI API key not configured — add OPENAI_API_KEY in Settings")

    p = Path(file_path)
    if not p.exists():
        raise WhisperError(f"Audio file not found on disk: {p.name}")

    content_type = _CONTENT_TYPES.get(p.suffix.lower(), "application/octet-stream")
    log.info("[whisper] transcribe START file=%r model=%r size=%d", p.name, model, p.stat().st_size)

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            with p.open("rb") as fh:
                resp = await client.post(
                    _WHISPER_URL,
                    headers={"Authorization": f"Bearer {api_key}"},
                    files={"file": (p.name, fh, content_type)},
                    data={"model": model, "response_format": "json"},
                )
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.PoolTimeout) as e:
        log.error("[whisper] connection error: %s: %s", type(e).__name__, e)
        raise WhisperError("Could not reach OpenAI — check your connection", is_connection_error=True)
    except httpx.HTTPError as e:
        log.error("[whisper] HTTP error: %s: %s", type(e).__name__, e)
        raise WhisperError(f"Transcription request failed: {e}")

    if resp.status_code == 401:
        raise WhisperError("OpenAI rejected the API key (401) — check it in Settings")
    if resp.status_code == 429:
        raise WhisperError("OpenAI rate limit / quota exceeded (429)")
    if resp.status_code >= 400:
        detail = resp.text[:300]
        log.error("[whisper] API %d: %s", resp.status_code, detail)
        raise WhisperError(f"Whisper API error {resp.status_code}: {detail}")

    try:
        text = (resp.json().get("text") or "").strip()
    except Exception as e:
        raise WhisperError(f"Could not parse Whisper response: {e}")

    log.info("[whisper] transcribe OK file=%r chars=%d", p.name, len(text))
    return text
