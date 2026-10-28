"""
Safety batch item 5 / B5-03 (28 Oct 2026): reviewer_notes are curator-only on
every guest-reachable path.

  * /api/map/geojson (guest-allowlisted) sends `description` = reviewer_notes:
    None for a guest on every pin, scenes included; the curator still gets it.
  * GET /api/observations/{id} already blanked it for guests (batch 8) — kept.
  * No other guest-allowlisted endpoint serialises reviewer_notes (source scan).

Run: python tests/test_safety_b5_03_reviewer_notes.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_enrichment_safety import Env  # noqa: E402
from test_enrichment_scope_and_recipe_warnings import _add, _job_queue  # noqa: E402
from test_batch8_guest_and_culinary_warnings import _app_client, _curator_device, _guest_device  # noqa: E402

import app.main as main  # noqa: E402
from app.models.observation import Observation  # noqa: E402
from app.models.workshop import WorkshopParticipant  # noqa: E402

NOTE_SP = "Auto-rejected: iNat kingdom=Insecta CURATOR-ONLY"
NOTE_SCENE = "Scene note CURATOR-ONLY"


def _env():
    env = Env()
    _job_queue(env)
    _add(env, [WorkshopParticipant(id=2, name="Alice")])
    _add(env, [
        Observation(id=301, file_path="/up/a.jpg", thumbnail_path="thumbnails/a.jpg", species_primary="Rumex acetosa",
                    review_status="approved", identification_status="identified",
                    latitude=51.5, longitude=-0.1, reviewer_notes=NOTE_SP),
        Observation(id=302, file_path="/up/s.jpg", thumbnail_path="thumbnails/s.jpg", species_primary=None,
                    obs_category="landscape", review_status="approved", identification_status="identified",
                    latitude=51.6, longitude=-0.2, reviewer_notes=NOTE_SCENE),
    ])
    return env


def _pins(c):
    r = c.get("/api/map/geojson")
    assert r.status_code == 200, r.text[:200]
    return {f["properties"]["id"]: f["properties"] for f in r.json()["features"]}


def test_guest_geojson_has_no_reviewer_notes():
    env = _env()
    try:
        with _guest_device(env):
            c = _app_client(env, None)
            pins = _pins(c)
            assert set(pins) >= {301, 302}, pins
            for oid in (301, 302):
                assert pins[oid]["description"] is None, pins[oid]
            body = c.get("/api/map/geojson").text
            assert "CURATOR-ONLY" not in body, body[:300]
            for oid in (301, 302):                                   # batch 8 path still blank
                d = c.get(f"/api/observations/{oid}").json()
                assert d["reviewer_notes"] is None, d
    finally:
        main.app.dependency_overrides.clear()
        env.close()


def test_curator_geojson_keeps_reviewer_notes():
    env = _env()
    try:
        with _curator_device(env):
            c = _app_client(env, None)
            pins = _pins(c)
            assert pins[301]["description"] == NOTE_SP, pins[301]
            assert pins[302]["description"] == NOTE_SCENE, pins[302]
    finally:
        main.app.dependency_overrides.clear()
        env.close()


def test_no_other_api_file_serialises_reviewer_notes_unguarded():
    """Every app/api file that reads reviewer_notes into a response is either
    curator-only (not guest-allowlisted) or guards it for guests."""
    guarded = {"map.py": 'None if identity.is_guest else (row.reviewer_notes or None)',
               "observations.py": 'd["reviewer_notes"] = None'}
    for fn, needle in guarded.items():
        assert needle in open(os.path.join(ROOT, "app", "api", fn), encoding="utf-8").read(), fn
    # Files that mention reviewer_notes; each must be in guarded or serve curator-only routes.
    curator_only = {"audit.py", "trust.py", "scan.py"}
    hits = set()
    for fn in os.listdir(os.path.join(ROOT, "app", "api")):
        if fn.endswith(".py") and re.search(r"reviewer_notes", open(os.path.join(ROOT, "app", "api", fn), encoding="utf-8").read()):
            hits.add(fn)
    assert hits <= set(guarded) | curator_only, hits - set(guarded) - curator_only


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
