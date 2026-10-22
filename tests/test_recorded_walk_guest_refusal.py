"""
Batch 8 follow-ups (Melvin, 22 Oct 2026): participants never record walks or
attach photos from the Record tab.

  * POST /api/recorded-walks and /api/recorded-walks/audio-upload → 403 for a
    participant device, refused by the middleware (guest_access.py) before the
    endpoint; the endpoint's own is_guest check is the second layer.
  * Curator recording unchanged.
  * Record tab: 🎙 row and 📷 Photo row both data-guest-hide; walk recording
    controls (👣, Record live, HUD, save modal) hidden and guarded for guests.

Run: python tests/test_recorded_walk_guest_refusal.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tests"))

from test_batch8_guest_and_culinary_warnings import (  # noqa: E402
    CURATOR, PARTICIPANT, _app_client, _curator_device, _extract, _guest_device, _guest_env, _src,
)
import app.api.recorded_walks as rw  # noqa: E402
import app.main as main  # noqa: E402
from app.services import guest_access as ga  # noqa: E402

WALK = {"name": "Test walk", "started_at": "2026-10-22T10:00:00", "ended_at": "2026-10-22T10:01:00", "duration_s": 60,
        "track_points": [], "proximity_encounters": []}


def test_guest_write_list_excludes_recorded_walks():
    for p in ("/api/recorded-walks", "/api/recorded-walks/audio-upload"):
        assert not ga.guest_api_allowed("POST", p), p
    assert ga.guest_api_allowed("GET", "/api/recorded-walks") and ga.guest_api_allowed("GET", "/api/recorded-walks/3")


def test_participant_refused_create_and_audio_upload():
    env = _guest_env()
    try:
        before = env.q("SELECT COUNT(*) FROM recorded_walks")[0][0]
        files_before = set(os.listdir(rw.AUDIO_DIR)) if rw.AUDIO_DIR.exists() else set()
        with _guest_device(env):
            c = _app_client(env, None)
            r = c.post("/api/recorded-walks", json=WALK)
            assert r.status_code == 403 and r.json()["detail"] == "Guest mode — read-only access", r.text
            r = c.post("/api/recorded-walks/audio-upload", files={"file": ("n.webm", b"RIFF", "audio/webm")})
            assert r.status_code == 403 and r.json()["detail"] == "Guest mode — read-only access", r.text
            assert c.get("/api/recorded-walks").status_code == 200                   # reading stays open
        assert env.q("SELECT COUNT(*) FROM recorded_walks")[0][0] == before
        files_after = set(os.listdir(rw.AUDIO_DIR)) if rw.AUDIO_DIR.exists() else set()
        assert files_after == files_before
    finally:
        main.app.dependency_overrides.clear()
        env.close()


def test_endpoint_still_refuses_a_guest_identity_past_the_middleware():
    # Second layer: a guest identity on a curator-tier request still gets 403.
    env = _guest_env()
    try:
        with _curator_device(env):
            c = _app_client(env, PARTICIPANT)
            r = c.post("/api/recorded-walks", json=WALK)
            assert r.status_code == 403 and r.json()["detail"] == "Curator only", r.text
            r = c.post("/api/recorded-walks/audio-upload", files={"file": ("n.webm", b"RIFF", "audio/webm")})
            assert r.status_code == 403 and r.json()["detail"] == "Curator only", r.text
    finally:
        main.app.dependency_overrides.clear()
        env.close()


def test_curator_still_records_and_uploads_audio():
    env = _guest_env()
    written = None
    try:
        with _curator_device(env):
            c = _app_client(env, CURATOR)
            r = c.post("/api/recorded-walks", json=WALK)
            assert r.status_code == 200, r.text
            wid = r.json()["id"]
            row = env.q(f"SELECT id, name, duration_s, user_id FROM recorded_walks WHERE id = {wid}")
            assert row == [(wid, "Test walk", 60, 1)], row
            r = c.post("/api/recorded-walks/audio-upload", files={"file": ("n.webm", b"RIFF", "audio/webm")})
            assert r.status_code == 200, r.text
            written = r.json()["path"]
            assert os.path.isfile(written)
    finally:
        if written and os.path.isfile(written):
            os.remove(written)                                                       # don't leave test audio in media/
        main.app.dependency_overrides.clear()
        env.close()


def test_record_tab_hides_voice_and_photo_for_participants():
    html = _src("frontend/encounters.html")
    assert '<div id="rec-voice-row" data-guest-hide' in html
    assert '<div id="rec-photo-row" data-guest-hide' in html
    assert html.index('id="rec-photo-row"') < html.index('id="rec-photo-input"') < html.index('id="rec-note"')
    assert "body.guest-mode [data-guest-hide]" in _src("frontend/static/js/guest-mode.js")


def test_walk_recording_controls_hidden_and_guarded_for_participants():
    idx = _src("frontend/index.html")
    assert '<button id="wrec-float-btn" data-guest-hide' in idx
    assert '<div id="walk-rec-hud" data-guest-hide>' in idx
    assert '<div id="walk-save-modal" data-guest-hide>' in idx
    assert idx.count('data-guest-hide onclick="_wbsStartRecording()"') == 2
    assert idx.count('onclick="_wbsStartRecording()"') == 2                           # no unhidden entry left
    start = _extract(idx, "window._wbsStartRecording = function() {", "if (!isMobile())")
    assert "classList.contains('guest-mode')) return;" in start
    toggle = _extract(idx, "function _wrecToggle() {", "GPS.getOnce()")
    assert "classList.contains('guest-mode') && !WalkRecorder.isRecording()) return;" in toggle


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print("PASS", fn.__name__)
    print(f"{len(fns)} passed")
