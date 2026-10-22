"""
access.py — who may reach the app, decided once per request (batch 7, A-01 / A-03).

Three layers (Melvin, 21 Oct 2026):
  1. Localhost (the laptop): curator, no token.
  2. Curator device: a long-lived guest_tokens row with participant_id NULL,
     signed in by its one-time /join link. Curator access, over https only.
  3. Participant: a 13.1 workshop token (participant_id set). Guest access.
Anything else — LAN or ngrok without a valid device cookie — gets the "Ask
Melvin for a link" page and no data.

resolve_access() is the ONLY place this is decided. The middleware in main.py
calls it for every request; get_identity() reads the same result (cached on
request.state), so the two can never disagree.
"""
import hashlib
import ipaddress
import logging
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workshop import GuestToken, is_curator_token, token_is_live

log = logging.getLogger(__name__)

COOKIE_NAME = "lm_device"
# Browsers cap cookie lifetime at about 400 days; the cookie is re-sent with a
# fresh Max-Age whenever last_used_at is refreshed, so a device in use stays in.
COOKIE_MAX_AGE = 400 * 24 * 3600
LAST_USED_EVERY = timedelta(minutes=5)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass
class Access:
    tier: Optional[str]              # 'curator' | 'guest' | None (no access)
    token: Optional[GuestToken] = None
    local: bool = False

    @property
    def is_curator_device(self) -> bool:
        return self.token is not None and is_curator_token(self.token)


def host_only(request: Request) -> str:
    """Lowercased Host header with any port stripped (handles IPv6 ``[::1]:8001``)."""
    host = (request.headers.get("host", "") or "").split(",")[0].strip().lower()
    if host.startswith("["):
        end = host.find("]")
        return host[1:end] if end != -1 else host
    if ":" in host:
        return host.rsplit(":", 1)[0]
    return host


def _peer_is_loopback(request: Request) -> bool:
    client = request.scope.get("client")
    if not client:
        return False
    try:
        return ipaddress.ip_address(client[0]).is_loopback
    except ValueError:
        return False


def is_local_request(request: Request) -> bool:
    """The laptop itself: a local Host AND a loopback peer AND no X-Forwarded-For.

    Host alone is forgeable by any LAN device (A-03). ngrok traffic arrives from
    127.0.0.1 but carries the ngrok Host and an X-Forwarded-For header, so it
    can never pass. (uvicorn rewrites the peer from X-Forwarded-For only for
    requests from 127.0.0.1, which the header check already refuses.)"""
    return (host_only(request) in _LOCAL_HOSTS
            and _peer_is_loopback(request)
            and "x-forwarded-for" not in request.headers)


def is_https(request: Request) -> bool:
    # uvicorn sets the scheme from X-Forwarded-Proto for the local ngrok agent only.
    return request.url.scheme == "https"


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def new_session_secret() -> str:
    return secrets.token_urlsafe(32)


async def resolve_access(request: Request, db: AsyncSession) -> Access:
    """Decide this request's access once; cached on request.state."""
    cached = getattr(request.state, "access", None)
    if cached is not None:
        return cached
    if is_local_request(request):
        acc = Access("curator", local=True)
    else:
        acc = Access(None)
        secret = request.cookies.get(COOKIE_NAME)
        if secret:
            try:
                tok = await db.scalar(select(GuestToken).where(GuestToken.session_hash == hash_secret(secret)))
            except Exception:
                log.exception("Device session lookup failed — refusing")
                tok = None
            if tok is not None and token_is_live(tok):
                if is_curator_token(tok):
                    # Curator devices are https-only: a copied cookie on plain-http
                    # LAN gives nothing.
                    if is_https(request):
                        acc = Access("curator", token=tok)
                else:
                    acc = Access("guest", token=tok)
    request.state.access = acc
    return acc


def cookie_kwargs(request: Request, tok: GuestToken) -> dict:
    """Set-Cookie options for a device session. Secure on https; participant
    cookies may also live on plain-http LAN (guest access only)."""
    max_age = COOKIE_MAX_AGE
    if tok.expires_at is not None:
        max_age = max(0, min(max_age, int((tok.expires_at - datetime.utcnow()).total_seconds())))
    return dict(key=COOKIE_NAME, max_age=max_age, httponly=True, samesite="lax",
                secure=is_https(request), path="/")


def needs_last_used_update(tok: GuestToken, now: Optional[datetime] = None) -> bool:
    now = now or datetime.utcnow()
    return tok.last_used_at is None or now - tok.last_used_at >= LAST_USED_EVERY


def message_page(title: str, body: str) -> str:
    """A small self-contained page for refusals and /join results. Constant
    text only — never request data."""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>LandMemory</title>
<style>
  body {{ margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
         background:#f6f8f1; color:#1f2a14; font:16px/1.5 -apple-system, system-ui, sans-serif; }}
  main {{ max-width:420px; margin:24px 16px; padding:28px 24px; background:#fff;
         border:1px solid #dfe8cf; border-radius:12px; text-align:center; }}
  h1 {{ font-size:1.25rem; margin:0 0 10px; color:#2d5016; }}
  p {{ margin:0; color:#4b5640; }}
</style></head>
<body><main><h1>🌿 {title}</h1><p>{body}</p></main></body></html>"""


# The ONLY wording for "no valid device / participant cookie" (Melvin, 21 Oct
# 2026). The 401 page and the 401 JSON carry it; offline.js and the outbox
# show the server's `detail` (their fallback copies are test-checked equal).
SIGNED_OUT_TEXT = "This device isn't signed in — ask Melvin for a link"

ASK_PAGE = message_page("This device isn't signed in", "Ask Melvin for a link.")
