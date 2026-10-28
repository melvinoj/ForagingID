"""
Phase 13.2 audit fix — revoke guest_tokens id=2.

Audit finding: token id=2 has participant_id=NULL, making identity.py resolve
it as a curator token (user_id=1, is_guest=False). This token was not minted
intentionally as a long-lived curator credential and should be inactive.

SQL applied (2026-06-13): UPDATE guest_tokens SET is_active=0 WHERE id=2
changed_by: curator_audit / phase13.2
"""
import logging
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "foragingid.db"


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    row = con.execute("SELECT id, is_active FROM guest_tokens WHERE id=2").fetchone()
    if row is None:
        log.info("guest_tokens id=2 does not exist — nothing to do")
        return
    if row[1] == 0:
        log.info("guest_tokens id=2 already inactive — idempotent, no change")
        return
    con.execute("UPDATE guest_tokens SET is_active=0 WHERE id=2")
    con.commit()
    log.info("changed_by=curator_audit: guest_tokens id=2 set is_active=0 (phase13.2 audit fix)")
    con.close()


if __name__ == "__main__":
    main()
    sys.exit(0)
