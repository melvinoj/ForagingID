"""
identity.py — Token-based identity resolver for ForagingID.

Provides get_identity() as a FastAPI dependency returning an Identity dataclass.
Used by encounter scoping, curator-only guards, and the workshop token endpoints.

Batch 7: identity comes from app.services.access.resolve_access() — the same
decision the access middleware made for this request — never from the Host
header or a ?token= / Bearer value. A link token is only good for its one-time
/join; after that the device is identified by its session cookie.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.workshop import WorkshopParticipant
from app.services.access import resolve_access

log = logging.getLogger(__name__)


@dataclass
class Identity:
    user_id:             Optional[int]
    is_guest:            bool
    is_anonymous_guest:  bool
    workshop_session_id: Optional[int]


_ANON = dict(user_id=None, is_guest=True, is_anonymous_guest=True, workshop_session_id=None)


async def get_identity(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Identity:
    """
    Resolution (fail-closed — any lookup error returns anonymous guest):

    1. Localhost or a curator device → curator: user_id=1, is_guest=False.
    2. A participant device → participant: user_id=participant.id, is_guest=True
       (participant id 1 is the reserved tombstone → anonymous guest).
    3. Anything else → anonymous guest. (The middleware already refused it, so
       only routers mounted without the middleware, e.g. in tests, see this.)
    """
    acc = await resolve_access(request, db)
    if acc.tier == "curator":
        return Identity(user_id=1, is_guest=False, is_anonymous_guest=False,
                        workshop_session_id=acc.token.workshop_session_id if acc.token else None)
    if acc.tier == "guest" and acc.token is not None:
        try:
            participant = await db.get(WorkshopParticipant, acc.token.participant_id)
            if participant is not None and participant.id >= 2:
                return Identity(user_id=participant.id, is_guest=True, is_anonymous_guest=False,
                                workshop_session_id=acc.token.workshop_session_id)
        except Exception:
            log.exception("Participant lookup error — falling back to anonymous guest")
    return Identity(**_ANON)
