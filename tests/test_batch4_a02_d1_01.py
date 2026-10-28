"""
Tests for batch 4 (audit REPORT section 9, 21 Oct 2026):

A-02  GET /api/settings returned the DeepSeek key to any reader, guests included.
      Now: no secret value in any settings response (only is_set), and every
      /api/settings route refuses a guest identity (host or token).
      A-04 (25 Oct 2026): the key comes from the environment / .env only — a
      DeepSeek row left in app_settings is ignored; Settings writes .env.
D1-01 POST /api/lists/pdf rendered request text as live HTML (autoescape off)
      and WeasyPrint fetched any local file. Now: autoescape on (|safe only for
      _season_str / _mdlite), and a url_fetcher limited to data: URIs and files
      under frontend/static, media, photos, uploads.

No external calls. Throw-away SQLite DB. The PDF tests need WeasyPrint's native
libraries; run standalone, the file re-executes itself with
DYLD_LIBRARY_PATH=/opt/homebrew/lib (macOS reads it only at process start).

Run from project root:  python tests/test_batch4_a02_d1_01.py
"""

import os
import sys

if __name__ == "__main__" and "DYLD_LIBRARY_PATH" not in os.environ:
    os.execve(sys.executable, [sys.executable] + sys.argv,
              {**os.environ, "DYLD_LIBRARY_PATH": "/opt/homebrew/lib"})

import asyncio  # noqa: E402
import io  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.main  # noqa: E402,F401  (registers every model on Base.metadata)
import app.api.lists_pdf as lp  # noqa: E402
import app.api.settings as settings_api  # noqa: E402
import app.services.settings_service as ss  # noqa: E402
from app.config import settings as cfg  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.models.settings import AppSetting  # noqa: E402
from app.models.species import safety_decision  # noqa: E402

PROJECT = Path(ROOT).resolve()

# Sentinel secrets — distinct, greppable, never real.
DEEPSEEK = "sk-A02-DEEPSEEK-SENTINEL-1111"
GDRIVE = "ya29.A02-GDRIVE-SENTINEL-2222"
CFG_SECRETS = {
    "plantnet_api_key":      "A02-PLANTNET-SENTINEL-3333",
    "inaturalist_api_token": "eyJA02.INAT-SENTINEL.4444",
    "ors_api_key":           "A02-ORS-SENTINEL-5555",
    "thunderforest_api_key": "A02-THUNDERFOREST-SENTINEL-6666",
    "openai_api_key":        "sk-A02-OPENAI-SENTINEL-7777",
    "anthropic_api_key":     "sk-ant-A02-ANTHROPIC-SENTINEL-8888",
    "deepseek_api_key":      DEEPSEEK,           # A-04: from the environment, like the rest
}
ALL_SECRETS = [GDRIVE, *CFG_SECRETS.values()]


# ── A-02 ──────────────────────────────────────────────────────────────────────

def _client():
    """The real settings router (with its curator dependency and the real
    get_identity) on a throw-away DB holding a DeepSeek key and a Drive token —
    stale rows the app must never read (A-04)."""
    path = os.path.join(tempfile.mkdtemp(prefix="a02test_"), "t.db")
    Base.metadata.create_all(create_engine(f"sqlite:///{path}"))
    eng = create_async_engine(f"sqlite+aiosqlite:///{path}")
    S = async_sessionmaker(eng, expire_on_commit=False)

    async def seed():
        async with S() as s:
            s.add(AppSetting(key="deepseek_api_key", value=DEEPSEEK, updated_by="human"))
            s.add(AppSetting(key="gdrive_access_token", value=GDRIVE, updated_by="human"))
            s.add(AppSetting(key="min_identification_confidence", value="0.3", updated_by="human"))
            await s.commit()
        async with S() as s:
            await ss.load_settings_from_db(s)
    asyncio.run(seed())

    async def _get_db():
        async with S() as s:
            yield s

    api = FastAPI()
    api.include_router(settings_api.router)
    api.dependency_overrides[get_db] = _get_db
    return TestClient(_with_peer(api, "127.0.0.1"))


def _with_peer(asgi, ip):
    """TestClient's peer is 'testclient'; batch 7 decides localhost by the socket
    peer too, so set it (as uvicorn does for a request from the laptop)."""
    async def wrapped(scope, receive, send):
        if scope["type"] == "http":
            scope = dict(scope, client=(ip, 50000))
        await asgi(scope, receive, send)
    return wrapped


class _CfgSecrets:
    """Put sentinel values on the config object for the duration of a test."""
    def __enter__(self):
        self.old = {k: getattr(cfg, k, None) for k in CFG_SECRETS}
        for k, v in CFG_SECRETS.items():
            object.__setattr__(cfg, k, v)
    def __exit__(self, *exc):
        for k, v in self.old.items():
            object.__setattr__(cfg, k, v)


def _assert_no_secret(text, where):
    for s in ALL_SECRETS:
        assert s not in text, f"{where} leaks {s}"
        assert s[-8:] not in text, f"{where} leaks the tail of {s}"


def test_settings_list_returns_no_secret_value_only_is_set():
    c = _client()
    with _CfgSecrets():
        r = c.get("/api/settings", headers={"host": "localhost:8000"})
        assert r.status_code == 200
        _assert_no_secret(r.text, "GET /api/settings")
        rows = {e["key"]: e for e in r.json()["settings"]}
        ds = rows["deepseek_api_key"]
        assert ds["is_set"] is True and ds["secret"] is True
        assert ds["current_value"] is None and ds["default_value"] is None and ds["db_raw"] is None
        assert "default" not in ds
        assert ds["overridden"] is False          # A-04: a secret is never a DB override
        # Non-secret settings are untouched.
        assert rows["min_identification_confidence"]["current_value"] == 0.3
        assert rows["min_identification_confidence"]["db_raw"] == "0.3"
        # Every secret-bearing registry entry is flagged secret (only DeepSeek is
        # stored in the registry; the others live in .env / config).
        assert [k for k, e in rows.items() if e.get("secret")] == ["deepseek_api_key"]

        r = c.get("/api/settings/api-meta", headers={"host": "localhost:8000"})
        assert r.status_code == 200
        _assert_no_secret(r.text, "GET /api/settings/api-meta")


def test_unset_secret_reports_is_set_false():
    """No key in the environment → not set, though the DB still holds a row (A-04)."""
    c = _client()
    old = cfg.deepseek_api_key
    object.__setattr__(cfg, "deepseek_api_key", "")
    try:
        r = c.get("/api/settings", headers={"host": "localhost"})
        ds = next(e for e in r.json()["settings"] if e["key"] == "deepseek_api_key")
        assert ds["is_set"] is False and ds["current_value"] is None
    finally:
        object.__setattr__(cfg, "deepseek_api_key", old)


def test_put_and_delete_never_echo_the_secret():
    import app.config as config_mod
    c = _client()
    tmp_env = Path(tempfile.mkdtemp(prefix="a02env_")) / ".env"      # never the real .env
    old_env, old_key = config_mod.ENV_FILE, cfg.deepseek_api_key
    config_mod.ENV_FILE = tmp_env
    try:
        r = c.put("/api/settings/deepseek_api_key", json={"value": DEEPSEEK + "-NEW"},
                  headers={"host": "localhost"})
        assert r.status_code == 200 and r.json()["value"] is None
        assert DEEPSEEK not in r.text
        assert ss.get_setting("deepseek_api_key") == DEEPSEEK + "-NEW"        # saved — to .env
        assert tmp_env.read_text() == f"DEEPSEEK_API_KEY={DEEPSEEK}-NEW\n"
        r = c.get("/api/settings", headers={"host": "localhost"})
        assert DEEPSEEK not in r.text
        r = c.delete("/api/settings/deepseek_api_key", headers={"host": "localhost"})
        assert r.status_code == 200 and r.json()["value"] is None
        assert tmp_env.read_text() == "DEEPSEEK_API_KEY=\n"
    finally:
        config_mod.ENV_FILE = old_env
        object.__setattr__(cfg, "deepseek_api_key", old_key)
    # A normal setting still echoes its value.
    r = c.put("/api/settings/min_identification_confidence", json={"value": 0.4},
              headers={"host": "localhost"})
    assert r.json()["value"] == 0.4


def test_guest_host_gets_403_on_every_settings_route():
    """An ngrok request with no curator device is a guest identity (batch 7:
    the guest-mode switch is gone; the token decides)."""
    c = _client()
    h = {"host": "abc123.ngrok-free.app", "x-forwarded-for": "203.0.113.9"}
    for method, url in [
        ("GET", "/api/settings"),
        ("GET", "/api/settings/api-meta"),
        ("GET", "/api/settings/api-status"),
        ("GET", "/api/settings/api-status/plantnet"),
        ("GET", "/api/settings/synthesis-sources"),
        ("PUT", "/api/settings/min_identification_confidence"),
        ("DELETE", "/api/settings/min_identification_confidence"),
        ("POST", "/api/settings/api-key"),
        ("POST", "/api/settings/synthesis-sources"),
        ("DELETE", "/api/settings/synthesis-sources/example.com"),
    ]:
        r = c.request(method, url, headers=h, json={"value": 1, "api": "x", "key": "y"})
        assert r.status_code == 403, (method, url, r.status_code)
        _assert_no_secret(r.text, url)


def test_url_and_bearer_tokens_grant_nothing():
    """Batch 7: a ?token= / Bearer value is never a credential (only a /join
    device cookie is). Off localhost it stays a guest; on localhost it is ignored."""
    c = _client()
    ngrok = {"host": "abc123.ngrok-free.app", "x-forwarded-for": "203.0.113.9"}
    r = c.get("/api/settings", headers={**ngrok, "authorization": "Bearer not-a-real-token"})
    assert r.status_code == 403
    r = c.get("/api/settings?token=not-a-real-token", headers=ngrok)
    assert r.status_code == 403
    r = c.get("/api/settings?token=not-a-real-token", headers={"host": "localhost"})
    assert r.status_code == 200


def test_curator_sees_set_not_set_and_lan_or_ngrok_without_a_device_do_not():
    c = _client()
    with _CfgSecrets():
        r = c.get("/api/settings", headers={"host": "localhost"})
    assert r.status_code == 200
    ds = next(e for e in r.json()["settings"] if e["key"] == "deepseek_api_key")
    assert ds["is_set"] is True
    for h in ({"host": "192.168.1.20:8000"},          # the laptop's own LAN address is not localhost
              {"host": "abc123.ngrok-free.app", "x-forwarded-for": "203.0.113.9"}):
        r = c.get("/api/settings", headers=h)
        assert r.status_code == 403, h
        _assert_no_secret(r.text, "/api/settings")


def test_frontend_never_reads_a_secret_value():
    for rel in ("frontend/settings.html", "frontend/scan.html", "frontend/index.html"):
        src = (PROJECT / rel).read_text()
        if rel == "frontend/index.html":   # batch 16: split page, read re-inlined
            from index_source import index_source
            src = index_source()
        assert "deepseek_api_key" not in src, rel


# ── D1-01 ─────────────────────────────────────────────────────────────────────

HOSTILE = ('<script>alert(1)</script> <img src="file:///etc/passwd"> '
           '<b>bold</b> & more')


def _profile(id_notes=HOSTILE, recipe_body="# <img src=x>Head\n\nStep <i>one</i> **well**"):
    return {
        "species": {"common_names": ["<b>Ramsons</b>"], "edibility_status": "edible",
                    "toxicity_severity": "none", "phenology": {"flower": [4, 5]}},
        "culinary": {"id_notes": id_notes, "look_alike_warnings": HOSTILE,
                     "preparation_warnings": HOSTILE, "edible_parts": HOSTILE,
                     "medicinal_notes": HOSTILE},
        "recipes": [{"title": "<u>Pesto</u>", "body": recipe_body, "is_preferred": True}],
    }


SAFE = safety_decision("none", "edible")   # batch 5: the PDF takes the server's decision


def _render(style, layout, profile=None):
    flat = [lp._flatten_species("Allium ursinum", profile or _profile(), {}, SAFE)]
    return lp._jinja_env.get_template("print_pdf.html").render(
        style=style, layout=layout, species=flat, ct=lp.ContentToggles().model_dump(),
        cover={"event": "<script>x</script>Walk", "date": "<b>1 May</b>", "location": "A & B",
               "intro": "<img src='file:///etc/hosts'>"},
        page_margin="10mm 8mm", goe_width=150, goe_pad=154,
        seasonal_returns=[{"scientific_name": "<i>X</i>", "reason": "<script>r</script>",
                           "timing": "now", "last_seen_fmt": "", "last_seen_place": "<b>P</b>"}])


def test_template_escapes_request_text_in_every_style_and_layout():
    for style in ("botanical", "herbalist", "goethean"):
        for layout in ("field_guide", "recipe_booklet", "workshop"):
            html = _render(style, layout)
            for raw in ("<script>", "<img src=\"file:///etc/passwd\">", "<img src='file:///etc/hosts'>",
                        "<b>bold</b>", "<b>Ramsons</b>", "<b>1 May</b>", "<img src=x>", "<i>one</i>",
                        "<i>X</i>", "<b>P</b>", "<u>Pesto</u>"):
                assert raw not in html, (style, layout, raw)
            assert "&lt;script&gt;" in html, (style, layout)
            assert "file:///etc/passwd" not in html or "&lt;img src=" in html


def test_safe_outputs_are_only_the_built_html():
    html = _render("botanical", "workshop")
    assert "<strong>A</strong>" in html                          # season_str (April) still HTML
    assert "<h3>&lt;img src=x&gt;Head</h3>" in html              # heading now escaped (was raw)
    assert "Step &lt;i&gt;one&lt;/i&gt; <strong>well</strong>" in html   # mdlite body + its own <strong>
    src = (PROJECT / "app/templates/print_pdf.html").read_text()
    assert src.count("| safe") == 4
    assert src.count("{{ sp.season_str | safe }}") == 2 and src.count("{{ sp.recipe_body | mdlite | safe }}") == 2
    assert lp._jinja_env.autoescape is True


def test_url_fetcher_allows_only_data_and_app_media_roots():
    ok_png = PROJECT / "frontend/static/print/botanical corner flowing light.png"
    r = lp._safe_url_fetcher(ok_png.as_uri())
    assert r.get("string") or r.get("file_obj")
    if "file_obj" in r:
        r["file_obj"].close()
    r = lp._safe_url_fetcher("data:text/plain;base64,aGk=")
    assert (r.get("string") or r["file_obj"].read()) == b"hi"

    refused = [
        "file:///etc/passwd",
        (PROJECT / ".env").as_uri(),
        (PROJECT / "data/foragingid.db").as_uri(),
        f"file://{PROJECT}/frontend/static/../../.env",                 # ../ escape
        f"file://{PROJECT}/uploads/../app/config.py",
        f"file://{PROJECT}/frontend/static%2F..%2F..%2F.env",            # encoded escape
        "file://otherhost/etc/passwd",
        "https://example.com/x.png",
        "http://127.0.0.1:8000/api/settings",
        "ftp://example.com/x",
    ]
    for url in refused:
        try:
            lp._safe_url_fetcher(url)
        except ValueError:
            continue
        raise AssertionError(f"fetched {url}")


def _weasy():
    try:
        from weasyprint import HTML
        return HTML
    except Exception as exc:  # native libs missing
        print("SKIP (WeasyPrint unavailable):", exc)
        return None


def _canaries():
    from PIL import Image
    d = Path(tempfile.mkdtemp(prefix="d101canary_"))
    (d / "canary.txt").write_text("D1-01-CANARY local file contents")
    Image.new("RGB", (64, 64), (255, 0, 0)).save(d / "canary.png")
    return d


def _pdf_facts(pdf_bytes):
    from pypdf import PdfReader
    rd = PdfReader(io.BytesIO(pdf_bytes))
    images = sum(len(p.images) for p in rd.pages)
    text = "".join(p.extract_text() or "" for p in rd.pages)
    # <a rel="attachment"> lands as a /FileAttachment page annotation (the
    # audit's repro), plus anything in the document's EmbeddedFiles tree.
    att = [a.get_object() for p in rd.pages for a in (p.get("/Annots") or [])
           if a.get_object().get("/Subtype") == "/FileAttachment"]
    return images, att + list(rd.attachments), text


def test_weasyprint_refuses_local_files_even_if_html_got_through():
    """Defence in depth: raw tags reaching WeasyPrint still can't pull files."""
    HTML = _weasy()
    if HTML is None:
        return
    d = _canaries()
    raw = (f'<p>x</p><img src="{(d / "canary.png").as_uri()}">'
           f'<a rel="attachment" href="{(d / "canary.txt").as_uri()}">att</a>')
    base = f"file://{PROJECT}/frontend/"
    # Control: the default fetcher does embed both (proves the check can fail).
    imgs, att, _ = _pdf_facts(HTML(string=raw, base_url=base).write_pdf())
    assert imgs == 1 and att, "control: default fetcher should embed the canaries"
    imgs, att, _ = _pdf_facts(HTML(string=raw, base_url=base, url_fetcher=lp._safe_url_fetcher).write_pdf())
    assert imgs == 0 and not att


def test_generate_pdf_all_styles_render_and_hostile_text_stays_text():
    HTML = _weasy()
    if HTML is None:
        return
    d = _canaries()
    hostile = (f'<script>alert(1)</script><img src="{(d / "canary.png").as_uri()}">'
               f'<a rel="attachment" href="{(d / "canary.txt").as_uri()}">att</a>')
    counts = {}
    for style in ("botanical", "herbalist", "goethean"):
        for layout in ("field_guide", "recipe_booklet", "workshop"):
            body = lp.PdfRequest(species=[lp.SpeciesData(scientific_name="Allium ursinum",
                                                         profile=_profile(id_notes=hostile))],
                                 style=style, layout=layout,
                                 cover=lp.CoverData(event="Walk", intro=hostile))
            resp = lp.render_pdf(body, {"Allium ursinum": SAFE})
            assert resp.status_code == 200 and resp.body[:5] == b"%PDF-", (style, layout, resp.body[:200])
            assert b"D1-01-CANARY" not in resp.body
            imgs, att, text = _pdf_facts(resp.body)
            assert not att, (style, layout)
            assert "<script>" in text.replace("\n", ""), (style, layout)   # printed as literal text
            counts[(style, layout)] = imgs
    # The real app images still embed: the botanical corner PNGs (4 per page,
    # from frontend/static/print). Herbalist/goethean borders are CSS data: URIs.
    assert all(counts[("botanical", lay)] >= 4 for lay in ("field_guide", "recipe_booklet", "workshop")), counts


def test_a_real_upload_photo_is_still_allowed():
    """The PDF has no species photos today; the fetcher must still accept one
    from uploads/ (or photos/) so adding them later needs no fetcher change."""
    HTML = _weasy()
    for root in ("uploads", "photos/pipeline2"):
        pic = next((p for p in (PROJECT / root).rglob("*.jp*g")), None)
        if pic:
            break
    if pic is None:
        print("SKIP (no photo in uploads/ or photos/)")
        return
    r = lp._safe_url_fetcher(pic.resolve().as_uri())
    if "file_obj" in r:
        r["file_obj"].close()
    if HTML is not None:
        imgs, _, _ = _pdf_facts(HTML(string=f'<img src="{pic.resolve().as_uri()}" style="width:2cm">',
                                     url_fetcher=lp._safe_url_fetcher).write_pdf())
        assert imgs == 1


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
