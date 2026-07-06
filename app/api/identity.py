"""
identity.py — Token-based identity resolver for ForagingID.

Provides get_identity() as a FastAPI dependency returning an Identity dataclass.
Used by encounter scoping, curator-only guards, and the workshop token endpoints.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.sharing import is_guest_request
from app.models.workshop import GuestToken, WorkshopParticipant

log = logging.getLogger(__name__)


@dataclass
class Identity:
    user_id:             Optional[int]
    is_guest:            bool
    is_anonymous_guest:  bool
    workshop_session_id: Optional[int]


def _extract_token(request: Request) -> Optional[str]:
    """Pull token from ?token= query param or Authorization: Bearer header."""
    t = request.query_params.get("token")
    if t:
        return t.strip()
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        t = auth[7:].strip()
        if t:
            return t
    return None


async def get_identity(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Identity:
    """
    Resolution order (fail-closed — any lookup error returns anonymous guest):

    1. Valid token (is_active=True, not expired):
       - participant_id NULL  → curator token: user_id=1, is_guest=False
       - participant_id set   → participant:   user_id=participant.id, is_guest=True
       Invalid/expired/missing token when a token string IS present → anonymous guest.

    2. No token + ngrok host → anonymous guest.
    3. No token + not ngrok  → curator (localhost): user_id=1, is_guest=False.
    """
    raw_token = _extract_token(request)
    if raw_token:
        try:
            row = await db.scalar(
                select(GuestToken).where(
                    GuestToken.token == raw_token,
                    GuestToken.is_active.is_(True),
                    GuestToken.expires_at > datetime.utcnow(),
                )
            )
            if row is not None:
                if row.participant_id is None:
                    return Identity(
                        user_id=1,
                        is_guest=False,
                        is_anonymous_guest=False,
                        workshop_session_id=row.workshop_session_id,
                    )
                participant = await db.get(WorkshopParticipant, row.participant_id)
                if participant is not None and participant.id >= 2:
                    return Identity(
                        user_id=participant.id,
                        is_guest=True,
                        is_anonymous_guest=False,
                        workshop_session_id=row.workshop_session_id,
                    )
                # participant_id=1 (tombstone) or missing → treat as anonymous guest
        except Exception:
            log.exception("Token lookup error — falling back to anonymous guest")
        # Token present but not valid (expired, inactive, not found, or lookup error).
        return Identity(user_id=None, is_guest=True, is_anonymous_guest=True, workshop_session_id=None)

    if is_guest_request(request):
        return Identity(user_id=None, is_guest=True, is_anonymous_guest=True, workshop_session_id=None)

    return Identity(user_id=1, is_guest=False, is_anonymous_guest=False, workshop_session_id=None)
