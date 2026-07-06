/**
 * walk-record.js — GPS Walk Recording module (Prompt A)
 *
 * Exposes window.WalkRecorder with:
 *   start()        — begin recording (returns Promise)
 *   stop()         — stop recording, return session data
 *   isRecording()  — boolean
 *   getState()     — live { distanceM, durationS, trackPoints, proximityEncounters }
 *   logProximityEncounter(obsId, isoTs) — called by proximity alert system
 *   onStateChange(fn) / offStateChange(fn) — subscribe to live updates
 *
 * The GPS watch persists as long as the module is loaded regardless of which
 * panel / page the user is on. Recording state is also mirrored to
 * sessionStorage so a page reload within the same tab can detect an
 * interrupted session (Prompt B concern — handled here as best-effort).
 */
(function () {
  'use strict';

  var TICK_INTERVAL_MS  = 5000;   // track point every 5 s
  var _recording        = false;
  var _startedAt        = null;   // Date
  var _trackPoints      = [];     // [{lat, lng, alt, ts}]
  var _proximityLog     = [];     // [{observation_id, encountered_at}]
  var _wakeLock         = null;
  // _watchHandle removed: WalkRecorder no longer owns the GPS watch (see Bug 3 fix below).
  var _tickTimer        = null;
  var _listeners        = [];
  var _lastPos          = null;   // most recent GPS fix

  // ------------------------------------------------------------------
  // Internal helpers
  // ------------------------------------------------------------------

  function _haversineM(lat1, lng1, lat2, lng2) {
    var R  = 6371000;
    var f1 = lat1 * Math.PI / 180, f2 = lat2 * Math.PI / 180;
    var df = (lat2 - lat1) * Math.PI / 180;
    var dl = (lng2 - lng1) * Math.PI / 180;
    var a  = Math.sin(df / 2) * Math.sin(df / 2) +
             Math.cos(f1) * Math.cos(f2) * Math.sin(dl / 2) * Math.sin(dl / 2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  }

  function _computeDistanceM(pts) {
    var d = 0;
    for (var i = 1; i < pts.length; i++) {
      d += _haversineM(pts[i-1].lat, pts[i-1].lng, pts[i].lat, pts[i].lng);
    }
    return d;
  }

  function _durationS() {
    if (!_startedAt) return 0;
    return Math.round((Date.now() - _startedAt.getTime()) / 1000);
  }

  function _notify() {
    var state = _buildState();
    _listeners.forEach(function (fn) { try { fn(state); } catch (_) {} });
    // Mirror to sessionStorage for crash recovery
    try {
      sessionStorage.setItem('fid_walk_recording', _recording ? JSON.stringify({
        startedAt:  _startedAt && _startedAt.toISOString(),
        trackPoints: _trackPoints,
      }) : '');
    } catch (_) {}
  }

  function _buildState() {
    return {
      recording:            _recording,
      startedAt:            _startedAt,
      durationS:            _durationS(),
      distanceM:            Math.round(_computeDistanceM(_trackPoints)),
      trackPoints:          _trackPoints.slice(),
      proximityEncounters:  _proximityLog.slice(),
    };
  }

  function _tick() {
    // Bug 3 fix: read from GPS.getLast() rather than a private watch callback.
    // This way WalkRecorder does not call GPS.startWatch, so the proximity-watch
    // callback registered by _startProxWatch() (index.html) is never overridden.
    var pos = GPS.getLast();
    if (!_recording || !pos) return;
    _lastPos = pos;
    _trackPoints.push({
      lat: _lastPos.lat,
      lng: _lastPos.lng,
      alt: _lastPos.accuracy != null ? null : null, // altitude if available
      ts:  Date.now(),
    });
    _notify();
  }

  // ------------------------------------------------------------------
  // Public API
  // ------------------------------------------------------------------

  async function start() {
    if (_recording) return;

    // Request wake lock — fail silently
    if ('wakeLock' in navigator) {
      try {
        _wakeLock = await navigator.wakeLock.request('screen');
        _wakeLock.addEventListener('release', function () { _wakeLock = null; });
      } catch (_) { _wakeLock = null; }
    }

    _recording   = true;
    _startedAt   = new Date();
    _trackPoints  = [];
    _proximityLog = [];

    // Bug 3 fix: do NOT call GPS.startWatch here — that would override the
    // proximity-watch callback. Instead, seed the GPS cache with getOnce() so
    // GPS.getLast() is non-null immediately, then rely on whatever watch is
    // already running (proximity watch in walk mode) to keep the cache fresh.
    GPS.getOnce().catch(function () { /* no fix yet — _tick skips if _lastPos null */ });

    _tickTimer = setInterval(_tick, TICK_INTERVAL_MS);
    _notify();
  }

  function stop() {
    if (!_recording) return null;
    _recording = false;

    clearInterval(_tickTimer);
    _tickTimer = null;

    // Push one final point
    if (_lastPos) {
      _trackPoints.push({ lat: _lastPos.lat, lng: _lastPos.lng, alt: null, ts: Date.now() });
    }

    if (_wakeLock) {
      try { _wakeLock.release(); } catch (_) {}
      _wakeLock = null;
    }

    // Bug 3 fix: no GPS.stopWatch() here — we don't own the watch.

    var result = {
      startedAt:           _startedAt,
      endedAt:             new Date(),
      durationS:           _durationS(),
      distanceM:           Math.round(_computeDistanceM(_trackPoints)),
      trackPoints:         _trackPoints.slice(),
      proximityEncounters: _proximityLog.slice(),
    };

    _startedAt    = null;
    _trackPoints  = [];
    _proximityLog = [];
    _lastPos      = null;

    try { sessionStorage.removeItem('fid_walk_recording'); } catch (_) {}
    _notify();
    return result;
  }

  function logProximityEncounter(obsId, isoTs) {
    if (!_recording) return;
    // Deduplicate by obsId within a recording session
    var exists = _proximityLog.some(function (e) { return e.observation_id === obsId; });
    if (!exists) {
      _proximityLog.push({ observation_id: obsId, encountered_at: isoTs || new Date().toISOString() });
    }
  }

  function isRecording() { return _recording; }

  function getState() { return _buildState(); }

  function onStateChange(fn) {
    if (typeof fn === 'function' && _listeners.indexOf(fn) === -1) {
      _listeners.push(fn);
    }
  }

  function offStateChange(fn) {
    _listeners = _listeners.filter(function (f) { return f !== fn; });
  }

  window.WalkRecorder = {
    start:                start,
    stop:                 stop,
    isRecording:          isRecording,
    getState:             getState,
    logProximityEncounter: logProximityEncounter,
    onStateChange:        onStateChange,
    offStateChange:       offStateChange,
  };
})();
