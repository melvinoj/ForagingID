// ── GPS Walk Recording (Prompt A) ────────────────────────────────────────
(function () {
  'use strict';

  var _recTrace          = null;   // Leaflet polyline for the live trace
  var _tracePoints       = [];     // LatLng array mirrored from WalkRecorder
  var _hudTimer          = null;
  var _pendingSession    = null;   // data returned by WalkRecorder.stop(), held until save
  var _audioRecorder     = null;   // MediaRecorder instance
  var _audioChunks       = [];
  var _audioBlob         = null;
  var _wsmAudioRecording = false;
  var _hudAudioRecorder  = null;   // inline HUD audio recorder
  var _hudAudioChunks    = [];
  var _hudAudioRecording = false;

  // ── Accuracy warning ────────────────────────────────────────────────────

  function _wrecAccuracyCancel() {
    document.getElementById('walk-rec-accuracy-modal').classList.remove('visible');
  }

  function _wrecAccuracyProceed() {
    document.getElementById('walk-rec-accuracy-modal').classList.remove('visible');
    _startRecording();
  }

  window._wrecAccuracyCancel  = _wrecAccuracyCancel;
  window._wrecAccuracyProceed = _wrecAccuracyProceed;

  // ── Start / toggle ──────────────────────────────────────────────────────

  function _wrecToggle() {
    // Curator only: participants never record walks (the server refuses them too).
    if (document.body.classList.contains('guest-mode') && !WalkRecorder.isRecording()) return;
    if (WalkRecorder.isRecording()) {
      _wrecStop();
    } else {
      // Check GPS accuracy first
      GPS.getOnce().then(function (pos) {
        if (pos.accuracy > 30) {
          document.getElementById('wram-msg').textContent =
            'GPS accuracy is ' + Math.round(pos.accuracy) + ' m (target ≤ 30 m). ' +
            'The recorded trace may be imprecise. Proceed anyway?';
          document.getElementById('walk-rec-accuracy-modal').classList.add('visible');
        } else {
          _startRecording();
        }
      }).catch(function () {
        // No fix yet — warn and offer to proceed
        document.getElementById('wram-msg').textContent =
          'Could not get a GPS fix. Proceed and start recording when signal improves?';
        document.getElementById('walk-rec-accuracy-modal').classList.add('visible');
      });
    }
  }
  window._wrecToggle = _wrecToggle;

  async function _startRecording() {
    // Bug 1 fix: recording no longer needs rectangle-draw mode; restore map drag.
    _detachWalkDraw();

    await WalkRecorder.start();

    // Live trace polyline — same style as the saved-trace renderer
    _tracePoints = [];
    _recTrace = L.polyline([], {
      color: '#2d5016', weight: 3.5, opacity: 0.85,
    }).addTo(map);

    // HUD
    document.getElementById('walk-rec-hud').classList.add('active');
    // Bug 4 fix: HUD changes map height — tell Leaflet so tile/polyline coords align.
    map.invalidateSize();

    // Wake-lock notice (always shown — tells user to keep screen on)
    var note = document.getElementById('walk-rec-wakelock-note');
    note.classList.add('visible');
    setTimeout(function () { note.classList.remove('visible'); }, 5000);

    // Update float button state
    var btn = document.getElementById('wrec-float-btn');
    if (btn) { btn.classList.add('recording'); btn.title = 'Recording…'; }

    // Subscribe to live state updates
    WalkRecorder.onStateChange(_onRecState);

    // HUD clock ticker
    _hudTimer = setInterval(_refreshHud, 1000);
  }

  function _onRecState(state) {
    // Extend the trace polyline with new points
    var pts = state.trackPoints;
    if (pts.length > _tracePoints.length) {
      var newPts = pts.slice(_tracePoints.length);
      newPts.forEach(function (p) {
        var ll = L.latLng(p.lat, p.lng);
        _tracePoints.push(ll);
        if (_recTrace) _recTrace.addLatLng(ll);
      });
    }
    _refreshHud(state);
  }

  function _refreshHud(state) {
    state = state || WalkRecorder.getState();
    if (!state.recording) return;
    // Distance
    var dm = state.distanceM;
    document.getElementById('wrec-dist').textContent =
      dm >= 1000 ? (dm / 1000).toFixed(2) + ' km' : dm + ' m';
    // Duration
    var s = state.durationS;
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var ss = s % 60;
    document.getElementById('wrec-dur').textContent =
      (h ? h + ':' : '') +
      (h ? String(m).padStart(2, '0') : m) + ':' +
      String(ss).padStart(2, '0');
  }

  // ── Stop ────────────────────────────────────────────────────────────────

  function _wrecStop() {
    var session = WalkRecorder.stop();
    if (!session) return;
    _pendingSession = session;

    WalkRecorder.offStateChange(_onRecState);
    clearInterval(_hudTimer);
    _hudTimer = null;

    document.getElementById('walk-rec-hud').classList.remove('active');
    var btn = document.getElementById('wrec-float-btn');
    if (btn) { btn.classList.remove('recording'); btn.title = 'Record walk'; }

    // Keep trace on map — _openSaveModal clears it after save/cancel
    _openSaveModal(session);
  }
  window._wrecStop = _wrecStop;

  // ── Audio note (in-HUD inline recording) ───────────────────────────────

  async function _wrecAudioNote() {
    if (!WalkRecorder.isRecording()) return;
    var hudBtn = document.querySelector('.wrec-btn-audio');

    if (_hudAudioRecording) {
      // Second tap — stop
      if (_hudAudioRecorder) _hudAudioRecorder.stop();
      return;
    }

    try {
      var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      _hudAudioChunks  = [];
      _hudAudioRecorder = new MediaRecorder(stream);
      _hudAudioRecorder.ondataavailable = function (e) {
        if (e.data.size > 0) _hudAudioChunks.push(e.data);
      };
      _hudAudioRecorder.onstop = function () {
        _audioBlob = new Blob(_hudAudioChunks, { type: 'audio/webm' });
        stream.getTracks().forEach(function (t) { t.stop(); });
        _hudAudioRecording = false;
        _hudAudioRecorder  = null;
        if (hudBtn) { hudBtn.classList.remove('recording'); hudBtn.textContent = '🎤✓'; }
        _showLocateToast('Audio note saved — will attach on stop');
      };
      _hudAudioRecorder.start();
      _hudAudioRecording = true;
      if (hudBtn) { hudBtn.classList.add('recording'); hudBtn.textContent = '⏹'; }
    } catch (_) {
      _showLocateToast('Microphone unavailable');
    }
  }
  window._wrecAudioNote = _wrecAudioNote;

  // ── Save modal ──────────────────────────────────────────────────────────

  function _openSaveModal(session) {
    // Default name: date + "walk"
    var now = session.startedAt || new Date();
    var dateStr = now.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    document.getElementById('wsm-name-input').value = dateStr + ' walk';
    var hadHudAudio = !!_audioBlob;
    document.getElementById('wsm-audio-status').textContent = hadHudAudio ? 'Voice note ready ✓' : '';
    document.getElementById('wsm-audio-btn').textContent = hadHudAudio ? '🎤 Re-record' : '🎤 Add voice note';
    document.getElementById('wsm-audio-btn').classList.remove('recording');
    document.getElementById('wsm-save-btn').disabled = false;
    if (!hadHudAudio) _audioBlob = null;
    _audioChunks = [];
    _wsmAudioRecording = false;
    document.getElementById('walk-save-modal').classList.add('visible');
  }

  function _wsmClose() {
    document.getElementById('walk-save-modal').classList.remove('visible');
    // Discard pending trace
    if (_recTrace) { map.removeLayer(_recTrace); _recTrace = null; }
    _tracePoints   = [];
    _pendingSession = null;
    if (_audioRecorder && _audioRecorder.state !== 'inactive') {
      _audioRecorder.stop();
    }
  }
  window._wsmClose = _wsmClose;

  async function _wsmToggleAudio() {
    if (_wsmAudioRecording) {
      // Stop recording
      if (_audioRecorder) _audioRecorder.stop();
      return;
    }
    try {
      var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      _audioChunks  = [];
      _audioRecorder = new MediaRecorder(stream);
      _audioRecorder.ondataavailable = function (e) {
        if (e.data.size > 0) _audioChunks.push(e.data);
      };
      _audioRecorder.onstop = function () {
        _audioBlob = new Blob(_audioChunks, { type: 'audio/webm' });
        stream.getTracks().forEach(function (t) { t.stop(); });
        _wsmAudioRecording = false;
        document.getElementById('wsm-audio-btn').textContent = '🎤 Re-record';
        document.getElementById('wsm-audio-btn').classList.remove('recording');
        document.getElementById('wsm-audio-status').textContent = 'Voice note ready ✓';
      };
      _audioRecorder.start();
      _wsmAudioRecording = true;
      document.getElementById('wsm-audio-btn').textContent = '⏹ Stop recording';
      document.getElementById('wsm-audio-btn').classList.add('recording');
      document.getElementById('wsm-audio-status').textContent = 'Recording…';
    } catch (_) {
      document.getElementById('wsm-audio-status').textContent = 'Microphone unavailable';
    }
  }
  window._wsmToggleAudio = _wsmToggleAudio;

  async function _wsmSave() {
    var btn = document.getElementById('wsm-save-btn');
    btn.disabled = true;
    btn.textContent = 'Saving…';

    var name    = (document.getElementById('wsm-name-input').value || '').trim() ||
                  new Date().toLocaleDateString('en-GB') + ' walk';
    var session = _pendingSession;
    if (!session) { _wsmClose(); return; }

    // Layer 1 — GPX download (belt: works regardless of connectivity)
    _gpxDownload(name, session);

    // Layer 2 — Write to IndexedDB immediately, status=pending
    var idbId = _walkUuid();
    var audioBuf = null;
    if (_audioBlob) {
      try { audioBuf = await _audioBlob.arrayBuffer(); } catch (_) {}
    }
    var idbRecord = {
      id:            idbId,
      name:          name,
      started_at:    session.startedAt.toISOString(),
      ended_at:      session.endedAt.toISOString(),
      distance_m:    session.distanceM,
      duration_s:    session.durationS,
      track_points:  session.trackPoints.map(function (p) {
        return { lat: p.lat, lng: p.lng, alt: p.alt || null, ts: p.ts };
      }),
      audio_note_blob:     audioBuf,
      observation_ids:     (session.proximityEncounters || []).map(function (e) { return e.observation_id; }),
      proximity_encounters: session.proximityEncounters,
      status:        'pending',
    };
    await _walkIdbPut(idbRecord);

    // Upload audio note to server if recorded
    var audioPath = null;
    if (_audioBlob) {
      try {
        var fd = new FormData();
        fd.append('file', _audioBlob, 'walk-note.webm');
        var ur = await fetch('/api/recorded-walks/audio-upload', { method: 'POST', body: fd });
        if (ur.ok) { var ud = await ur.json(); audioPath = ud.path; }
      } catch (_) {}
    }

    var payload = {
      name:         name,
      started_at:   session.startedAt.toISOString(),
      ended_at:     session.endedAt.toISOString(),
      distance_m:   session.distanceM,
      duration_s:   session.durationS,
      track_points: idbRecord.track_points,
      audio_note_path:      audioPath,
      proximity_encounters: session.proximityEncounters,
    };

    var serverOk = false;
    try {
      var r = await fetch('/api/recorded-walks', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!r.ok) throw new Error('save failed');
      serverOk = true;
    } catch (_) {}

    if (serverOk) {
      await _walkIdbSetStatus(idbId, 'synced');
      _showLocateToast('Walk saved ✓');
    } else {
      await _walkIdbSetStatus(idbId, 'pending');
      _showLocateToast('Saved locally — sync when back on WiFi');
    }

    _walkUpdateSyncBtn();
    document.getElementById('walk-save-modal').classList.remove('visible');
    if (_recTrace) { map.removeLayer(_recTrace); _recTrace = null; }
    _tracePoints    = [];
    _pendingSession = null;
    _audioBlob      = null;
  }
  window._wsmSave = _wsmSave;

  // ── IndexedDB helpers ────────────────────────────────────────────────────

  var _walkIdbName    = 'foragingid_walks';
  var _walkIdbVersion = 1;
  var _walkIdbDb      = null;

  function _walkIdbOpen() {
    if (_walkIdbDb) return Promise.resolve(_walkIdbDb);
    return new Promise(function (resolve, reject) {
      var req = indexedDB.open(_walkIdbName, _walkIdbVersion);
      req.onupgradeneeded = function (e) {
        var db = e.target.result;
        if (!db.objectStoreNames.contains('walks')) {
          db.createObjectStore('walks', { keyPath: 'id' });
        }
      };
      req.onsuccess = function (e) { _walkIdbDb = e.target.result; resolve(_walkIdbDb); };
      req.onerror   = function (e) { reject(e.target.error); };
    });
  }

  async function _walkIdbPut(record) {
    try {
      var db = await _walkIdbOpen();
      return new Promise(function (resolve, reject) {
        var tx = db.transaction('walks', 'readwrite');
        tx.objectStore('walks').put(record);
        tx.oncomplete = resolve;
        tx.onerror    = function (e) { reject(e.target.error); };
      });
    } catch (_) {}
  }

  async function _walkIdbSetStatus(id, status) {
    try {
      var db = await _walkIdbOpen();
      return new Promise(function (resolve, reject) {
        var tx    = db.transaction('walks', 'readwrite');
        var store = tx.objectStore('walks');
        var req   = store.get(id);
        req.onsuccess = function () {
          if (!req.result) { resolve(); return; }
          req.result.status = status;
          store.put(req.result);
        };
        tx.oncomplete = resolve;
        tx.onerror    = function (e) { reject(e.target.error); };
      });
    } catch (_) {}
  }

  async function _walkIdbGetPending() {
    try {
      var db = await _walkIdbOpen();
      return new Promise(function (resolve, reject) {
        var tx      = db.transaction('walks', 'readonly');
        var results = [];
        tx.objectStore('walks').openCursor().onsuccess = function (e) {
          var cursor = e.target.result;
          if (cursor) {
            if (cursor.value.status === 'pending') results.push(cursor.value);
            cursor.continue();
          }
        };
        tx.oncomplete = function () { resolve(results); };
        tx.onerror    = function (e) { reject(e.target.error); };
      });
    } catch (_) { return []; }
  }

  function _walkUuid() {
    if (crypto && crypto.randomUUID) return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
      var r = Math.random() * 16 | 0;
      return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
  }

  // ── GPX export (Layer 1) ────────────────────────────────────────────────

  function _gpxDownload(name, session) {
    var gpx = _buildGpx(name, session);
    var blob = new Blob([gpx], { type: 'application/gpx+xml' });
    var url  = URL.createObjectURL(blob);
    var a    = document.createElement('a');
    var dateSlug = (session.startedAt || new Date()).toISOString().slice(0, 10);
    var nameSafe = name.replace(/[^a-zA-Z0-9_-]/g, '_');
    a.href     = url;
    a.download = nameSafe + '_' + dateSlug + '.gpx';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 5000);
  }

  function _buildGpx(name, session) {
    var esc = window.lmEsc;   // XML-safe too (static/js/esc.js)
    var startIso = (session.startedAt || new Date()).toISOString();
    var trkpts = (session.trackPoints || []).map(function (p) {
      var ts  = new Date(p.ts).toISOString();
      var ele = p.alt != null ? '\n      <ele>' + p.alt + '</ele>' : '';
      return '    <trkpt lat="' + p.lat + '" lon="' + p.lng + '">' + ele + '\n      <time>' + ts + '</time>\n    </trkpt>';
    }).join('\n');
    return '<?xml version="1.0" encoding="UTF-8"?>\n' +
      '<gpx version="1.1" creator="LandMemory" xmlns="http://www.topografix.com/GPX/1/1">\n' +
      '  <metadata>\n' +
      '    <name>' + esc(name) + '</name>\n' +
      '    <time>' + startIso + '</time>\n' +
      '  </metadata>\n' +
      '  <trk>\n' +
      '    <name>' + esc(name) + '</name>\n' +
      '    <trkseg>\n' + trkpts + '\n    </trkseg>\n' +
      '  </trk>\n' +
      '</gpx>';
  }

  // ── Sync button (Layer 3) ───────────────────────────────────────────────

  async function _walkUpdateSyncBtn() {
    var btn    = document.getElementById('walk-sync-btn');    // desktop sidebar
    var wbsUp  = document.getElementById('wbs-upload');       // phone bottom sheet
    var wbsBtn = document.getElementById('wbs-sync-btn');
    try {
      var pending = await _walkIdbGetPending();
      if (pending.length > 0) {
        var label = '↑ Upload pending walks (' + pending.length + ')';
        if (btn) { btn.textContent = label; btn.classList.add('visible'); btn.disabled = false; }
        if (wbsBtn) { wbsBtn.textContent = label; wbsBtn.disabled = false; }
        if (wbsUp) wbsUp.style.display = 'block';
      } else {
        if (btn) btn.classList.remove('visible');
        if (wbsUp) wbsUp.style.display = 'none';
      }
    } catch (_) {
      if (btn) btn.classList.remove('visible');
      if (wbsUp) wbsUp.style.display = 'none';
    }
  }
  window._walkUpdateSyncBtn = _walkUpdateSyncBtn;

  window._walkSyncPending = async function () {
    var btn       = document.getElementById('walk-sync-btn');
    var wbsBtn    = document.getElementById('wbs-sync-btn');
    var wbsStatus = document.getElementById('wbs-sync-status');
    if (btn)    { btn.disabled    = true; btn.textContent    = 'Uploading…'; }
    if (wbsBtn) { wbsBtn.disabled = true; wbsBtn.textContent = 'Uploading…'; }
    if (wbsStatus) wbsStatus.innerHTML = '';

    var pending = await _walkIdbGetPending();
    console.log('[walk-sync] pending walks in IDB:', pending.length, pending.map(function(w){ return {id:w.id, name:w.name, started_at:w.started_at, ended_at:w.ended_at}; }));
    if (!pending.length) { _walkUpdateSyncBtn(); return; }

    // Build per-walk status rows in the bottom sheet
    if (wbsStatus) {
      wbsStatus.innerHTML = pending.map(function (w) {
        return '<div class="wbs-sync-row" id="wssr-' + w.id + '">' +
          '<span class="wbs-sync-name">' + _esc(w.name || 'Walk') + '</span>' +
          '<span class="wbs-sync-skip" id="wsst-' + w.id + '">…</span>' +
        '</div>';
      }).join('') + '<div id="wbs-sync-summary"></div>';
    }

    function _setRow(id, cls, text) {
      var el = document.getElementById('wsst-' + id);
      if (el) { el.className = cls; el.textContent = text; }
    }

    var ok = 0, skip = 0, fail = 0;

    // Fetch existing walks once for duplicate guard
    var existing = [];
    try {
      var checkR = await fetch('/api/recorded-walks');
      if (checkR.ok) existing = await checkR.json();
    } catch (e) {
      console.warn('[walk-sync] could not fetch existing walks for dup-check:', e);
    }

    for (var i = 0; i < pending.length; i++) {
      var w = pending[i];
      console.log('[walk-sync] processing walk', w.id, w.name, '— started_at:', w.started_at, 'ended_at:', w.ended_at);
      try {
        // Duplicate guard
        var dup = existing.some(function (e) {
          return e.name === w.name && e.started_at && w.started_at &&
                 Math.abs(new Date(e.started_at) - new Date(w.started_at)) < 2000;
        });
        if (dup) {
          console.log('[walk-sync] walk', w.id, 'already on server — skipping');
          await _walkIdbSetStatus(w.id, 'synced');
          _setRow(w.id, 'wbs-sync-skip', 'Already synced');
          skip++;
          continue;
        }

        // Upload audio if blob stored
        var audioPath = null;
        if (w.audio_note_blob) {
          try {
            var blob = new Blob([w.audio_note_blob], { type: 'audio/webm' });
            var fd   = new FormData();
            fd.append('file', blob, 'walk-note.webm');
            var ur = await fetch('/api/recorded-walks/audio-upload', { method: 'POST', body: fd });
            if (ur.ok) { var ud = await ur.json(); audioPath = ud.path; }
            else console.warn('[walk-sync] audio upload failed for walk', w.id, ur.status, await ur.text());
          } catch (ae) { console.warn('[walk-sync] audio upload exception for walk', w.id, ae); }
        }

        var payload = {
          name:                 w.name,
          started_at:           w.started_at,
          ended_at:             w.ended_at,
          distance_m:           w.distance_m,
          duration_s:           w.duration_s,
          track_points:         w.track_points,
          audio_note_path:      audioPath,
          proximity_encounters: w.proximity_encounters || [],
        };
        console.log('[walk-sync] POSTing walk', w.id, '— payload keys:', Object.keys(payload), 'track_points:', (w.track_points||[]).length);
        var r = await fetch('/api/recorded-walks', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        if (!r.ok) {
          var errBody = await r.text();
          console.error('[walk-sync] POST /api/recorded-walks failed for walk', w.id, '— HTTP', r.status, errBody);
          throw new Error('HTTP ' + r.status + ': ' + errBody);
        }
        await _walkIdbSetStatus(w.id, 'synced');
        _setRow(w.id, 'wbs-sync-ok', '✓');
        ok++;
      } catch (e) {
        console.error('[walk-sync] failed walk', w.id, w.name, e);
        _setRow(w.id, 'wbs-sync-err', 'Failed');
        fail++;
      }
    }

    // Summary line
    var summaryEl = document.getElementById('wbs-sync-summary');
    if (summaryEl) {
      if (fail === 0) {
        summaryEl.style.color = '#2d6a2d';
        summaryEl.textContent = ok + ' uploaded' + (skip ? ', ' + skip + ' already synced' : '') + ' ✓';
      } else {
        summaryEl.style.color = '#b91c1c';
        summaryEl.textContent = fail + ' failed — see console for details' + (ok ? ' (' + ok + ' uploaded)' : '');
      }
    }
    console.log('[walk-sync] done — ok:', ok, 'skipped:', skip, 'failed:', fail);

    _walkUpdateSyncBtn();
    loadRecordedWalksList();
  };

  // Initialise sync button on load
  _walkUpdateSyncBtn();

  // ── Cache area ──────────────────────────────────────────────────────────

  function _wrecCacheArea() {
    GPS.getOnce().then(function (pos) {
      // ~20 km² ≈ 4.5 km radius ≈ 0.04° lat/lng
      var buf = 0.04;
      var bounds = L.latLngBounds(
        [pos.lat - buf, pos.lng - buf],
        [pos.lat + buf, pos.lng + buf]
      );
      // Request SW to cache tiles in bbox across zoom 12-16
      if (!navigator.serviceWorker || !navigator.serviceWorker.controller) {
        _showLocateToast('Offline caching not available');
        return;
      }
      _showLocateToast('Caching map tiles…');
      var tilesToCache = [];
      [12, 13, 14, 15, 16].forEach(function (z) {
        var nw = _latLngToTile(bounds.getNorth(), bounds.getWest(), z);
        var se = _latLngToTile(bounds.getSouth(), bounds.getEast(), z);
        for (var x = nw.x; x <= se.x; x++) {
          for (var y = nw.y; y <= se.y; y++) {
            tilesToCache.push('https://tile.openstreetmap.org/' + z + '/' + x + '/' + y + '.png');
          }
        }
      });
      navigator.serviceWorker.controller.postMessage({
        type: 'cache-tiles', urls: tilesToCache,
      });
      // Listen for completion
      navigator.serviceWorker.addEventListener('message', function handler(ev) {
        if (ev.data && ev.data.type === 'cache-tiles-done') {
          _showLocateToast('Map tiles cached (' + (ev.data.count || '?') + ' tiles)');
          navigator.serviceWorker.removeEventListener('message', handler);
        }
      });
    }).catch(function () {
      _showLocateToast('Location unavailable — cannot cache area');
    });
  }
  window._wrecCacheArea = _wrecCacheArea;

  function _latLngToTile(lat, lng, z) {
    var n = Math.pow(2, z);
    var x = Math.floor((lng + 180) / 360 * n);
    var latR = lat * Math.PI / 180;
    var y = Math.floor((1 - Math.log(Math.tan(latR) + 1 / Math.cos(latR)) / Math.PI) / 2 * n);
    return { x: x, y: y };
  }

})();

// ── GPS Walk Recording: Playback + Display (Prompt B) ────────────────────
(function () {
  'use strict';

  // Active recorded walk trace state
  var _recWalkId      = null;   // currently displayed recorded walk id
  var _recTraceLayer  = null;   // Leaflet polyline
  var _recPinMarkers  = [];     // thumbnail pin markers

  // ── Helpers ─────────────────────────────────────────────────────────────

  function _fmtDist(m) {
    if (m == null) return '—';
    return m >= 1000 ? (m / 1000).toFixed(2) + ' km' : Math.round(m) + ' m';
  }
  function _fmtDur(s) {
    if (s == null) return '—';
    var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60);
    return h ? h + 'h ' + m + 'm' : m + 'm';
  }
  function _fmtDate(iso) {
    if (!iso) return '';
    try {
      return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
    } catch (_) { return iso.slice(0, 10); }
  }
  function _fmtElev(m) {
    return m != null ? Math.round(m) + ' m' : 'Calculating…';
  }
  // _esc: the page's one (→ static/js/esc.js, batch 15).

  // ── Recorded walks list ──────────────────────────────────────────────────

  window.toggleRecordedWalksList = function () {
    // Delegate to wbs version — wbs list is the only copy now
    _wbsToggleRecordedWalks();
  };

  window.loadRecordedWalksList = async function () {
    var listEl = document.getElementById('wbs-recorded-walks-list');
    if (!listEl) return;
    listEl.innerHTML = '<div style="padding:8px 2px;color:#aaa;font-size:0.75rem">Loading…</div>';
    try {
      var r = await fetch('/api/recorded-walks');
      if (!r.ok) throw new Error();
      var walks = await r.json();
      listEl.innerHTML = !walks.length
        ? '<div style="padding:8px 2px;color:#aaa;font-size:0.75rem">No recorded walks yet.</div>'
        : walks.map(function (w) {
            var dm   = _fmtDist(w.distance_m);
            var dur  = _fmtDur(w.duration_s);
            var date = _fmtDate(w.started_at);
            var elev = w.elevation_gain_m != null ? ' · ↑' + Math.round(w.elevation_gain_m) + 'm' : '';
            return '<div class="rec-walk-row">' +
              '<div class="rec-walk-info" onclick="_openRecordedWalk(' + w.id + ')">' +
                '<div class="rec-walk-name">🔴 ' + _esc(w.name) + '</div>' +
                '<div class="rec-walk-meta">' + date + ' · ' + dm + ' · ' + dur + elev + '</div>' +
              '</div>' +
              '<button class="rec-walk-del" onclick="event.stopPropagation();_deleteRecordedWalk(' + w.id + ')">✕</button>' +
            '</div>';
          }).join('');
    } catch (_) {
      listEl.innerHTML = '<div style="padding:8px 2px;color:#b91c1c;font-size:0.75rem">Failed to load.</div>';
    }
  };

  // ── GPX import ──────────────────────────────────────────────────────────

  window._gpxImportPick = function () {
    var inp = document.getElementById('gpx-file-input');
    if (inp) inp.click();
  };

  window._gpxImportFile = async function (file) {
    if (!file) return;

    // ── Parse ──────────────────────────────────────────────────────────────
    var text;
    try {
      text = await file.text();
    } catch (_) {
      alert('Could not read the file.');
      return;
    }

    var doc;
    try {
      doc = new DOMParser().parseFromString(text, 'application/xml');
      var parseErr = doc.querySelector('parsererror');
      if (parseErr) throw new Error('XML parse error');
    } catch (_) {
      alert('The file could not be parsed as GPX — it may be corrupted or not a valid GPX file.');
      return;
    }

    // Walk name: <name> inside <trk>, falling back to filename without extension
    var trkNameEl = doc.querySelector('trk > name');
    var name = (trkNameEl && trkNameEl.textContent.trim()) ||
               file.name.replace(/\.gpx$/i, '') ||
               'Imported walk';

    // Track points from all <trkseg> segments in order
    var trkpts = Array.from(doc.querySelectorAll('trkpt'));
    if (!trkpts.length) {
      alert('No track points found in this GPX file.');
      return;
    }

    var trackPoints = [];
    var badPoints   = 0;
    trkpts.forEach(function (pt) {
      var lat = parseFloat(pt.getAttribute('lat'));
      var lng = parseFloat(pt.getAttribute('lon'));
      if (isNaN(lat) || isNaN(lng)) { badPoints++; return; }

      var eleEl  = pt.querySelector('ele');
      var timeEl = pt.querySelector('time');
      var alt    = eleEl ? parseFloat(eleEl.textContent) : null;
      var ts     = timeEl ? Date.parse(timeEl.textContent.trim()) : null;

      trackPoints.push({
        lat: lat,
        lng: lng,
        alt: (eleEl && !isNaN(alt)) ? alt : null,
        ts:  (ts && !isNaN(ts)) ? ts : Date.now(),
      });
    });

    if (!trackPoints.length) {
      alert('No valid track points found (all points were missing lat/lon).');
      return;
    }
    if (badPoints) {
      console.warn('[gpx-import] Skipped ' + badPoints + ' point(s) with missing lat/lon');
    }

    // Derive started_at / ended_at / duration from timestamps
    var firstTs = trackPoints[0].ts;
    var lastTs  = trackPoints[trackPoints.length - 1].ts;
    var startedAt = new Date(firstTs).toISOString();
    var endedAt   = new Date(lastTs).toISOString();
    var durationS = Math.max(0, Math.round((lastTs - firstTs) / 1000));

    // ── POST ──────────────────────────────────────────────────────────────
    var payload = {
      name:                 name,
      started_at:           startedAt,
      ended_at:             endedAt,
      distance_m:           null,    // server computes from track_points
      duration_s:           durationS,
      track_points:         trackPoints,
      audio_note_path:      null,
      proximity_encounters: [],
    };

    try {
      var r = await fetch('/api/recorded-walks', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload),
      });
      if (!r.ok) {
        var body = await r.json().catch(function () { return {}; });
        alert('Import failed: ' + (body.detail || 'HTTP ' + r.status));
        return;
      }
      var saved = await r.json();

      // Open the recorded-walks section and reload the list
      var listEl  = document.getElementById('wbs-recorded-walks-list');
      var arrowEl = document.getElementById('wbs-recorded-walks-arrow');
      if (listEl) listEl.style.display = 'block';
      if (arrowEl) arrowEl.textContent = '▾';
      await loadRecordedWalksList();

      // Show the imported walk on the map
      if (saved && saved.id) _openRecordedWalk(saved.id);

    } catch (err) {
      alert('Import failed: ' + err.message);
    }
  };

  window._deleteRecordedWalk = async function (id) {
    if (!confirm('Delete this recorded walk?')) return;
    try {
      var r = await fetch('/api/recorded-walks/' + id, { method: 'DELETE' });
      if (!r.ok) throw new Error();
      if (_recWalkId === id) _clearRecordedWalkTrace();
      loadRecordedWalksList();
    } catch (_) {
      alert('Delete failed.');
    }
  };

  // ── Open a recorded walk: draw trace + show detail ───────────────────────

  window._openRecordedWalk = async function (id) {
    // Clear previous trace
    _clearRecordedWalkTrace();
    _recWalkId = id;

    try {
      var r = await fetch('/api/recorded-walks/' + id);
      if (!r.ok) throw new Error();
      var walk = await r.json();
      _drawRecordedTrace(walk);
      _placeThumbnailPins(walk, id);
      if (isMobile()) _closeWalkSheet();
      if (_recTraceLayer) map.fitBounds(_recTraceLayer.getBounds(), { padding: [40, 40] });
    } catch (_) {
      _showLocateToast('Failed to load recorded walk');
    }
  };

  function _drawRecordedTrace(walk) {
    var pts = (walk.track_points || []).filter(function (p) {
      return p.lat != null && p.lng != null;
    });
    if (!pts.length) return;
    var lls = pts.map(function (p) { return L.latLng(p.lat, p.lng); });
    _recTraceLayer = L.polyline(lls, {
      color: '#2d5016', weight: 3.5, opacity: 0.85,
    }).addTo(map);
  }

  function _placeThumbnailPins(walk, walkId) {
    var obs = (walk.observations || []).filter(function (o) {
      return o.latitude != null && o.longitude != null;
    });
    obs.forEach(function (o) {
      var thumbName = o.thumbnail_path ? o.thumbnail_path.split('/').pop() : null;
      var html = thumbName
        ? '<div class="rec-thumb-pin"><img src="/thumbnails/' + _esc(thumbName) + '" loading="lazy" onerror="this.parentElement.innerHTML=\'🌿\'"></div>'
        : '<div class="rec-thumb-pin-empty">🌿</div>';
      var icon = L.divIcon({
        className: '', html: html,
        iconSize: [40, 40], iconAnchor: [20, 20],
      });
      var mk = L.marker([o.latitude, o.longitude], { icon: icon, zIndexOffset: 500 })
        .addTo(map);
      mk.on('click', function () {
        window._openRecordedWalk(walkId);
      });
      _recPinMarkers.push(mk);
    });
  }

  function _clearRecordedWalkTrace() {
    if (_recTraceLayer) { map.removeLayer(_recTraceLayer); _recTraceLayer = null; }
    _recPinMarkers.forEach(function (mk) { map.removeLayer(mk); });
    _recPinMarkers = [];
    _recWalkId = null;
  }
  window._clearRecordedWalkTrace = _clearRecordedWalkTrace;

  // ── Walk detail panel ────────────────────────────────────────────────────

  function _showWalkDetail(walk) {
    var sid = document.getElementById('sidebar');

    // Hide all other pane content
    document.getElementById('detail-view').style.display      = 'none';
    document.getElementById('filter-view').style.display      = 'none';
    document.getElementById('walk-detail-view').style.display = 'none';

    document.getElementById('discover-view').classList.remove('active');
    if (typeof _openToolbarPanel !== 'undefined' && _openToolbarPanel) {
      var pEl = document.getElementById('panel-' + _openToolbarPanel);
      var bEl = document.getElementById('btn-panel-' + _openToolbarPanel);
      if (pEl) pEl.style.display = 'none';
      if (bEl) bEl.classList.remove('active');
      _openToolbarPanel = null;
    }

    // Switch to detail mode
    sid.classList.add('rp-detail');
    document.getElementById('rp-pane').classList.add('rp-open');
    if (isMobile()) document.getElementById('drawer-scrim').classList.add('show');

    document.getElementById('walk-detail-title-bar').textContent = walk.name;
    document.getElementById('walk-detail-view').style.display = 'flex';

    _renderWalkDetailContent(walk);
  }

  function _renderWalkDetailContent(walk) {
    var scroll = document.getElementById('walk-detail-scroll');

    // Stats row
    var statsHtml =
      '<div class="wd-stat"><div class="wd-stat-val">' + _fmtDist(walk.distance_m) + '</div><div class="wd-stat-lbl">Distance</div></div>' +
      '<div class="wd-stat"><div class="wd-stat-val">' + _fmtDur(walk.duration_s)  + '</div><div class="wd-stat-lbl">Duration</div></div>' +
      '<div class="wd-stat"><div class="wd-stat-val">' + _fmtElev(walk.elevation_gain_m) + '</div><div class="wd-stat-lbl">↑ Gain</div></div>' +
      '<div class="wd-stat"><div class="wd-stat-val">' + _fmtElev(walk.elevation_loss_m) + '</div><div class="wd-stat-lbl">↓ Loss</div></div>';

    // Elevation chart
    var elevHtml = '';
    var pts = walk.track_points || [];
    if (pts.length >= 2) {
      var svg = _buildElevationSVG(pts);
      if (svg) {
        elevHtml = '<div class="wd-elev-wrap">' +
          '<div class="wd-elev-label">Elevation profile</div>' + svg + '</div>';
      }
    }

    // Photo grid
    var obsWithPhotos = (walk.observations || []).filter(function (o) { return o.thumbnail_path; });
    var photosHtml = '';
    if (obsWithPhotos.length) {
      photosHtml = '<div class="wd-photos-label">Species encountered (' + (walk.observations || []).length + ')</div>' +
        '<div class="wd-photos-grid">' +
        obsWithPhotos.map(function (o) {
          var thumbName = o.thumbnail_path.split('/').pop();
          var sp = _esc(o.species || '');
          var cn = _esc(spCommon(o.common_name || ''));
          return '<div class="wd-photo-cell" onclick="_wdOpenPhoto(' + o.observation_id + ',' + JSON.stringify(o.thumbnail_path) + ',' + JSON.stringify(o.species || '') + ',' + JSON.stringify(o.common_name || '') + ')">' +
            '<img src="/thumbnails/' + _esc(thumbName) + '" loading="lazy" alt="">' +
            (sp ? '<div class="wd-photo-species">' + (cn || sp) + '</div>' : '') +
          '</div>';
        }).join('') + '</div>';
    }

    // Audio player
    var audioHtml = '';
    if (walk.audio_note_path) {
      audioHtml = '<div class="wd-audio-wrap">' +
        '<div class="wd-audio-label">Voice note</div>' +
        '<audio class="wd-audio-player" controls src="/media/recorded-walks/' + _esc(walk.audio_note_path.split('/').pop()) + '"></audio>' +
        '</div>';
    }

    // "Show to guests" (curator only — hidden for guests by guest-mode.js; the
    // PATCH refuses them server-side). Off: participants never see this walk.
    var shareHtml = '<label class="wd-share" data-guest-hide title="Workshop participants see this walk (route and photos) only while this is on. The voice note stays yours.">' +
      '<input type="checkbox" id="wd-share-cb"' + (walk.shared_with_guests ? ' checked' : '') +
      ' onchange="_wdSetShared(' + walk.id + ', this)"> Show to guests' +
      '<span class="wd-share-note" id="wd-share-note"></span></label>';

    scroll.innerHTML =
      '<div class="wd-name">' + _esc(walk.name) + '</div>' +
      '<div class="wd-date">' + _fmtDate(walk.started_at) + '</div>' +
      shareHtml +
      '<div class="wd-stats-row">' + statsHtml + '</div>' +
      elevHtml + photosHtml + audioHtml;
  }

  window._wdSetShared = async function (walkId, cb) {
    var note = document.getElementById('wd-share-note');
    cb.disabled = true;
    try {
      var r = await fetch('/api/recorded-walks/' + walkId + '/share', {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shared: cb.checked }),
      });
      var d = await r.json().catch(function () { return {}; });
      if (!r.ok) throw new Error(d.detail || ('HTTP ' + r.status));
      cb.checked = !!d.shared_with_guests;
      if (note) note.textContent = cb.checked ? ' — guests can see it' : ' — hidden from guests';
    } catch (e) {
      cb.checked = !cb.checked;
      if (note) note.textContent = ' — not saved: ' + e.message;
    }
    cb.disabled = false;
  };

  window._wdBack = function () {
    document.getElementById('walk-detail-view').style.display = 'none';
    document.getElementById('sidebar').classList.remove('rp-detail');
    document.getElementById('rp-pane').classList.remove('rp-open');
    document.getElementById('drawer-scrim').classList.remove('show');
    _openToolbarPanel = null;
  };

  window._wdOpenPhoto = function (obsId, thumbPath, species, commonName) {
    if (window.Lightbox) {
      var thumbName = thumbPath.split('/').pop();
      Lightbox.open({
        src:     '/thumbnails/' + thumbName,
        caption: spCommon(commonName) || species || '',
        obsId:   obsId,
      });
    }
  };

  // ── Elevation SVG chart ──────────────────────────────────────────────────

  function _buildElevationSVG(trackPoints) {
    // Filter to points with altitude data
    var pts = trackPoints.filter(function (p) { return p.alt != null; });
    if (pts.length < 2) return null;   // no altitude data available

    // Compute cumulative distance for X axis
    var xs = [0];
    for (var i = 1; i < pts.length; i++) {
      var prev = pts[i - 1], cur = pts[i];
      var R = 6371000;
      var f1 = prev.lat * Math.PI / 180, f2 = cur.lat * Math.PI / 180;
      var df = (cur.lat - prev.lat) * Math.PI / 180;
      var dl = (cur.lng - prev.lng) * Math.PI / 180;
      var a  = Math.sin(df/2)**2 + Math.cos(f1)*Math.cos(f2)*Math.sin(dl/2)**2;
      xs.push(xs[xs.length - 1] + R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
    }
    var alts = pts.map(function (p) { return p.alt; });
    var minAlt = Math.min.apply(null, alts);
    var maxAlt = Math.max.apply(null, alts);
    var totalDist = xs[xs.length - 1];

    if (totalDist === 0 || maxAlt === minAlt) return null;

    var W = 280, H = 72, PAD = 4;
    var toX = function (d) { return PAD + (d / totalDist) * (W - PAD * 2); };
    var toY = function (a) { return H - PAD - ((a - minAlt) / (maxAlt - minAlt)) * (H - PAD * 2); };

    // Build polyline points
    var polyPts = pts.map(function (p, i) { return toX(xs[i]) + ',' + toY(alts[i]); }).join(' ');
    // Fill polygon (close to bottom)
    var fillPts = polyPts +
      ' ' + toX(totalDist) + ',' + (H - PAD) +
      ' ' + toX(0) + ',' + (H - PAD);

    return '<svg class="wd-elev-svg" viewBox="0 0 ' + W + ' ' + H + '" height="80" preserveAspectRatio="none">' +
      '<polygon points="' + fillPts + '" fill="rgba(180,60,40,0.15)" stroke="none"/>' +
      '<polyline points="' + polyPts + '" fill="none" stroke="#c0392b" stroke-width="1.5" stroke-linejoin="round"/>' +
      '</svg>';
  }

  // ── Walk panel: minimise / restore ───────────────────────────────────────

  window._walkMinimise = function () {
    // Store current title/distance in the bar
    var title = (document.getElementById('walk-title') || {}).textContent || 'Walk Route';
    var sub   = (document.getElementById('walk-sub')   || {}).textContent || '';
    document.getElementById('wmb-name').textContent = title.replace('🥾 ', '');
    document.getElementById('wmb-dist').textContent = sub;
    document.getElementById('walk-min-bar').classList.add('visible');
    // Close the sidebar pane but keep walk active
    document.getElementById('rp-pane').classList.remove('rp-open');
    document.getElementById('drawer-scrim').classList.remove('show');
    _openToolbarPanel = null;
  };

  window._walkRestore = function () {
    document.getElementById('walk-min-bar').classList.remove('visible');
    // Re-open Walk view in the panel
    if (typeof setLayer === 'function') setLayer('walk');
  };

  // Hide bar when walk is cleared
  var _origExitWalkMode = window._exitWalkMode;
  window._exitWalkMode = function () {
    document.getElementById('walk-min-bar').classList.remove('visible');
    _clearRecordedWalkTrace();
    if (typeof _origExitWalkMode === 'function') _origExitWalkMode.apply(this, arguments);
  };

  // ── Walk panel: tab switcher ─────────────────────────────────────────────

  window._walkTab = function (name) {
    var stops = document.getElementById('walk-tab-stops');
    var stats = document.getElementById('walk-tab-stats');
    var btnS  = document.getElementById('walk-tab-btn-stops');
    var btnW  = document.getElementById('walk-tab-btn-stats');
    if (name === 'stops') {
      if (stops) stops.style.display = 'flex';
      if (stats) stats.style.display = 'none';
      if (btnS) { btnS.classList.add('active');    }
      if (btnW) { btnW.classList.remove('active'); }
    } else {
      if (stops) stops.style.display = 'none';
      if (stats) { stats.style.display = 'block'; _renderWalkStats(); }
      if (btnS) { btnS.classList.remove('active'); }
      if (btnW) { btnW.classList.add('active');    }
    }
  };

  function _renderWalkStats() {
    var el = document.getElementById('walk-stats-rows');
    if (!el) return;
    var distM  = (typeof _walkOrsDistM  !== 'undefined') ? _walkOrsDistM  : null;
    var durMin = (typeof _walkOrsDurMin !== 'undefined') ? _walkOrsDurMin : null;
    var stops  = (typeof _activeWalkRoute !== 'undefined' && _activeWalkRoute) ? _activeWalkRoute.length : 0;
    el.innerHTML =
      '<div class="wts-row"><span class="wts-key">Distance</span><span class="wts-val">' + (distM ? _fmtDist(distM) : '—') + '</span></div>' +
      '<div class="wts-row"><span class="wts-key">Est. duration</span><span class="wts-val">' + (durMin ? durMin + ' min' : '—') + '</span></div>' +
      '<div class="wts-row"><span class="wts-key">Species stops</span><span class="wts-val">' + stops + '</span></div>';
    // Publish block: a loaded saved walk only (walk-publish.js hides itself otherwise).
    if (window.WalkPublish) {
      var sw = (typeof _savedWalkView !== 'undefined' && _savedWalkView && _savedWalkData) ? _savedWalkData : null;
      WalkPublish.show(sw ? sw.id : null, sw ? sw.name : '');
    }
  }

  // ── Walk panel: live recording stats ─────────────────────────────────────

  function _onRecStateWalkPanel(state) {
    var liveEl = document.getElementById('walk-live-stats');
    var tabsEl = document.getElementById('walk-tabs');
    if (!liveEl) return;
    if (state.recording) {
      liveEl.classList.add('active');
      if (tabsEl) tabsEl.style.display = 'none';
      document.getElementById('wls-dist').textContent = _fmtDist(state.distanceM);
      // Duration
      var s  = state.durationS;
      var h  = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = s % 60;
      document.getElementById('wls-dur').textContent =
        (h ? h + ':' : '') + (h ? String(m).padStart(2,'0') : m) + ':' + String(ss).padStart(2,'0');
      document.getElementById('wls-enc').textContent = state.proximityEncounters.length;
    } else {
      liveEl.classList.remove('active');
      if (tabsEl) tabsEl.style.display = 'flex';
    }
  }

  if (window.WalkRecorder) {
    WalkRecorder.onStateChange(_onRecStateWalkPanel);
  }

  // Also ensure the walk-detail-view is hidden when openSidebar/backToFilters runs
  var _origOpenSidebar = window.openSidebar;
  window.openSidebar = function () {
    document.getElementById('walk-detail-view').style.display = 'none';
    if (typeof _origOpenSidebar === 'function') _origOpenSidebar.apply(this, arguments);
  };

  // ── Audio file serving ────────────────────────────────────────────────────
  // Audio files are served via the static /media-file?path=... endpoint;
  // the backend needs a small passthrough route if not already present.
  // (Added in the backend below if missing.)

})();

