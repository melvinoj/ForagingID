"""
Deleted-hash ingest gate — single implementation, called by every ingest path.

WHY THIS EXISTS
    deleted_hashes records the sha256 of every observation a human permanently
    DELETEd (as distinct from rejected: reject keeps the row, delete removes it).
    Its whole purpose is to stop a later rescan of the source media re-ingesting
    a photo the user deliberately destroyed — passport pages, private photos.

    Until 17 July that guarantee was fictional on four of five ingest paths. The
    check lived only in syncthing.py (P1). Every other path — the P2 browser
    scan, the P2 upload, the folder-scan service, and _run_archive_scan (which
    is the DIGIERA archive rescan, i.e. the exact event the blacklist exists to
    prevent) — deduped on Observation.file_hash alone. Since DELETE removes the
    observations row, that check cannot match, and the photo re-ingests.

    A reflog walk over 21 distinct versions found the check has never existed on
    those paths in any recoverable commit. Not a regression — born incomplete,
    same shape as the review.html missing `else` and the _dual_agree bypass.

WHY A SHARED FUNCTION AND NOT FIVE INLINE CHECKS
    Five copies of a guard drift apart; that divergence is precisely the bug
    being fixed here. This module is the single place the rule is expressed.
    Each ingest path calls it at the point where the hash is known and before
    any row is written.

    Note honestly what this is NOT: a true chokepoint that all ingest funnels
    through does not exist — the five paths are independent and share no common
    row-writing function. Building one would mean restructuring ingest, which is
    out of scope here. This is one implementation with five call sites, which
    removes the drift surface without restructuring.

    A BEFORE INSERT trigger on observations was considered as a real chokepoint
    and rejected: it would raise an opaque exception instead of a clean, counted,
    logged skip, and hide a load-bearing rule outside the application code.

PERMANENCE
    deleted_hashes has no removal path — no endpoint, no service, nothing but a
    manual DELETE FROM. Blacklisting a hash is therefore a permanent foreclosure:
    that photo can never be ingested again by any path, from any source, forever.
    This gate is what makes that real, so a DELETE decision must be taken as final.

SCOPE
    Ingest gate only. Touches no identification, prefilter, routing, or edibility
    behaviour.
"""
from typing import Optional

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.observation import DeletedHash
from app.models.processing import ProcessingLog


async def blacklisted_skip(
    session,
    file_hash: Optional[str],
    source: str,
    path: str,
) -> bool:
    """
    Return True when file_hash is on the deleted-hash blacklist.

    When True the caller MUST NOT create an Observation row for this file and
    MUST NOT run prefilter or identification on it — the user destroyed this
    photo deliberately.

    session — the caller's open session, used for the lookup only. The lookup is
              an indexed equality hit on ix_deleted_hashes_file_hash (UNIQUE),
              so it is O(log n) and costs nothing at any realistic table size.

    The skip log is written in this function's OWN session and committed
    immediately, rather than added to the caller's. The five call sites have
    incompatible commit conventions — ingestion.py explicitly batches and does
    not commit, scan.py and upload.py exit their `async with` blocks without
    committing — so a log row added to the caller's session would be silently
    dropped on exactly the paths that matter. A silent skip is unacceptable
    here: this log is the only way anyone would ever learn the gate fired.

    Returns False for a falsy hash: a file whose hash could not be computed
    cannot be matched against the blacklist, and this gate does not invent a
    verdict it has no evidence for. Such a file proceeds to the caller's normal
    handling.
    """
    if not file_hash:
        return False

    hit = await session.scalar(
        select(DeletedHash).where(DeletedHash.file_hash == file_hash)
    )
    if hit is None:
        return False

    async with AsyncSessionLocal() as log_session:
        log_session.add(ProcessingLog(
            observation_id=None,   # no row exists, and none will — orphan log,
                                   # same pattern as the manual_delete audit row
            stage="ingest",
            status="skipped",
            message=(
                f"action=blacklisted_hash_skip source={source} "
                f"hash={file_hash[:16]} file={path} "
                f"original_observation_id={hit.original_observation_id} "
                f"deleted_at={hit.deleted_at} "
                "— permanently deleted by user; not re-ingested"
            ),
        ))
        await log_session.commit()

    return True
