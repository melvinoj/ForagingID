// ForagingID encounter outbox — Phase 13.10b (offline write queue) + Tier-1 hardening.
//
// Goal: field capture always succeeds locally and is durable across reloads;
// sync to the server happens when signal allows. No encounter is ever lost to
// flaky/dropped cellular.
//
// Pattern: OUTBOX. Capture writes the record to IndexedDB FIRST (durable), then
// attempts the send. This survives the tab dying mid-send and makes replay safe.
//
// Idempotency: each record carries a client-generated UUID (the key). The server
// (POST /api/encounters, migration 0032) returns the existing row when it sees a
// repeated client_uuid, so a request whose response was lost to bad signal never
// produces a duplicate on replay.
//
// Tier-1 correctness changes:
//   • A 2xx is NOT proof of persistence. Before deleting a record we require the
//     response body to parse and echo the matching client_uuid (with an id). This
//     defeats a proxy/ngrok interstitial that returns "200 OK" with HTML.
//   • ngrok-skip-browser-warning header sent on every POST.
//   • Failure taxonomy: 401/403 = auth (keep retrying, surface "re-open your link",
//     queue intentionally wedges so nothing is lost); 408/429/5xx/network = transient
//     (retry, preserve order); other permanent 4xx (e.g. 422) = PARK in a won't-retry
//     bucket so one poison record can't stall everything behind it.
//   • Location grace: a record captured without coordinates waits briefly for a fresh
//     GPS fix (attachLocation) before its first send, so field captures land located.
//
// Auth: the participant token is read ONCE from ?token= on load into a module-level
// variable and attached as `Authorization: Bearer` on every send. Never persisted in
// the queue, never in the URL.
//
// Exposes window.EncounterQueue and dispatches window CustomEvents:
//   • 'encounter-queue:change' { pending, parked, failed, authBlocked, syncing }
//   • 'encounter-queue:synced' { uuid }

(function () {
  'use strict';

  // ── Constants ──────────────────────────────────────────────────────────────
  var DB_NAME            = 'fid_encounter_queue';
  var DB_VERSION         = 1;
  var STORE              = 'encounter_queue';
  var ENDPOINT           = '/api/encounters';
  var REPLAY_INTERVAL_MS = 20000;  // periodic replay while retryable items are pending
  var FAILED_THRESHOLD   = 3;      // attempts above this → "failed — will retry" chip
  var LOCATION_GRACE_MS  = 9000;   // hold a coord-less record this long for a GPS fix

  // ── Token — captured once on load, never persisted in the queue ─────────────
  var _token = null;
  try {
    var t = new URLSearchParams(location.search).get('token');
    _token = t ? (t.trim() || null) : null;
  } catch (e) { _token = null; }

  function authHeader() { return _token ? ('Bearer ' + _token) : null; }

  // ── UUID (idempotency key) — generated at capture time ──────────────────────
  function newUUID() {
    try {
      if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    } catch (e) { /* fall through */ }
    var buf = new Uint8Array(16);
    if (window.crypto && crypto.getRandomValues) crypto.getRandomValues(buf);
    else for (var k = 0; k < 16; k++) buf[k] = Math.floor(Math.random() * 256);
    buf[6] = (buf[6] & 0x0f) | 0x40;
    buf[8] = (buf[8] & 0x3f) | 0x80;
    var h = [];
    for (var i = 0; i < 16; i++) h.push((buf[i] + 0x100).toString(16).slice(1));
    return h.slice(0, 4).join('') + '-' + h.slice(4, 6).join('') + '-' +
           h.slice(6, 8).join('') + '-' + h.slice(8, 10).join('') + '-' +
           h.slice(10, 16).join('');
  }

  // ── IndexedDB plumbing ──────────────────────────────────────────────────────
  var _dbPromise = null;
  function _openDB() {
    if (_dbPromise) return _dbPromise;
    _dbPromise = new Promise(function (resolve, reject) {
      var req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = function () {
        var db = req.result;
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE, { keyPath: 'uuid' });
        }
      };
      req.onsuccess = function () { resolve(req.result); };
      req.onerror   = function () { reject(req.error); };
    });
    return _dbPromise;
  }

  function _store(mode) {
    return _openDB().then(function (db) {
      return db.transaction(STORE, mode).objectStore(STORE);
    });
  }

  function _reqAsPromise(makeReq, mode) {
    return _store(mode || 'readonly').then(function (store) {
      return new Promise(function (resolve, reject) {
        var r = makeReq(store);
        r.onsuccess = function () { resolve(r.result); };
        r.onerror   = function () { reject(r.error); };
      });
    });
  }

  function _put(record)  { return _reqAsPromise(function (s) { return s.put(record); },  'readwrite'); }
  function _delete(uuid) { return _reqAsPromise(function (s) { return s.delete(uuid); }, 'readwrite'); }
  function _get(uuid)    { return _reqAsPromise(function (s) { return s.get(uuid); },    'readonly'); }
  function _all()        { return _reqAsPromise(function (s) { return s.getAll(); },     'readonly'); }

  function _hasLocation(rec) {
    var p = rec.payload || {};
    return p.latitude != null && p.longitude != null;
  }

  // ── Status ──────────────────────────────────────────────────────────────────
  var _flushing    = false;
  var _authBlocked = false;  // last flush hit a 401/403 — token expired/invalid

  function _status() {
    return _all().then(function (recs) {
      recs = recs || [];
      var pending = 0, parked = 0, failed = 0;
      for (var i = 0; i < recs.length; i++) {
        if (recs[i].status === 'parked') { parked++; continue; }
        pending++;
        if ((recs[i].attempts || 0) > FAILED_THRESHOLD) failed++;
      }
      return { pending: pending, parked: parked, failed: failed,
               authBlocked: _authBlocked, syncing: _flushing };
    }).catch(function () {
      return { pending: 0, parked: 0, failed: 0, authBlocked: _authBlocked, syncing: _flushing };
    });
  }

  // ── Status chip (single, non-blocking, bottom-right) ────────────────────────
  var _chip = null;
  function _ensureChip() {
    if (_chip || !document.body) return _chip;
    _chip = document.createElement('div');
    _chip.id = 'enc-queue-chip';
    _chip.setAttribute('role', 'status');
    _chip.setAttribute('aria-live', 'polite');
    _chip.style.cssText = [
      'position:fixed', 'right:14px', 'bottom:14px', 'z-index:10001',
      'display:inline-flex', 'align-items:center', 'gap:7px',
      'padding:6px 13px', 'border-radius:14px', 'max-width:78vw',
      'font:600 0.78rem system-ui,-apple-system,sans-serif',
      'box-shadow:0 2px 8px rgba(0,0,0,0.28)', 'pointer-events:none',
      'transition:opacity 0.25s, background 0.2s',
    ].join(';');
    document.body.appendChild(_chip);
    return _chip;
  }

  function _renderChip(st) {
    var chip = _ensureChip();
    if (!chip) return;
    var dot, label, bg, fg, opacity = '1';
    if (st.authBlocked) {
      dot = '⚠️'; label = 'Token expired — re-open your link';   bg = '#5a2030'; fg = '#ffd2d2';
    } else if (st.syncing && st.pending > 0) {
      dot = '🔄'; label = 'Syncing…';                            bg = '#23406b'; fg = '#dce8ff';
    } else if (st.pending > 0 && st.failed > 0) {
      dot = '⚠️'; label = st.failed + ' failed — will retry';     bg = '#5a3320'; fg = '#ffd9b3';
    } else if (st.pending > 0) {
      dot = '📥'; label = st.pending + ' queued';                 bg = '#3a3320'; fg = '#ffe6a3';
    } else if (st.parked > 0) {
      dot = '⚠️'; label = st.parked + " can't sync — check encounters"; bg = '#5a3320'; fg = '#ffd9b3';
    } else {
      dot = '✓';  label = 'All synced';                           bg = '#2a3a26'; fg = '#9fc78a'; opacity = '0.72';
    }
    chip.textContent = dot + ' ' + label;
    chip.style.background = bg;
    chip.style.color      = fg;
    chip.style.opacity    = opacity;
  }

  // ── Event + chip notification ────────────────────────────────────────────────
  function _dispatch(name, detail) {
    try { window.dispatchEvent(new CustomEvent(name, { detail: detail })); } catch (e) {}
  }
  function _emitChange() {
    return _status().then(function (st) {
      _renderChip(st);
      _dispatch('encounter-queue:change', st);
      return st;
    });
  }

  // ── Periodic replay (only while retryable items are pending) ────────────────
  var _intervalId = null;
  function _scheduleInterval() {
    if (_intervalId) return;
    _intervalId = setInterval(function () { flush(); }, REPLAY_INTERVAL_MS);
  }
  function _clearInterval() {
    if (_intervalId) { clearInterval(_intervalId); _intervalId = null; }
  }

  // ── Send a single record ────────────────────────────────────────────────────
  function _sendRecord(record) {
    var fd = new FormData();
    var p = record.payload || {};
    Object.keys(p).forEach(function (key) {
      var v = p[key];
      if (v !== null && v !== undefined && v !== '') fd.append(key, v);
    });
    // ngrok-skip-browser-warning bypasses the free-tier interstitial so a POST is
    // proxied to the server rather than answered with the warning HTML page.
    var headers = { 'ngrok-skip-browser-warning': 'true' };
    var hdr = authHeader();
    if (hdr) headers['Authorization'] = hdr;
    // NB: never set Content-Type — the browser sets the multipart boundary itself.
    return fetch(ENDPOINT, { method: 'POST', body: fd, headers: headers });
  }

  function _markFailed(rec, err) {
    rec.attempts   = (rec.attempts || 0) + 1;
    rec.last_error = err || null;
    rec.status     = 'failed';
    return _put(rec);
  }

  function _park(rec, err) {
    rec.attempts   = (rec.attempts || 0) + 1;
    rec.last_error = err || null;
    rec.status     = 'parked';  // permanent — never retried
    return _put(rec);
  }

  // Outcome codes from processing one record:
  //   'continue' — done with this record, move to the next
  //   'stop'     — leave this and all later records for a future flush (order/retry)
  function _processResponse(rec, resp) {
    if (resp.ok) {
      // A 2xx is necessary but NOT sufficient. Require the body to be our JSON and
      // echo the matching client_uuid — otherwise a proxy/interstitial 200 would
      // make us delete an encounter that never reached the server.
      return resp.json().catch(function () { return null; }).then(function (body) {
        if (body && body.client_uuid === rec.uuid && body.id != null) {
          return _delete(rec.uuid).then(function () {
            _dispatch('encounter-queue:synced', { uuid: rec.uuid });
            return 'continue';
          });
        }
        return _markFailed(rec, '2xx but unexpected body (proxy/interstitial?) — kept')
          .then(function () { return 'stop'; });
      });
    }
    var s = resp.status;
    if (s === 401 || s === 403) {
      // Auth: keep the data, keep retrying; the whole queue waits for a fresh token.
      _authBlocked = true;
      return _markFailed(rec, 'HTTP ' + s + ' (auth) — re-open your link').then(function () { return 'stop'; });
    }
    if (s === 408 || s === 429 || s >= 500) {
      // Transient: retry later, preserve order.
      return resp.json().catch(function () { return {}; }).then(function (j) {
        return _markFailed(rec, 'HTTP ' + s + (j && j.detail ? ': ' + j.detail : '')).then(function () { return 'stop'; });
      });
    }
    // Any other 4xx (400/404/409/413/422 …) is permanent for this payload. PARK it so
    // it can never block the records behind it.
    return resp.json().catch(function () { return {}; }).then(function (j) {
      return _park(rec, 'HTTP ' + s + (j && j.detail ? ': ' + j.detail : '')).then(function () { return 'continue'; });
    });
  }

  // ── Flush — oldest-first, single-flight ─────────────────────────────────────
  var flush = function () {
    if (_flushing) return Promise.resolve();
    if (!navigator.onLine) return _emitChange();
    _flushing    = true;
    _authBlocked = false;  // recomputed this pass
    _emitChange();         // → "Syncing…"
    var now = Date.now();
    return _all().then(function (records) {
      records = (records || [])
        .filter(function (r) { return r.status !== 'parked'; })
        .sort(function (a, b) {
          return String(a.captured_at || '').localeCompare(String(b.captured_at || ''));
        });

      return records.reduce(function (chain, rec) {
        return chain.then(function (stopped) {
          if (stopped) return true;
          // Location grace: hold a coord-less record briefly for a fresh GPS fix.
          if (!_hasLocation(rec) && rec.awaiting_location_until && now < rec.awaiting_location_until) {
            return true;  // defer this (and, to preserve order, later) records
          }
          rec.status = 'sending';
          return _put(rec)
            .then(function () { return _sendRecord(rec); })
            .then(function (resp) { return _processResponse(rec, resp); })
            .catch(function (e) {
              // Network error / went offline mid-send → transient, stop.
              return _markFailed(rec, (e && e.message) ? e.message : 'network error')
                .then(function () { return 'stop'; });
            })
            .then(function (outcome) { return outcome === 'stop'; });
        });
      }, Promise.resolve(false));
    }).then(function () {
      return _all();
    }).then(function (recs) {
      // Keep the retry interval alive only while retryable (non-parked) items remain.
      var retryable = (recs || []).some(function (r) { return r.status !== 'parked'; });
      if (retryable) _scheduleInterval(); else _clearInterval();
    }).catch(function () { /* swallow — chip refresh below reflects state */ })
      .then(function () {
        _flushing = false;
        return _emitChange();
      });
  };

  // ── Enqueue (durable write, then trigger a send) ────────────────────────────
  function enqueue(payload, opts) {
    if (!payload || !payload.client_uuid) {
      return Promise.reject(new Error('payload.client_uuid is required'));
    }
    opts = opts || {};
    var record = {
      uuid:        payload.client_uuid,
      payload:     payload,
      captured_at: new Date().toISOString(),
      status:      'pending',
      attempts:    0,
      last_error:  null,
    };
    // If we have no fix yet and a fresh one is being fetched, hold the first send
    // briefly so the encounter lands located rather than location-pending.
    if (opts.awaitLocation && !_hasLocation(record)) {
      record.awaiting_location_until = Date.now() + LOCATION_GRACE_MS;
    }
    return _put(record).then(function () {
      _scheduleInterval();
      flush();  // confirmation in the UI is immediate and independent of this send
      return _emitChange().then(function () { return record; });
    });
  }

  // ── Attach a location to a still-queued record (from a fresh GPS fix) ────────
  function attachLocation(uuid, fields) {
    if (!uuid || !fields || fields.latitude == null || fields.longitude == null) {
      return Promise.resolve(false);
    }
    return _get(uuid).then(function (rec) {
      if (!rec || rec.status === 'parked') return false;  // gone (sent) or won't-retry
      rec.payload = rec.payload || {};
      rec.payload.latitude  = fields.latitude;
      rec.payload.longitude = fields.longitude;
      delete rec.awaiting_location_until;  // grace satisfied — eligible to send now
      return _put(rec).then(function () {
        flush();
        return _emitChange().then(function () { return true; });
      });
    }).catch(function () { return false; });
  }

  // ── Init ────────────────────────────────────────────────────────────────────
  function _init() {
    _emitChange();
    if (navigator.onLine) flush();
    _all().then(function (recs) {
      if ((recs || []).some(function (r) { return r.status !== 'parked'; })) _scheduleInterval();
    });

    window.addEventListener('online',  function () { flush(); });
    window.addEventListener('offline', function () { _emitChange(); });
    window.addEventListener('focus',   function () { flush(); });
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) flush();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }

  // ── Public API ──────────────────────────────────────────────────────────────
  window.EncounterQueue = {
    enqueue:        enqueue,
    attachLocation: attachLocation,
    flush:          flush,
    status:         _status,
    newUUID:        newUUID,
    authHeader:     authHeader,
    hasToken:       function () { return !!_token; },
  };

})();
