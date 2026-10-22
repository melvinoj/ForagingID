"""
Batch 7 (A-01 / A-03) — access is gated by the token layer (Melvin, 21 Oct 2026).

The REAL app (app.main.app: its access middleware, every router and mount) on a
throw-away DB. TestClient can't set the socket peer, so a tiny ASGI wrapper sets
scope["client"]; uvicorn's proxy-header rewrite is NOT applied, so an ngrok
request keeps peer 127.0.0.1 — the exact case that must never count as localhost.

  localhost      Host localhost, peer 127.0.0.1, no X-Forwarded-For   → curator
  ngrok          Host abc123.ngrok-free.app, peer 127.0.0.1, XFF, https
  LAN            Host 192.168.1.5:8000, peer 192.168.1.20, http

Run from project root:  python tests/test_batch7_access.py
"""
import asyncio
import os
import sys
import tempfile
from datetime import datetime, timedelta

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main as main  # noqa: E402
import app.api.sharing as sharing  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.models.workshop import GuestToken, WorkshopParticipant  # noqa: E402
from app.services.access import COOKIE_NAME, SIGNED_OUT_TEXT, hash_secret  # noqa: E402

NGROK = "abc123.ngrok-free.app"
TUNNEL = f"https://{NGROK}"
ASK = "Ask Melvin for a link"           # on the 401 page; the JSON detail is SIGNED_OUT_TEXT

# Pages, APIs and mounts that hold data — refused without a device.
DATA_URLS = ["/", "/map", "/species", "/settings", "/api/map/geojson", "/api/settings",
             "/api/species/", "/api/workshop/tokens", "/api/sharing/devices",
             "/uploads-files/x.jpg", "/thumbnails/x.jpg", "/sw.js"]


def _with_peer(asgi, ip):
    async def wrapped(scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope = dict(scope, client=(ip, 50000))
        await asgi(scope, receive, send)
    return wrapped


class Env:
    """Throw-away DB wired into the middleware and get_db."""
    def __init__(self):
        path = os.path.join(tempfile.mkdtemp(prefix="b7test_"), "t.db")
        Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
        self.eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
        self.S = async_sessionmaker(self.eng, expire_on_commit=False)
        self._old_sl = main.AsyncSessionLocal
        main.AsyncSessionLocal = self.S

        async def _get_db():
            async with self.S() as s:
                yield s
        main.app.dependency_overrides[get_db] = _get_db
        self._old_tunnel = sharing._tunnel_url
        sharing._tunnel_url = TUNNEL

    def close(self):
        main.AsyncSessionLocal = self._old_sl
        main.app.dependency_overrides.pop(get_db, None)
        sharing._tunnel_url = self._old_tunnel
        asyncio.run(self.eng.dispose())

    def run(self, coro):
        return asyncio.run(coro)

    def token_row(self, tid):
        async def q():
            async with self.S() as s:
                return await s.get(GuestToken, tid)
        return self.run(q())

    def add_participant_token(self, name="Alice", days=7):
        async def q():
            async with self.S() as s:
                if await s.get(WorkshopParticipant, 1) is None:
                    s.add(WorkshopParticipant(id=1, name="__reserved__"))
                p = WorkshopParticipant(name=name)
                s.add(p)
                await s.flush()
                t = GuestToken(token=f"part-{name}-{p.id}", participant_id=p.id,
                               expires_at=datetime.utcnow() + timedelta(days=days))
                s.add(t)
                await s.commit()
                return t.id, t.token
        return self.run(q())


def local():
    return TestClient(_with_peer(main.app, "127.0.0.1"), base_url="http://localhost:8000", follow_redirects=False)


def ngrok():
    c = TestClient(_with_peer(main.app, "127.0.0.1"), base_url=TUNNEL, follow_redirects=False)
    c.headers.update({"x-forwarded-for": "203.0.113.9", "x-forwarded-proto": "https"})
    return c


def lan():
    return TestClient(_with_peer(main.app, "192.168.1.20"), base_url="http://192.168.1.5:8000", follow_redirects=False)


def _assert_refused(c, urls=DATA_URLS, **kw):
    for u in urls:
        r = c.get(u, **kw)
        assert r.status_code == 401, (u, r.status_code, r.text[:200])
        assert r.json() == {"detail": SIGNED_OUT_TEXT}, (u, r.text)        # fetch(): JSON
        if not u.startswith("/api/"):                                    # a browser navigation: the page
            nav = {k: v for k, v in kw.items() if k != "headers"}
            r = c.get(u, headers={**kw.get("headers", {}), "accept": "text/html"}, **nav)
            assert r.status_code == 401 and ASK in r.text and "<script" not in r.text.lower(), u
    r = c.post("/api/observations/1/review?status=approved", **kw)
    assert r.status_code == 401, r.status_code


def _add_device(env, name="Melvin's phone"):
    r = local().post("/api/sharing/devices", json={"name": name})
    assert r.status_code == 201, r.text
    d = r.json()
    assert d["join_url"].startswith(TUNNEL + "/join/") and d["qr_data_url"].startswith("data:image/png;base64,")
    assert "token" not in d and "session_hash" not in d
    return d


def _join(c, join_url_or_path):
    path = join_url_or_path.replace(TUNNEL, "")
    return c.get(path)


# ── no token ────────────────────────────────────────────────────────────────

def test_ngrok_without_a_token_is_refused_on_pages_apis_and_files():
    env = Env()
    try:
        _assert_refused(ngrok())
    finally:
        env.close()


def test_lan_without_a_token_is_refused():
    env = Env()
    try:
        _assert_refused(lan())
        # A LAN device claiming Host: localhost (A-03) is still not the laptop.
        c = TestClient(_with_peer(main.app, "192.168.1.20"), base_url="http://localhost:8000", follow_redirects=False)
        _assert_refused(c)
        # Loopback peer + localhost Host but forwarded (the ngrok agent path).
        c = TestClient(_with_peer(main.app, "127.0.0.1"), base_url="http://localhost:8000", follow_redirects=False)
        _assert_refused(c, headers={"x-forwarded-for": "203.0.113.9"})
    finally:
        env.close()


def test_unknown_host_is_forbidden():
    env = Env()
    try:
        c = TestClient(_with_peer(main.app, "127.0.0.1"), base_url="https://evil.example.com", follow_redirects=False)
        assert c.get("/api/settings").status_code == 403
    finally:
        env.close()


def test_localhost_works_without_a_token():
    env = Env()
    try:
        c = local()
        for u in ["/", "/settings", "/api/settings", "/api/sharing/devices", "/api/map/geojson"]:
            r = c.get(u)
            assert r.status_code == 200, (u, r.status_code, r.text[:200])
        me = c.get("/api/me").json()
        assert me["is_guest"] is False and me["is_local"] is True
    finally:
        env.close()


def test_url_and_bearer_tokens_are_no_longer_credentials():
    env = Env()
    try:
        _, raw = env.add_participant_token()
        c = ngrok()
        assert c.get(f"/api/settings?token={raw}").status_code == 401
        assert c.get("/api/map/geojson", headers={"authorization": f"Bearer {raw}"}).status_code == 401
        assert c.get(f"/?token={raw}").status_code == 401
    finally:
        env.close()


# ── curator devices ─────────────────────────────────────────────────────────

def test_curator_device_join_sets_cookie_cleans_url_and_gets_full_access():
    env = Env()
    try:
        d = _add_device(env)
        c = ngrok()
        r = _join(c, d["join_url"])
        assert r.status_code == 303 and r.headers["location"] == "/", (r.status_code, r.headers)
        sc = r.headers["set-cookie"].lower()
        assert sc.startswith(COOKIE_NAME + "=") and "httponly" in sc and "secure" in sc and "samesite=lax" in sc
        tok = d["join_url"].rsplit("/", 1)[1]
        assert tok not in r.headers["location"] and tok not in r.headers["set-cookie"]
        # The cookie is not the link token, and the DB keeps only its hash.
        secret = c.cookies.get(COOKIE_NAME)
        row = env.token_row(d["id"])
        assert secret and secret != tok and row.session_hash == hash_secret(secret) and row.claimed_at
        # Full curator access over ngrok.
        for u in ["/", "/settings", "/api/settings", "/api/sharing/devices", "/api/workshop/tokens"]:
            assert c.get(u).status_code == 200, u
        assert c.get("/api/me").json()["is_guest"] is False
        # Following the redirect ends on a clean URL.
        r = TestClient(_with_peer(main.app, "127.0.0.1"), base_url=TUNNEL)
        r.headers.update({"x-forwarded-for": "203.0.113.9"})
        d2 = _add_device(env, "second")
        final = r.get(d2["join_url"].replace(TUNNEL, ""))
        assert final.status_code == 200 and str(final.url) == TUNNEL + "/", final.url
    finally:
        env.close()


def test_a_used_join_link_cannot_be_used_again():
    env = Env()
    try:
        d = _add_device(env)
        assert _join(ngrok(), d["join_url"]).status_code == 303
        other = ngrok()                                  # a second device with the same link
        r = _join(other, d["join_url"])
        assert r.status_code == 410 and "already used" in r.text and "set-cookie" not in r.headers
        assert other.get("/api/settings").status_code == 401
        assert _join(ngrok(), TUNNEL + "/join/not-a-real-token").status_code == 404
    finally:
        env.close()


def test_curator_device_is_https_only():
    env = Env()
    try:
        d = _add_device(env)
        # The /join link for a curator device does nothing over plain http (LAN).
        r = lan().get(d["join_url"].replace(TUNNEL, ""))
        assert r.status_code == 403 and "set-cookie" not in r.headers
        assert env.token_row(d["id"]).claimed_at is None          # link still unused
        # Joined over https; the same cookie copied to plain-http LAN is refused.
        c = ngrok()
        assert _join(c, d["join_url"]).status_code == 303
        secret = c.cookies.get(COOKIE_NAME)
        _assert_refused(lan(), urls=["/", "/api/settings"], cookies={COOKIE_NAME: secret})
    finally:
        env.close()


def test_curator_device_lists_and_revokes_but_cannot_create_links():
    env = Env()
    try:
        phone = _add_device(env, "phone")
        tablet = _add_device(env, "tablet")
        c = ngrok()
        assert _join(c, phone["join_url"]).status_code == 303
        r = c.post("/api/sharing/devices", json={"name": "sneaky"})
        assert r.status_code == 403, r.text
        r = c.post("/api/workshop/tokens", json={"participant_id": None})
        assert r.status_code == 422, r.text                      # no second curator-minting path
        rows = c.get("/api/sharing/devices").json()
        assert [x["name"] for x in rows] == ["phone", "tablet"]
        assert all("token" not in x for x in rows)
        assert all(x["participant_id"] is not None for x in c.get("/api/workshop/tokens").json())
        assert c.post(f"/api/sharing/devices/{tablet['id']}/revoke").status_code == 200
        assert env.token_row(tablet["id"]).is_active is False
        # Even localhost can't mint a curator token through the workshop endpoint.
        assert local().post("/api/workshop/tokens", json={"participant_id": None}).status_code == 422
    finally:
        env.close()


def test_revoked_curator_device_is_refused_at_once():
    env = Env()
    try:
        d = _add_device(env)
        c = ngrok()
        assert _join(c, d["join_url"]).status_code == 303
        assert c.get("/api/settings").status_code == 200
        assert local().post(f"/api/sharing/devices/{d['id']}/revoke").status_code == 200
        _assert_refused(c, urls=["/", "/api/settings", "/api/map/geojson"])
    finally:
        env.close()


def test_last_used_is_recorded():
    env = Env()
    try:
        d = _add_device(env)
        c = ngrok()
        _join(c, d["join_url"])

        async def age():
            async with env.S() as s:
                t = await s.get(GuestToken, d["id"])
                t.last_used_at = datetime.utcnow() - timedelta(hours=1)
                await s.commit()
        env.run(age())
        r = c.get("/api/map/geojson")
        assert r.status_code == 200 and COOKIE_NAME in r.headers.get("set-cookie", "")   # Max-Age refreshed
        assert datetime.utcnow() - env.token_row(d["id"]).last_used_at < timedelta(minutes=1)
    finally:
        env.close()


# ── participants ────────────────────────────────────────────────────────────

def test_participant_token_gets_guest_access_only():
    env = Env()
    try:
        tid, raw = env.add_participant_token()
        c = ngrok()
        r = c.get(f"/join/{raw}?next=/encounters")
        assert r.status_code == 303 and r.headers["location"] == "/encounters"
        assert "secure" in r.headers["set-cookie"].lower()
        assert c.get("/api/me").json()["is_guest"] is True
        assert c.get("/api/map/geojson").status_code == 200          # guest reads (batch 8 scopes them)
        assert c.get("/api/settings").status_code == 403             # curator-only
        assert c.get("/api/sharing/devices").status_code == 403
        assert c.get("/settings").status_code == 302                 # guest-blocked page
        r = c.get("/")
        with open(os.path.join(ROOT, "frontend/landing.html"), encoding="utf-8") as f:
            assert r.status_code == 200 and r.text == f.read()          # guest landing page, not the map
        assert c.post("/api/observations/1/review?status=approved").status_code == 403   # read-only
        assert _join(ngrok(), f"/join/{raw}").status_code == 410
    finally:
        env.close()


def test_participant_cookie_works_on_lan_http_without_secure():
    env = Env()
    try:
        _, raw = env.add_participant_token("Bob")
        c = lan()
        r = c.get(f"/join/{raw}")
        assert r.status_code == 303
        sc = r.headers["set-cookie"].lower()
        assert "httponly" in sc and "secure" not in sc and "samesite=lax" in sc
        assert c.get("/api/me").json()["is_guest"] is True
        assert c.get("/api/settings").status_code == 403
    finally:
        env.close()


def test_expired_participant_is_refused():
    env = Env()
    try:
        tid, raw = env.add_participant_token("Carol")
        c = ngrok()
        assert _join(c, f"/join/{raw}").status_code == 303

        async def expire():
            async with env.S() as s:
                (await s.get(GuestToken, tid)).expires_at = datetime.utcnow() - timedelta(seconds=1)
                await s.commit()
        env.run(expire())
        assert c.get("/api/map/geojson").status_code == 401
    finally:
        env.close()


def test_join_next_is_same_site_only():
    env = Env()
    try:
        for nxt, want in [("//evil.example.com/x", "/"), ("https://evil.example.com", "/"), ("/species?s=A", "/species?s=A")]:
            _, raw = env.add_participant_token(f"N{abs(hash(nxt)) % 10000}")
            r = ngrok().get(f"/join/{raw}", params={"next": nxt})
            assert r.status_code == 303 and r.headers["location"] == want, (nxt, r.headers.get("location"))
    finally:
        env.close()


def test_no_token_paths_hold_no_data():
    env = Env()
    try:
        c = ngrok()
        assert c.get("/static/manifest.json").status_code == 200
        assert c.get("/static/js/safety-gate.js").status_code == 401
    finally:
        env.close()


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok", _name)
