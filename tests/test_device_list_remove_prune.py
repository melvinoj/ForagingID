"""
Settings → device list: ✕ on every entry + auto-prune of dead entries
(Melvin, 28 Oct 2026).

  ✕ on a live paired device   → revoke + remove (the row is deleted; its cookie
                                matches nothing on the next request)
  ✕ on a revoked device or an
    unused pairing link       → delete the leftover entry
  prune (every list load)     → revoked devices, and pairing links unused after
                                7 days. Never a paired device for being offline.

Reuses the batch 7 harness (real app, throw-away DB).
Run from project root:  python tests/test_device_list_remove_prune.py
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from test_batch7_access import Env, _add_device, _assert_refused, _join, local, ngrok  # noqa: E402
from app.models.workshop import GuestToken, WorkshopParticipant  # noqa: E402


def _insert(env, **kw):
    async def q():
        async with env.S() as s:
            t = GuestToken(**kw)
            s.add(t)
            await s.commit()
            return t.id
    return env.run(q())


def test_x_on_a_live_paired_device_revokes_and_removes_it():
    env = Env()
    try:
        d = _add_device(env, "phone")
        c = ngrok()
        assert _join(c, d["join_url"]).status_code == 303
        assert c.get("/api/settings").status_code == 200
        r = local().delete(f"/api/sharing/devices/{d['id']}")
        assert r.status_code == 200 and r.json() == {"id": d["id"], "removed": "revoked"}, r.text
        assert env.token_row(d["id"]) is None
        _assert_refused(c, urls=["/", "/api/settings", "/api/map/geojson"])
        assert local().get("/api/sharing/devices").json() == []
    finally:
        env.close()


def test_x_on_a_leftover_entry_deletes_it():
    env = Env()
    try:
        unused = _add_device(env, "never opened")
        revoked = _add_device(env, "old phone")
        keep = _add_device(env, "tablet")
        assert _join(ngrok(), revoked["join_url"]).status_code == 303
        assert local().post(f"/api/sharing/devices/{revoked['id']}/revoke").status_code == 200
        for d in (unused, revoked):
            r = local().delete(f"/api/sharing/devices/{d['id']}")
            assert r.status_code == 200 and r.json()["removed"] == "deleted", r.text
            assert env.token_row(d["id"]) is None
        assert [x["name"] for x in local().get("/api/sharing/devices").json()] == ["tablet"]
        assert env.token_row(keep["id"]) is not None
        assert local().delete(f"/api/sharing/devices/{unused['id']}").status_code == 404
    finally:
        env.close()


def test_prune_removes_only_dead_entries_and_keeps_an_offline_paired_device():
    env = Env()
    try:
        now = datetime.utcnow()
        long_ago = now - timedelta(days=90)
        offline = _insert(env, token="t-offline", name="offline phone", is_active=True,
                          created_at=long_ago, claimed_at=long_ago, last_used_at=long_ago,
                          session_hash="h-offline")
        never_used_pair = _insert(env, token="t-paired-idle", name="paired, never used since",
                                  is_active=True, created_at=long_ago, claimed_at=long_ago,
                                  session_hash="h-idle")
        fresh_link = _insert(env, token="t-fresh", name="fresh link", is_active=True,
                             created_at=now - timedelta(days=6))
        stale_link = _insert(env, token="t-stale", name="stale link", is_active=True,
                             created_at=now - timedelta(days=8))
        revoked = _insert(env, token="t-revoked", name="revoked", is_active=False,
                          created_at=now - timedelta(days=1), claimed_at=now - timedelta(days=1),
                          session_hash="h-revoked")
        revoked_link = _insert(env, token="t-revoked-link", name="revoked link", is_active=False,
                               created_at=now)

        async def part():
            async with env.S() as s:
                p = WorkshopParticipant(name="Alice")
                s.add(p)
                await s.flush()
                t = GuestToken(token="t-part", participant_id=p.id, is_active=False,
                               created_at=long_ago, expires_at=long_ago)
                s.add(t)
                await s.commit()
                return t.id
        participant = env.run(part())

        rows = local().get("/api/sharing/devices").json()
        assert sorted(x["id"] for x in rows) == sorted([offline, never_used_pair, fresh_link]), rows
        for gone in (stale_link, revoked, revoked_link):
            assert env.token_row(gone) is None, gone
        for kept in (offline, never_used_pair, fresh_link):
            row = env.token_row(kept)
            assert row is not None and row.is_active is True, kept
        # Workshop participant tokens are not curator devices: never pruned here.
        assert env.token_row(participant) is not None
        # A second load prunes nothing more.
        assert len(local().get("/api/sharing/devices").json()) == 3
    finally:
        env.close()


def test_delete_is_curator_only_and_never_touches_participant_tokens():
    env = Env()
    try:
        d = _add_device(env, "phone")
        pid, raw = env.add_participant_token("Bob")
        guest = ngrok()
        assert _join(guest, "/join/" + raw).status_code == 303
        assert guest.delete(f"/api/sharing/devices/{d['id']}").status_code == 403
        assert env.token_row(d["id"]) is not None
        assert local().delete(f"/api/sharing/devices/{pid}").status_code == 404
        assert env.token_row(pid) is not None
    finally:
        env.close()


def test_settings_page_uses_the_in_app_confirm_not_a_browser_dialog():
    root = os.path.join(os.path.dirname(__file__), "..")
    src = open(os.path.join(root, "frontend", "settings.html"), encoding="utf-8").read()
    start = src.index("async function loadDevices()")
    end = src.index("async function confirmRemoveDevice()")
    end = src.index("\n}\n", end)
    block = src[start:end]
    assert "askRemoveDevice(" in block and "✕" in block
    assert "confirm(" not in block.replace("askRemoveDevice", "").replace("Confirm", "").replace("confirmRemove", "").replace("device-confirm", "")
    assert "method: 'DELETE'" in block
    assert 'id="device-confirm"' in src
    assert "revokeDevice" not in src


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok", _name)
