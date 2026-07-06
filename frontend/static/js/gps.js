// Shared GPS manager — the single source of truth for the device position.
//
// Used by:
//   - the map locate button (locateMe in index.html)
//   - the Near me view (prompt 10a.4)
//   - the walk proximity watch (prompt 10a.5)
//
// getOnce() returns the cached fix immediately if it is fresh (< 60s old),
// otherwise it calls getCurrentPosition. This is what lets "Near me" reuse a
// position the locate button already obtained without re-fetching.
(function () {
  'use strict';

  var CACHE_MS = 60000;   // a fix younger than this is reused by getOnce()
  var _last = null;       // { lat, lng, accuracy, timestamp }
  var _watchId = null;

  function _store(pos) {
    _last = {
      lat: pos.coords.latitude,
      lng: pos.coords.longitude,
      accuracy: pos.coords.accuracy,
      timestamp: Date.now(),
    };
    // Keep the legacy global in sync so existing readers keep working.
    window.foragingUser = { lat: _last.lat, lng: _last.lng, timestamp: _last.timestamp };
    return _last;
  }

  // Returns a Promise resolving to { lat, lng, accuracy, timestamp }.
  // opts.maxAge overrides the module reuse window (default CACHE_MS). Pass maxAge: 0
  // to force a fresh hardware fix — used by encounter capture so two records taken
  // moments apart while walking never share a stale reading.
  function getOnce(opts) {
    opts = opts || {};
    var maxAge = (opts.maxAge != null) ? opts.maxAge : CACHE_MS;
    return new Promise(function (resolve, reject) {
      if (!('geolocation' in navigator)) {
        reject(new Error('geolocation-unavailable'));
        return;
      }
      // Fresh cached fix — hand it back immediately, no hardware re-fetch.
      if (maxAge > 0 && _last && (Date.now() - _last.timestamp) < maxAge) {
        resolve(_last);
        return;
      }
      navigator.geolocation.getCurrentPosition(
        function (pos) { resolve(_store(pos)); },
        function (err) { reject(err); },
        {
          enableHighAccuracy: opts.enableHighAccuracy !== false,
          timeout: opts.timeout || 10000,
          // When forcing a fresh module fix, also forbid a stale browser-cached one.
          maximumAge: opts.maximumAge != null ? opts.maximumAge : (maxAge > 0 ? 30000 : 0),
        }
      );
    });
  }

  // Continuous position updates. callback receives the same shape as getOnce().
  // Only one watch runs at a time; starting a new one replaces the previous.
  function startWatch(callback) {
    if (!('geolocation' in navigator)) return null;
    if (_watchId !== null) navigator.geolocation.clearWatch(_watchId);
    _watchId = navigator.geolocation.watchPosition(
      function (pos) { if (callback) callback(_store(pos)); },
      function () { /* swallow transient watch errors — caller keeps last fix */ },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 }
    );
    return _watchId;
  }

  function stopWatch() {
    if (_watchId !== null) {
      navigator.geolocation.clearWatch(_watchId);
      _watchId = null;
    }
  }

  function getLast() { return _last; }

  window.GPS = {
    getOnce: getOnce,
    startWatch: startWatch,
    stopWatch: stopWatch,
    getLast: getLast,
  };
})();
