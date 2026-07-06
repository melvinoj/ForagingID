// ForagingID offline module — Phase 10a Session C.
//
// Responsibilities:
//   • Show / hide a persistent "Offline — read only" banner.
//   • Add / remove body.offline-mode class that CSS uses to visually disable
//     write-action controls across all pages.
//   • Apply "available when back online" title to write-action elements,
//     using a MutationObserver so dynamically-rendered buttons are caught.
//   • Pre-cache species profile data for all confirmed species on page load
//     and whenever the app comes back online after a period offline.
//   • Expose window.OfflineCache for the Settings page (status + refresh).
//
// Guest sessions: pre-caching is skipped (guests can't access /api/me or
// species endpoints in write mode, but we still show the offline banner).

(function () {
  'use strict';

  // ── Constants ─────────────────────────────────────────────────────────────
  var LS_CACHED_AT  = 'fid_species_cached_at';    // ISO timestamp
  var LS_CACHED_N   = 'fid_species_cached_n';     // count
  var PRECACHE_BATCH  = 5;     // concurrent profile fetches
  var PRECACHE_GAP_MS = 80;    // ms between batches (avoids hammering server)
  var PRECACHE_INTERVAL_MS = 6 * 24 * 60 * 60 * 1000; // re-cache after 6 days

  // CSS selectors for write-action elements, scoped to body.offline-mode.
  // Covers review.html, species.html, scan.html write controls.
  var WRITE_CSS = [
    // review.html — per-card approve / reject
    'button.approve', 'button.reject',
    // review.html — bulk toolbar
    '.btn-approve-all', '.btn-reject-all',
    // review.html — correction rename save
    '.btn-rrow-save',
    // review.html — dynamically-generated correction save buttons
    '[id^="corr-save-btn-"]',
    // review.html — GPS, location-approve, AI draft buttons
    '.btn-gps-set', '.btn-loc-approve',
    '.btn-ai-approve', '.btn-ai-reject', '.btn-ai-edit',
    // review.html — edibility condition save
    '.edib-save-btn',
    // review.html — onclick-based (no stable class)
    'button[onclick*="saveNotes"]',
    'button[onclick*="saveEnrichField"]',
    'button[onclick*="saveLocAndApprove"]',
    'button[onclick*="approveAllDrafts"]',
    // species.html — inline field editing + rename
    '.field-edit-btn', '.btn-sp-save', '.btn-prof-rename-save',
    // scan.html — upload (already unusable offline, but disable visually)
    '#drop-zone', '.dz-folder-btn',
  ].join(',');

  var TOOLTIP = 'Offline — available when back online';

  // ── Banner ────────────────────────────────────────────────────────────────

  function _showBanner() {
    if (document.getElementById('offline-banner')) return;
    var b = document.createElement('div');
    b.id   = 'offline-banner';
    b.setAttribute('role', 'status');
    b.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:10000',
      'display:flex', 'align-items:center', 'gap:10px',
      'padding:7px 16px',
      'background:#1c2235', 'color:#e8eaf6',
      'font-size:0.83rem', 'font-family:system-ui,sans-serif',
      'box-shadow:0 2px 6px rgba(0,0,0,0.3)',
    ].join(';');
    b.innerHTML =
      '<span style="font-size:1rem">📴</span>' +
      '<strong>Offline — read only</strong>' +
      '<span style="flex:1;font-size:0.76rem;opacity:0.75">' +
        'Map and species data available from cache. ' +
        'Write actions will be available when back online.' +
      '</span>';
    // Nudge page content down so banner doesn't overlap the top nav
    document.body.style.paddingTop =
      (parseInt(document.body.style.paddingTop || '0', 10) + 36) + 'px';
    document.body.insertBefore(b, document.body.firstChild);
  }

  function _hideBanner() {
    var b = document.getElementById('offline-banner');
    if (b) {
      document.body.style.paddingTop =
        Math.max(0, parseInt(document.body.style.paddingTop || '0', 10) - 36) + 'px';
      b.parentNode.removeChild(b);
    }
  }

  // ── Offline-mode CSS ──────────────────────────────────────────────────────

  var _styleInjected = false;
  function _injectStyles() {
    if (_styleInjected) return;
    _styleInjected = true;
    var s = document.createElement('style');
    s.id = 'fid-offline-styles';
    // Build the scoped rule once — all selectors prefixed with the body class.
    var rules = WRITE_CSS.split(',').map(function (sel) {
      return 'body.offline-mode ' + sel.trim();
    }).join(',\n');
    s.textContent =
      rules + ' {\n' +
      '  opacity: 0.42 !important;\n' +
      '  pointer-events: none !important;\n' +
      '  cursor: not-allowed !important;\n' +
      '  user-select: none !important;\n' +
      '}\n';
    document.head.appendChild(s);
  }

  // ── Title / tooltip on write elements ────────────────────────────────────
  // Runs immediately + via MutationObserver so dynamically-rendered buttons
  // (review cards are built from JS) also get the tooltip.

  function _markElements() {
    if (!document.body.classList.contains('offline-mode')) return;
    try {
      document.querySelectorAll(WRITE_CSS).forEach(function (el) {
        if (!el.dataset.offlineMarked) {
          el.dataset.offlineMarked = '1';
          el.dataset.prevTitle = el.title || '';
          el.title = TOOLTIP;
        }
      });
    } catch (e) {}
  }

  function _unmarkElements() {
    document.querySelectorAll('[data-offline-marked]').forEach(function (el) {
      el.title = el.dataset.prevTitle || '';
      delete el.dataset.offlineMarked;
      delete el.dataset.prevTitle;
    });
  }

  var _observer = null;

  function _startObserver() {
    if (_observer || typeof MutationObserver === 'undefined') return;
    _observer = new MutationObserver(function () { _markElements(); });
    _observer.observe(document.body, { childList: true, subtree: true });
  }

  function _stopObserver() {
    if (_observer) { _observer.disconnect(); _observer = null; }
  }

  // ── Mode switch ───────────────────────────────────────────────────────────

  function _setOffline(offline) {
    if (offline) {
      _injectStyles();
      document.body.classList.add('offline-mode');
      _showBanner();
      _markElements();
      _startObserver();
    } else {
      document.body.classList.remove('offline-mode');
      _hideBanner();
      _unmarkElements();
      _stopObserver();
    }
  }

  // ── Species pre-caching ───────────────────────────────────────────────────

  function _shouldPrecache() {
    try {
      var ts = localStorage.getItem(LS_CACHED_AT);
      if (!ts) return true;
      return (Date.now() - new Date(ts).getTime()) > PRECACHE_INTERVAL_MS;
    } catch (e) { return true; }
  }

  function _delay(ms) {
    return new Promise(function (res) { setTimeout(res, ms); });
  }

  async function _precacheSpecies(force) {
    if (_wasOffline) return;
    if (!force && !_shouldPrecache()) return;
    if (typeof fetch === 'undefined') return;

    try {
      // Fetch the confirmed-species list (array of {scientific_name, ...})
      var r = await fetch('/api/species/');
      if (!r.ok) return;
      var list = await r.json();
      if (!Array.isArray(list) || !list.length) return;

      var names = list.map(function (s) { return s.scientific_name; }).filter(Boolean);
      var count = 0;

      for (var i = 0; i < names.length; i += PRECACHE_BATCH) {
        var batch = names.slice(i, i + PRECACHE_BATCH);
        await Promise.all(batch.map(function (name) {
          // The SW's speciesFirst handler will cache this response.
          return fetch('/api/species/' + encodeURIComponent(name) + '/profile')
            .then(function (res) { if (res.ok) count++; })
            .catch(function () {});
        }));
        if (i + PRECACHE_BATCH < names.length) await _delay(PRECACHE_GAP_MS);
      }

      try {
        localStorage.setItem(LS_CACHED_AT, new Date().toISOString());
        localStorage.setItem(LS_CACHED_N,  String(count));
      } catch (e) {}

      if (window.OfflineCache && typeof window.OfflineCache.onCacheRefresh === 'function') {
        window.OfflineCache.onCacheRefresh({ count: count });
      }

    } catch (e) { /* network may have failed mid-run — silently bail */ }
  }

  // ── Reachability ping ──────────────────────────────────────────────────────
  var PING_URL          = '/health';
  var PING_INTERVAL_MS  = 15000;
  var PING_TIMEOUT_MS   = 3000;
  var FAIL_THRESHOLD    = 2;

  var _consecutiveFails = 0;
  var _pingTimer        = null;
  var _wasOffline       = false;

  async function _ping() {
    try {
      var r = await fetch(PING_URL, { method: 'GET', cache: 'no-store',
        signal: AbortSignal.timeout(PING_TIMEOUT_MS) });
      if (r.ok) {
        _consecutiveFails = 0;
        if (_wasOffline) {
          _wasOffline = false;
          _setOffline(false);
          setTimeout(function () { _precacheSpecies(true); }, 2500);
        }
      } else {
        _onPingFail();
      }
    } catch (e) {
      _onPingFail();
    }
  }

  function _onPingFail() {
    _consecutiveFails++;
    if (_consecutiveFails >= FAIL_THRESHOLD && !_wasOffline) {
      _wasOffline = true;
      _setOffline(true);
    }
  }

  // ── Init ──────────────────────────────────────────────────────────────────

  function _init() {
    _ping();
    _pingTimer = setInterval(_ping, PING_INTERVAL_MS);

    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible') _ping();
    });
    window.addEventListener('focus', function () { _ping(); });

    setTimeout(function () { _precacheSpecies(false); }, 6000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _init);
  } else {
    _init();
  }

  // ── Public API (for Settings page) ───────────────────────────────────────

  window.OfflineCache = {
    // Called by Settings to get current cache state from localStorage
    getStatus: function () {
      var cachedAt = null, count = 0;
      try {
        cachedAt = localStorage.getItem(LS_CACHED_AT);
        count    = parseInt(localStorage.getItem(LS_CACHED_N) || '0', 10);
      } catch (e) {}
      return { cachedAt: cachedAt, count: count };
    },

    // Called by Settings "Refresh" button — clears SW species cache then re-caches
    refresh: async function () {
      try {
        localStorage.removeItem(LS_CACHED_AT);
        localStorage.removeItem(LS_CACHED_N);
      } catch (e) {}

      // Ask the SW to clear its SPECIES_CACHE
      if (navigator.serviceWorker && navigator.serviceWorker.controller) {
        navigator.serviceWorker.controller.postMessage({ type: 'clear-species-cache' });
        await _delay(300);  // give SW time to clear before we re-fetch
      }

      await _precacheSpecies(true);
    },

    // Callback set by Settings page before calling refresh()
    onCacheRefresh: null,
  };

})();
