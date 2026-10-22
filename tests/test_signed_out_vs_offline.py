"""
Batch 7 follow-up (Melvin, 21 Oct 2026) — "not signed in" is not "offline".

The real frontend files are EXECUTED in JavaScriptCore (`jsc`) with small fakes
for the DOM, fetch, timers, the Cache API and IndexedDB:

  offline.js         a 401 from the /health ping → the signed-out banner (the
                     server's wording), no Offline banner, pinging stops; a
                     network failure (and a 502 gateway) still → Offline.
  sw.js              a 401 is never cached and never replaced by a cached copy;
                     only a network error falls back; /health is never handled.
  encounter-queue.js a 401 keeps every queued record, shows the signed-out text
                     and starts no replay loop.
Server side: the 401 is JSON for fetch() and HTML for a navigation, both
Cache-Control: no-store, with the one wording (access.SIGNED_OUT_TEXT) that the
two JS fallback copies must equal.

Run from project root:  python tests/test_signed_out_vs_offline.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)

from app.services.access import ASK_PAGE, SIGNED_OUT_TEXT  # noqa: E402

JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def _src(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


def _jsc(script):
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(script)
        path = f.name
    try:
        out = subprocess.run([JSC, path], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    assert out.returncode == 0, out.stderr or out.stdout
    return json.loads(out.stdout.strip().splitlines()[-1])


# ── fakes ────────────────────────────────────────────────────────────────────
DOM = r"""
var window = this;
function _el(tag) {
  return { tagName: tag, id: '', style: { cssText: '' }, children: [], textContent: '', innerHTML: '',
           dataset: {}, parentNode: null, classList: { _s: {}, add: function (c) { this._s[c] = 1; },
             remove: function (c) { delete this._s[c]; }, contains: function (c) { return !!this._s[c]; } },
           setAttribute: function () {}, appendChild: function (c) { c.parentNode = this; this.children.push(c); return c; },
           insertBefore: function (c) { c.parentNode = this; this.children.unshift(c); return c; },
           removeChild: function (c) { this.children = this.children.filter(function (x) { return x !== c; }); } };
}
var document = {
  readyState: 'complete', visibilityState: 'visible', hidden: false,
  body: _el('body'), head: _el('head'),
  createElement: _el,
  getElementById: function (id) {
    function walk(n) { if (n.id === id) return n; for (var i = 0; i < n.children.length; i++) { var r = walk(n.children[i]); if (r) return r; } return null; }
    return walk(document.body) || walk(document.head);
  },
  querySelectorAll: function () { return []; },
  addEventListener: function () {},
};
window.addEventListener = function () {};
var MutationObserver = function () { this.observe = function () {}; this.disconnect = function () {}; };
var localStorage = { getItem: function () { return new Date().toISOString(); }, setItem: function () {} };
var sessionStorage = localStorage;
var navigator = { onLine: true };
var location = { search: '', origin: 'https://abc123.ngrok-free.app' };
var AbortSignal = { timeout: function () { return null; } };
var _intervals = {}, _nextId = 1;
function setInterval(fn) { var id = _nextId++; _intervals[id] = fn; return id; }
function clearInterval(id) { delete _intervals[id]; }
function setTimeout() { return 0; }
function CustomEvent(n, o) { this.type = n; this.detail = o && o.detail; }
window.dispatchEvent = function () {};
function _resp(status, body) {
  return { status: status, ok: status >= 200 && status < 300, type: 'basic',
           json: function () { return Promise.resolve(body); }, clone: function () { return this; } };
}
"""


def _tick(n=40):
    """n chained microtask turns — lets the async code under test settle."""
    return "function _settle(n) { var p = Promise.resolve(); for (var i = 0; i < n; i++) p = p.then(function () {}); return p; }\n"


# ── offline.js ───────────────────────────────────────────────────────────────

def _offline(responses):
    """Run offline.js; /health answers from `responses` in turn (a status, or
    'network' for a rejected fetch). Pings: init + one per extra response."""
    script = DOM + _tick() + """
var _answers = %s, _pings = 0;
function fetch(url) {
  if (url !== '/health') return Promise.reject(new Error('no ' + url));
  var a = _answers[Math.min(_pings++, _answers.length - 1)];
  if (a === 'network') return Promise.reject(new TypeError('Failed to fetch'));
  return Promise.resolve(_resp(a, a === 401 ? { detail: %s } : {}));
}
""" % (json.dumps(responses), json.dumps(SIGNED_OUT_TEXT)) + _src("frontend/static/js/offline.js") + """
var p = _settle(40);
for (var k = 1; k < _answers.length; k++) {
  p = p.then(function () { for (var id in _intervals) _intervals[id](); return _settle(40); });
}
p.then(function () {
  var so = document.getElementById('signedout-banner'), off = document.getElementById('offline-banner');
  print(JSON.stringify({ signedOut: so ? so.children.map(function (c) { return c.textContent; }).join(' ') : null,
                         offline: !!off, offlineMode: document.body.classList.contains('offline-mode'),
                         intervals: Object.keys(_intervals).length, pings: _pings }));
});
"""
    return _jsc(script)


def test_401_shows_signed_out_not_offline_and_stops_pinging():
    r = _offline([401, 401, 401])
    assert r["signedOut"] and SIGNED_OUT_TEXT in r["signedOut"], r
    assert r["offline"] is False and r["offlineMode"] is False, r
    assert r["intervals"] == 0 and r["pings"] == 1, r          # no retry loop


def test_network_failure_still_shows_offline():
    r = _offline(["network", "network"])
    assert r["offline"] is True and r["offlineMode"] is True and r["signedOut"] is None, r


def test_gateway_502_counts_as_offline_other_statuses_do_not():
    assert _offline([502, 502])["offline"] is True
    r = _offline([403, 404, 500])
    assert r["offline"] is False and r["signedOut"] is None, r


def test_signed_out_after_offline_clears_the_offline_banner():
    r = _offline(["network", "network", 401])
    assert r["offline"] is False and r["signedOut"], r


# ── sw.js ────────────────────────────────────────────────────────────────────

def _sw(case):
    script = r"""
function URL(u) {                       // jsc has no URL — enough for sw.js routing
  var m = /^(https?:)\/\/([^\/?#]+)([^?#]*)/.exec(u);
  this.href = u; this.protocol = m[1]; this.host = m[2]; this.hostname = m[2].split(':')[0];
  this.origin = m[1] + '//' + m[2]; this.pathname = m[3] || '/';
}
var self = { location: { origin: 'https://abc123.ngrok-free.app' }, clients: { claim: function () {} },
             skipWaiting: function () {}, _h: {} };
self.addEventListener = function (t, fn) { self._h[t] = fn; };
var _store = {}, _puts = [];
var caches = {
  open: function (name) { return Promise.resolve({
    match: function (req) { return Promise.resolve(_store[req.url || req] || null); },
    put: function (req, resp) { _puts.push({ cache: name, url: req.url || req, status: resp.status }); _store[req.url || req] = resp; return Promise.resolve(); },
    delete: function () { return Promise.resolve(true); }, keys: function () { return Promise.resolve([]); },
    addAll: function () { return Promise.resolve(); } }); },
  match: function (req) { return Promise.resolve(_store[req.url || req] || null); },
  keys: function () { return Promise.resolve([]); }, delete: function () { return Promise.resolve(true); },
};
function _resp(status) { return { status: status, ok: status >= 200 && status < 300, type: 'basic',
  statusText: '', headers: { get: function () { return null; } }, clone: function () { return this; },
  arrayBuffer: function () { return Promise.resolve(new ArrayBuffer(0)); } }; }
var Response = function (b, o) { return _resp((o || {}).status || 200); };
var _net = null;
function fetch(req) { return _net === 'network' ? Promise.reject(new TypeError('Failed to fetch')) : Promise.resolve(_resp(_net)); }
""" + _src("frontend/static/sw.js") + r"""
var CASE = %s;
_net = CASE.net;
if (CASE.cachedShell) _store['/'] = Object.assign(_resp(200), { shell: true });
if (CASE.cachedSelf) _store[CASE.url] = Object.assign(_resp(200), { cachedCopy: true });
var handled = null;
self._h.fetch({ request: { method: 'GET', url: CASE.url, mode: CASE.mode || 'cors' },
                respondWith: function (p) { handled = p; } });
(handled || Promise.resolve('not-handled')).then(function (r) {
  print(JSON.stringify({ handled: !!handled, status: r && r.status, shell: !!(r && r.shell),
                         cachedCopy: !!(r && r.cachedCopy), puts: _puts }));
}, function (e) { print(JSON.stringify({ handled: !!handled, error: String(e), puts: _puts })); });
""" % json.dumps(case)
    return _jsc(script)


BASE = "https://abc123.ngrok-free.app"


def test_sw_never_caches_a_401():
    for url, mode in [(BASE + "/", "navigate"), (BASE + "/map", "navigate"), (BASE + "/api/map/geojson", "cors"),
                      (BASE + "/api/species/Allium%20ursinum/profile", "cors"), (BASE + "/static/js/x.js", "cors")]:
        r = _sw({"url": url, "mode": mode, "net": 401})
        assert r["handled"] and r["status"] == 401 and r["puts"] == [], (url, r)


def test_sw_never_serves_a_cached_page_in_place_of_a_401():
    r = _sw({"url": BASE + "/", "mode": "navigate", "net": 401, "cachedShell": True, "cachedSelf": True})
    assert r["status"] == 401 and not r["shell"] and not r["cachedCopy"], r
    r = _sw({"url": BASE + "/api/map/geojson", "net": 401, "cachedSelf": True})
    assert r["status"] == 401 and not r["cachedCopy"], r


def test_sw_network_failure_still_falls_back_to_the_cached_shell():
    r = _sw({"url": BASE + "/map", "mode": "navigate", "net": "network", "cachedShell": True})
    assert r["shell"] is True, r


def test_sw_leaves_the_health_ping_to_the_network():
    r = _sw({"url": BASE + "/health", "net": 200})
    assert r["handled"] is False, r


# ── encounter-queue.js ───────────────────────────────────────────────────────

def _queue(status, n_records=2):
    script = DOM + _tick() + r"""
var _db = {};
function _req(fn) { var r = {}; Promise.resolve().then(function () { r.result = fn(); r.onsuccess && r.onsuccess(); }); return r; }
var indexedDB = { open: function () {
  var store = { put: function (rec) { return _req(function () { _db[rec.uuid] = JSON.parse(JSON.stringify(rec)); return rec.uuid; }); },
                delete: function (k) { return _req(function () { delete _db[k]; }); },
                get: function (k) { return _req(function () { return _db[k]; }); },
                getAll: function () { return _req(function () { return Object.keys(_db).map(function (k) { return _db[k]; }); }); } };
  var db = { objectStoreNames: { contains: function () { return true; } },
             transaction: function () { return { objectStore: function () { return store; } }; } };
  var r = {}; Promise.resolve().then(function () { r.result = db; r.onsuccess && r.onsuccess(); }); return r; } };
var STATUS = %s, _posts = 0;
var FormData = function () { this.append = function () {}; };
function fetch(url, opts) {
  _posts++;
  if (STATUS === 'ok') return Promise.resolve(_resp(201, { client_uuid: JSON.parse(opts._uuid || '""'), id: 1 }));
  return Promise.resolve(_resp(STATUS, STATUS === 401 ? { detail: %s } : {}));
}
""" % (json.dumps(status), json.dumps(SIGNED_OUT_TEXT)) + _src("frontend/static/js/encounter-queue.js") + r"""
var p = _settle(60);
for (var i = 0; i < %d; i++) (function (i) {
  p = p.then(function () { return EncounterQueue.enqueue({ client_uuid: 'u' + i, species_text: 'x' }); })
       .then(function () { return _settle(60); });
})(i);
p = p.then(function () { for (var id in _intervals) _intervals[id](); return _settle(80); });
p.then(function () { return EncounterQueue.status(); }).then(function (st) {
  var chip = document.body.children.filter(function (c) { return /queued|sync|signed|allowed|kept/i.test(c.textContent || ''); })[0];
  print(JSON.stringify({ kept: Object.keys(_db).length, records: Object.keys(_db).map(function (k) { return _db[k]; }),
                         status: st, chip: chip ? chip.textContent : null,
                         intervals: Object.keys(_intervals).length, posts: _posts }));
});
""" % n_records
    return _jsc(script)


def test_outbox_keeps_every_item_on_401_and_shows_signed_out():
    r = _queue(401, 2)
    assert r["kept"] == 2, r                                         # nothing dropped
    # The queue waits in order: the oldest record holds the 401, later ones are
    # never sent past it (kept as pending).
    recs = sorted(r["records"], key=lambda x: x["captured_at"])
    assert recs[0]["status"] == "failed" and "not signed in" in recs[0]["last_error"], r
    assert all(x["status"] == "pending" for x in recs[1:]), r
    assert r["status"]["authBlocked"] is True and r["status"]["signedOut"] is True, r
    assert r["chip"] and SIGNED_OUT_TEXT in r["chip"], r
    assert r["intervals"] == 0, r                                    # no replay loop against the 401


def test_outbox_403_keeps_items_with_not_allowed_text():
    r = _queue(403, 1)
    assert r["kept"] == 1 and r["status"]["signedOut"] is False and "Not allowed" in (r["chip"] or ""), r


# ── server ───────────────────────────────────────────────────────────────────

def test_one_wording_everywhere():
    assert SIGNED_OUT_TEXT == "This device isn't signed in — ask Melvin for a link"
    for rel in ("frontend/static/js/offline.js", "frontend/static/js/encounter-queue.js"):
        m = re.search(r'var SIGNED_OUT_TEXT\s*=\s*"([^"]+)"', _src(rel))
        assert m and m.group(1) == SIGNED_OUT_TEXT, rel
    assert "This device isn&#x27;t signed in" in ASK_PAGE or "This device isn't signed in" in ASK_PAGE
    assert "Ask Melvin for a link" in ASK_PAGE


def test_server_401_is_json_for_fetch_html_for_navigation_and_never_cached():
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import test_batch7_access as t7
    env = t7.Env()
    try:
        c = t7.ngrok()
        r = c.get("/health")
        assert r.status_code == 401 and r.json() == {"detail": SIGNED_OUT_TEXT}
        assert r.headers["cache-control"] == "no-store"
        r = c.get("/", headers={"accept": "text/html,application/xhtml+xml"})
        assert r.status_code == 401 and r.headers["content-type"].startswith("text/html")
        assert r.headers["cache-control"] == "no-store" and "isn't signed in" in r.text
        r = c.get("/api/map/geojson", headers={"accept": "text/html"})      # an API is always JSON
        assert r.status_code == 401 and r.json()["detail"] == SIGNED_OUT_TEXT
    finally:
        env.close()


if __name__ == "__main__":
    for _name, _fn in list(globals().items()):
        if _name.startswith("test_") and callable(_fn):
            _fn()
            print("ok", _name)
