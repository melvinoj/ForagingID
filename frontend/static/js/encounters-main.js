(function () {
  'use strict';

  // -- Shared state -------------------------------------------
  var _species = [];
  var _lat = null, _lng = null;
  var _recorder = null, _chunks = [], _audioBlob = null, _audioName = null;
  var _stream = null, _audioCtx = null, _analyser = null, _rafId = null;
  var _wakeLock = null;
  var _viewUserId = null;  // set when ?user_id= is in URL (curator viewing a participant)

  // -- Init ---------------------------------------------------
  // IMPORTANT: loadMySeason, loadEncounters, and the tab/species URL params must
  // NOT wait on _loadSpecies -- that fetch (234 species) is only needed for the
  // add-species and filter dropdowns. Gating everything on it caused both the
  // "New Encounter tab does nothing" and "My Season stuck on loading" bugs.
  document.addEventListener('DOMContentLoaded', function () {
    // Mount the capture widget into both tabs (identical behaviour; season-tab
    // saves tag encounter_type='season').
    _mountCapture('new');
    _mountCapture('season');
    // URL params handled immediately -- tab switch must not wait for any fetch.
    // Default tab is New Encounter (the observation pipeline); ?tab=season opens My Season.
    var params = new URLSearchParams(location.search);
    var tabParam = params.get('tab');
    var spParam  = params.get('species');
    var uidParam = params.get('user_id');
    if (uidParam) {
      _viewUserId = parseInt(uidParam, 10) || null;
      if (_viewUserId) _initViewMode(_viewUserId);
    }
    if (tabParam === 'season') switchTab('season');
    else if (tabParam === 'new') switchTab('new');
    else if (tabParam === 'reading') switchTab('reading');
    else switchTab('record');
    if (spParam) openCard(parseInt(spParam, 10));
    // Load season + encounter lists independently.
    loadMySeason();
    loadEncounters();
    // Load species dropdowns (add-to-season, filter) asynchronously -- non-blocking.
    _loadSpecies();
    // When queued encounters reach the server, refresh the list so they appear.
    // Debounced so a burst flush of several items triggers a single reload.
    var _syncRefreshT = null;
    window.addEventListener('encounter-queue:synced', function () {
      clearTimeout(_syncRefreshT);
      _syncRefreshT = setTimeout(function () { loadEncounters(); }, 400);
    });
  });

  // -- Tabs ---------------------------------------------------
  window.switchTab = function (tab) {
    document.querySelectorAll('.tab-panel').forEach(function (p) { p.style.display = 'none'; });
    document.getElementById('panel-' + tab).style.display = '';
    document.querySelectorAll('.tab-btn').forEach(function (b) { b.classList.remove('active'); });
    document.getElementById('tab-' + tab).classList.add('active');
    if (tab === 'browse') loadBrowseTab();
  };

  // -- Browse tab: reverse-chron, walk-grouped ----------------
  var _browseLoaded = false;
  var WALK_GAP_MS = 90 * 60 * 1000; // 90 min gap = new walk

  async function loadBrowseTab() {
    var el = document.getElementById('browse-content');
    if (!el) return;
    el.innerHTML = '<div style="color:#888;font-size:0.85rem;padding:12px">Loading...</div>';
    try {
      var r = await fetch('/api/encounters');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      var data = await r.json();
      var encs = (data.encounters || []).filter(function (e) {
        return e.encounter_type === 'field' || e.encounter_type == null;
      });
      _renderBrowse(el, encs);
      _browseLoaded = true;
    } catch (e) {
      el.innerHTML = '<div style="color:#c0392b;font-size:0.85rem;padding:12px">Error: ' + _esc(e.message) + '</div>';
    }
  }

  function _groupByWalk(encs) {
    if (!encs.length) return [];
    var walks = [];
    var current = { encs: [encs[0]], start: encs[0].encounter_date };
    for (var i = 1; i < encs.length; i++) {
      var prev = new Date(encs[i - 1].encounter_date).getTime();
      var cur = new Date(encs[i].encounter_date).getTime();
      if (prev - cur > WALK_GAP_MS) {
        walks.push(current);
        current = { encs: [encs[i]], start: encs[i].encounter_date };
      } else {
        current.encs.push(encs[i]);
      }
    }
    walks.push(current);
    return walks;
  }

  function _fmtWalkDate(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    var mo = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return pad(d.getDate()) + ' ' + mo[d.getMonth()] + ' ' + d.getFullYear() + ', ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }

  function _fmtTime(iso) {
    if (!iso) return '';
    var d = new Date(iso);
    return String(d.getHours()).padStart(2,'0') + ':' + String(d.getMinutes()).padStart(2,'0');
  }

  function _renderBrowse(el, encs) {
    if (!encs.length) {
      el.innerHTML = '<div style="color:#888;font-size:0.85rem;padding:12px">No encounters yet. Record your first one!</div>';
      return;
    }
    var walks = _groupByWalk(encs);
    var html = '';
    walks.forEach(function (walk) {
      var dateLabel = _fmtWalkDate(walk.encs[0].encounter_date);
      var unconfirmed = walk.encs.filter(function (e) {
        var suggs = e.suggestions || [];
        return suggs.some(function (s) { return s.status === 'pending'; }) || (!e.photos.length && e.expected_filename);
      }).length;
      var noteHtml = unconfirmed > 0
        ? '<span class="walk-note">' + unconfirmed + ' encounter' + (unconfirmed !== 1 ? 's' : '') + ' with unconfirmed notes or pending photos</span>'
        : '';

      html += '<div class="walk-group">';
      html += '<div class="walk-header"><span>' + _esc(dateLabel) + ' (' + walk.encs.length + ')</span>' + noteHtml + '</div>';
      walk.encs.forEach(function (enc) { html += _renderEncCard(enc); });
      html += '</div>';
    });
    el.innerHTML = html;
    setTimeout(_setupCandidateLoading, 100);
  }

  function _renderEncCard(enc) {
    var thumbHtml;
    if (enc.photos && enc.photos.length) {
      var p = enc.photos[0];
      thumbHtml = p.thumbnail
        ? '<img class="enc-thumb" src="' + _esc(p.thumbnail) + '" onerror="this.outerHTML=\'<div class=enc-thumb-pending>photo</div>\'">'
        : '<div class="enc-thumb-pending">photo</div>';
    } else if (enc.expected_filename) {
      thumbHtml = '<div class="enc-thumb-pending">photo<br>pending</div>';
    } else {
      thumbHtml = '';
    }

    var speciesHtml = enc.species_name
      ? '<div class="enc-card-species">' + _esc(enc.species_name) + '</div>'
      : '';

    var noteText = enc.transcript || enc.text_note || enc.prompt_response || '';
    var noteHtml = noteText ? '<div class="enc-card-note">' + _esc(noteText) + '</div>' : '';

    var metaParts = [_fmtTime(enc.encounter_date)];
    if (enc.location_name) metaParts.push(enc.location_name);
    if (enc.has_audio) metaParts.push('🎙');
    var metaHtml = '<div class="enc-card-meta">' + _esc(metaParts.join(' · ')) + '</div>';

    // Suggestion chips
    var chipsHtml = '';
    var suggs = (enc.suggestions || []);
    if (suggs.length) {
      chipsHtml = '<div class="enc-chips">';
      suggs.forEach(function (s) {
        var ico = { species: '🌿', phenology: '📅', field_recipe: '🍲', foraging_note: '📝', safety_note: '⚠️', location: '📍' }[s.type] || '*';
        var cls = s.status === 'confirmed' ? 'enc-chip confirmed' : 'enc-chip';
        var label = s.type === 'species' && s.matched_species_name ? s.matched_species_name : (s.value || s.type);
        if (label.length > 30) label = label.substring(0, 28) + '...';
        if (s.status === 'confirmed') {
          chipsHtml += '<span class="' + cls + '">' + ico + ' ' + _esc(label) + '</span>';
        } else {
          chipsHtml += '<span class="' + cls + '" onclick="resolveSuggestion(' + enc.id + ',\'' + _esc(s.id) + '\',\'confirm\')" title="Tap to confirm">' + ico + ' ' + _esc(label) + '</span>';
          chipsHtml += '<span class="enc-chip" onclick="resolveSuggestion(' + enc.id + ',\'' + _esc(s.id) + '\',\'dismiss\')" title="Dismiss" style="color:#c0392b;border-color:#5a3a3a">✕</span>';
        }
      });
      chipsHtml += '</div>';
    }

    // Photo candidates strip (loaded lazily)
    var candidatesHtml = '';
    if (!enc.photos.length && !enc.expected_filename && enc.latitude != null) {
      candidatesHtml = '<div class="photo-candidates" id="cands-' + enc.id + '" data-enc="' + enc.id + '"></div>';
    }

    // Manual photo bind
    var manualHtml = '<div style="margin-top:4px"><label style="font-size:0.72rem;color:#6a8a6a;cursor:pointer">+ add photo <input type="file" accept="image/*" onchange="browseManualBind(' + enc.id + ', this)" style="display:none"></label></div>';

    return '<div class="enc-card" id="enc-card-' + enc.id + '">'
      + '<div class="enc-card-top">' + thumbHtml + '<div class="enc-card-body">'
      + speciesHtml + metaHtml + noteHtml
      + '</div></div>'
      + chipsHtml + candidatesHtml + manualHtml
      + '</div>';
  }

  // Lazy-load proximity candidates for visible encounter cards
  window.addEventListener('encounter-queue:synced', function () {
    if (_browseLoaded) loadBrowseTab();
  });

  window.browseManualBind = async function (encId, input) {
    if (!input.files || !input.files.length) return;
    var file = input.files[0];
    try {
      var fd = new FormData();
      fd.append('file', file);
      fd.append('source', 'both');
      fd.append('upload_source', 'file_upload');
      var headers = { 'ngrok-skip-browser-warning': 'true' };
      var hdr = window.EncounterQueue && EncounterQueue.authHeader();
      if (hdr) headers['Authorization'] = hdr;
      var pr = await fetch('/api/scan', { method: 'POST', body: fd, headers: headers });
      if (!pr.ok) throw new Error('Upload failed');
      var result = await pr.json();
      if (!result.observation_id) throw new Error('No observation created');
      var br = await fetch('/api/encounters/' + encId + '/bind-photo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ observation_id: result.observation_id, binding_method: 'manual' }),
      });
      if (!br.ok) throw new Error('Bind failed');
      loadBrowseTab();
    } catch (e) {
      alert('Could not bind photo: ' + e.message);
    }
  };

  window.browseBindCandidate = async function (encId, obsId) {
    try {
      var r = await fetch('/api/encounters/' + encId + '/bind-photo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ observation_id: obsId, binding_method: 'proximity' }),
      });
      if (!r.ok) throw new Error('Bind failed');
      loadBrowseTab();
    } catch (e) {
      alert('Could not bind: ' + e.message);
    }
  };

  window.browseLoadCandidates = async function (encId, radiusM, windowS) {
    var el = document.getElementById('cands-' + encId);
    if (!el) return;
    try {
      var url = '/api/encounters/' + encId + '/photo-candidates?radius_m=' + (radiusM || 20) + '&window_s=' + (windowS || 300);
      var r = await fetch(url);
      var data = await r.json();
      var cands = data.candidates || [];
      if (!cands.length) {
        el.innerHTML = '<span style="font-size:0.7rem;color:#666">No nearby photos</span>';
        return;
      }
      var html = cands.map(function (c) {
        var label = c.distance_m + 'm · ' + _fmtTime(c.photo_taken_at);
        var img = c.thumbnail ? '<img src="' + _esc(c.thumbnail) + '" onerror="this.style.display=\'none\'">' : '';
        return '<div class="photo-cand" onclick="browseBindCandidate(' + encId + ',' + c.observation_id + ')" title="Tap to bind">'
          + img + '<div class="photo-cand-label">' + _esc(label) + '</div></div>';
      }).join('');
      html += '<span class="enc-chip" onclick="browseLoadCandidates(' + encId + ',' + (radiusM || 20) * 2 + ',' + (windowS || 300) * 2 + ')" title="Widen search" style="align-self:center">⟷ widen</span>';
      el.innerHTML = html;
    } catch (e) {
      el.innerHTML = '<span style="font-size:0.7rem;color:#c0392b">Error loading candidates</span>';
    }
  };

  // Auto-load proximity candidates for visible cards after browse renders
  var _candObserver = null;
  function _setupCandidateLoading() {
    if (_candObserver) _candObserver.disconnect();
    _candObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          var encId = entry.target.dataset.enc;
          if (encId) { browseLoadCandidates(parseInt(encId)); _candObserver.unobserve(entry.target); }
        }
      });
    }, { threshold: 0.1 });
    document.querySelectorAll('.photo-candidates[data-enc]').forEach(function (el) { _candObserver.observe(el); });
  }

  // -- Record tab: minimal capture ----------------------------
  var _recRecorder = null, _recStream = null, _recChunks = [], _recBlob = null;
  var _recStartMs = 0, _recTimerInterval = null;
  var _recLat = null, _recLng = null;
  var _recPhotoFile = null, _recPhotoFilename = null;
  var _recIsOnline = function () { return navigator.onLine !== false; };

  window.recToggle = function () {
    if (_recRecorder && _recRecorder.state === 'recording') { _recStop(); return; }
    _recStart();
  };

  async function _recStart() {
    var btn = document.getElementById('rec-btn');
    var status = document.getElementById('rec-status');
    var timer = document.getElementById('rec-timer');
    var wave = document.getElementById('rec-wave');
    try {
      _recStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      _recChunks = [];
      _recRecorder = new MediaRecorder(_recStream);
      _recRecorder.ondataavailable = function (e) { if (e.data.size) _recChunks.push(e.data); };
      _recRecorder.onstop = function () {
        _recBlob = new Blob(_recChunks, { type: 'audio/webm' });
        if (status) status.textContent = 'Recording ready';
        if (btn) { btn.textContent = '🎙'; btn.style.background = '#2d5a1b'; }
        if (wave) wave.style.display = 'none';
        clearInterval(_recTimerInterval);
      };
      _recRecorder.start();
      _recStartMs = Date.now();
      if (btn) { btn.textContent = '⏹'; btn.style.background = '#c0392b'; }
      if (status) status.textContent = 'Recording...';
      if (wave) wave.style.display = '';
      _recTimerInterval = setInterval(function () {
        var s = Math.round((Date.now() - _recStartMs) / 1000);
        if (timer) timer.textContent = Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
      }, 500);
      // GPS fix in background
      _recLat = null; _recLng = null;
      if (window.GPS && GPS.getOnce) {
        GPS.getOnce({ maxAge: 0, timeout: 8000 }).then(function (p) {
          _recLat = p.lat; _recLng = p.lng;
        }).catch(function () {});
      }
    } catch (e) {
      if (status) status.textContent = 'Mic unavailable';
    }
  }

  function _recStop() {
    if (_recRecorder && _recRecorder.state === 'recording') _recRecorder.stop();
    if (_recStream) { _recStream.getTracks().forEach(function (t) { t.stop(); }); _recStream = null; }
  }

  window.recPhotoSelected = function (input) {
    if (!input.files || !input.files.length) return;
    _recPhotoFile = input.files[0];
    _recPhotoFilename = _recPhotoFile.name;
    var nameEl = document.getElementById('rec-photo-name');
    var clearEl = document.getElementById('rec-photo-clear');
    if (nameEl) nameEl.textContent = _recPhotoFilename;
    if (clearEl) clearEl.style.display = '';
  };

  window.recPhotoClear = function () {
    _recPhotoFile = null; _recPhotoFilename = null;
    var input = document.getElementById('rec-photo-input');
    if (input) input.value = '';
    var nameEl = document.getElementById('rec-photo-name');
    var clearEl = document.getElementById('rec-photo-clear');
    if (nameEl) nameEl.textContent = '';
    if (clearEl) clearEl.style.display = 'none';
  };

  window.recSave = async function () {
    var btn = document.getElementById('rec-save-btn');
    var msg = document.getElementById('rec-msg');
    var saved = document.getElementById('rec-saved');
    var note = document.getElementById('rec-note');
    var textNote = note ? note.value.trim() : '';

    if (!_recBlob && !textNote && !_recPhotoFilename) {
      if (msg) { msg.textContent = 'Record audio, pick a photo, or write a note first.'; msg.style.color = '#c0392b'; }
      return;
    }

    if (btn) { btn.disabled = true; btn.textContent = 'Saving...'; }
    if (msg) msg.textContent = '';

    var encDate = new Date().toISOString().replace('Z', '+00:00');
    var uuid = EncounterQueue.newUUID();

    // -- Online + photo: upload photo via P2, bind immediately --
    var photoObsIds = null;
    if (_recPhotoFile && _recIsOnline()) {
      try {
        var renamedName = 'encounter_' + uuid.replace(/-/g, '') + (_recPhotoFilename.match(/\.[^.]+$/) || ['.jpg'])[0];
        var renamedFile = new File([_recPhotoFile], renamedName, { type: _recPhotoFile.type });
        var fd = new FormData();
        fd.append('file', renamedFile);
        fd.append('source', 'both');
        fd.append('upload_source', 'file_upload');
        var headers = { 'ngrok-skip-browser-warning': 'true' };
        var hdr = window.EncounterQueue && EncounterQueue.authHeader();
        if (hdr) headers['Authorization'] = hdr;
        var pr = await fetch('/api/scan', { method: 'POST', body: fd, headers: headers });
        if (pr.ok) {
          var pResult = await pr.json();
          if (pResult.observation_id) {
            photoObsIds = JSON.stringify([{ observation_id: pResult.observation_id, binding_method: 'own_named', binding_detail: renamedName }]);
          }
        }
      } catch (e) {
        // Photo upload failed -- degrade to offline filename path
      }
    }

    // Determine expected_filename: online=renamed, offline=original gallery name
    var expectedFn = null;
    if (photoObsIds) {
      expectedFn = 'encounter_' + uuid.replace(/-/g, '') + (_recPhotoFilename.match(/\.[^.]+$/) || ['.jpg'])[0];
    } else if (_recPhotoFilename) {
      expectedFn = _recPhotoFilename;
    }

    // -- Audio present -> direct send (no blob in queue) --
    if (_recBlob) {
      try {
        var fd2 = new FormData();
        fd2.append('encounter_date', encDate);
        fd2.append('encounter_type', 'field');
        fd2.append('client_uuid', uuid);
        if (_recLat != null) fd2.append('latitude', _recLat);
        if (_recLng != null) fd2.append('longitude', _recLng);
        if (textNote) fd2.append('text_note', textNote);
        if (expectedFn) fd2.append('expected_filename', expectedFn);
        if (photoObsIds) fd2.append('photo_observation_ids', photoObsIds);
        fd2.append('audio', _recBlob, 'recording.webm');
        var headers2 = { 'ngrok-skip-browser-warning': 'true' };
        var hdr2 = window.EncounterQueue && EncounterQueue.authHeader();
        if (hdr2) headers2['Authorization'] = hdr2;
        var resp = await fetch('/api/encounters', { method: 'POST', body: fd2, headers: headers2 });
        if (!resp.ok) { var err = await resp.json().catch(function () { return {}; }); throw new Error(err.detail || resp.status); }
        _recReset();
        _recShowSaved('Recording saved');
      } catch (e) {
        if (msg) { msg.textContent = 'Error: ' + e.message; msg.style.color = '#c0392b'; }
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Save'; }
      }
      return;
    }

    // -- No audio -> durable outbox (JSON only, no binary) --
    try {
      var payload = {
        client_uuid: uuid,
        encounter_date: encDate,
        encounter_type: 'field',
      };
      if (_recLat != null) payload.latitude = _recLat;
      if (_recLng != null) payload.longitude = _recLng;
      if (textNote) payload.text_note = textNote;
      if (expectedFn) payload.expected_filename = expectedFn;
      if (photoObsIds) payload.photo_observation_ids = photoObsIds;

      var haveFix = (_recLat != null && _recLng != null);
      await EncounterQueue.enqueue(payload, { awaitLocation: !haveFix });
      _recReset();
      _recShowSaved('Saved');

      if (!haveFix && window.GPS && GPS.getOnce) {
        GPS.getOnce({ maxAge: 0, timeout: 8000 }).then(function (p) {
          EncounterQueue.attachLocation(uuid, { latitude: p.lat, longitude: p.lng });
        }).catch(function () {});
      }
    } catch (e) {
      if (msg) { msg.textContent = 'Could not save: ' + e.message; msg.style.color = '#c0392b'; }
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = 'Save'; }
    }
  };

  function _recReset() {
    _recBlob = null; _recChunks = [];
    _recPhotoFile = null; _recPhotoFilename = null;
    var input = document.getElementById('rec-photo-input');
    if (input) input.value = '';
    var nameEl = document.getElementById('rec-photo-name');
    var clearEl = document.getElementById('rec-photo-clear');
    if (nameEl) nameEl.textContent = '';
    if (clearEl) clearEl.style.display = 'none';
    var note = document.getElementById('rec-note');
    if (note) note.value = '';
    var status = document.getElementById('rec-status');
    var timer = document.getElementById('rec-timer');
    if (status) status.textContent = 'Tap to record';
    if (timer) timer.textContent = '';
    var btn = document.getElementById('rec-btn');
    if (btn) { btn.textContent = '🎙'; btn.style.background = '#c0392b'; }
  }

  function _recShowSaved(label) {
    var el = document.getElementById('rec-saved');
    if (!el) return;
    var now = new Date();
    var pad = function (n) { return String(n).padStart(2, '0'); };
    var stamp = pad(now.getDate()) + '/' + pad(now.getMonth() + 1) + ' ' + pad(now.getHours()) + ':' + pad(now.getMinutes());
    var parts = [label, stamp];
    if (_recLat != null) parts.push('📍');
    el.textContent = parts.join(' · ');
    el.style.display = '';
    setTimeout(function () { el.style.display = 'none'; }, 5000);
  }

  // -- Species dropdowns (capture, add-to-season, filter) -----
  async function _loadSpecies() {
    try {
      var data = await (await fetch('/api/species/')).json();
      var list = Array.isArray(data) ? data : (data.species || []);
      _species = list.filter(function (sp) { return sp.id != null; });
    } catch (e) { _species = []; }

    var _populate = function (selId, placeholder) {
      var sel = document.getElementById(selId);
      if (!sel) return;
      sel.innerHTML = '<option value="">' + placeholder + '</option>';
      _species.forEach(function (sp) {
        var label = sp.scientific_name;
        if (sp.common_names && sp.common_names.length) label += ' (' + sp.common_names[0] + ')';
        var o = document.createElement('option'); o.value = sp.id; o.textContent = label;
        sel.appendChild(o);
      });
    };
    // Only the My Season add-species dropdown remains; the old capture/filter
    // selects were removed with the Foraging Notes filter section. _populate
    // always sets a placeholder option, so an empty species list never hangs.
    _populate('add-species-select', '-- choose a species --');
  }

  // -- Capture widget (context-aware: one per tab) ------------
  // The New Encounter tab (ctx='new') and the My Season tab (ctx='season')
  // mount an identical capture widget. Element IDs are suffixed by ctx; the
  // single set of module-level recorder globals is fine because only one
  // recording is ever active at a time. Season-tab saves tag encounter_type='season'.
  var _activeCtx = null, _recStartMs = 0, _recDurationSec = null;

  function _cap(ctx, base) { return document.getElementById(base + '-' + ctx); }
  function _capShow(ctx, base) { var el = _cap(ctx, base); if (el) el.style.display = ''; }
  function _capHide(ctx, base) { var el = _cap(ctx, base); if (el) el.style.display = 'none'; }

  function _buildCaptureHTML(ctx) {
    return ''
      + '<div class="rec-primary-row">'
      +   '<button class="btn-rec-big start" id="btn-rec-start-' + ctx + '" onclick="startRecording(\'' + ctx + '\')" title="Tap to start recording">🎙</button>'
      +   '<button class="btn-rec-big stop"  id="btn-rec-stop-' + ctx + '"  onclick="stopRecording(\'' + ctx + '\')"  title="Tap to stop" style="display:none">⏹</button>'
      +   '<span class="rec-hint" id="rec-hint-' + ctx + '">Tap to record a voice note</span>'
      +   '<span class="rec-status" id="rec-status-' + ctx + '" style="display:none"><span class="rec-dot"></span> Recording...</span>'
      +   '<div class="rec-saved" id="rec-saved-' + ctx + '" style="display:none"></div>'
      + '</div>'
      + '<div class="wakelock-row">'
      +   '<input type="checkbox" id="wakelock-toggle-' + ctx + '" checked>'
      +   '<label for="wakelock-toggle-' + ctx + '">Keep screen on while recording</label>'
      + '</div>'
      + '<canvas id="waveform-' + ctx + '" width="640" height="84" style="display:none"></canvas>'
      + '<audio id="audio-preview-' + ctx + '" style="display:none" controls></audio>'
      + '<div class="audio-row" id="post-rec-row-' + ctx + '" style="display:none">'
      +   '<button class="btn-rec btn-rec-play" id="btn-rec-play-' + ctx + '" onclick="playRecording(\'' + ctx + '\')">▶ Play back</button>'
      +   '<button class="btn-rec-discard" id="btn-rec-discard-' + ctx + '" onclick="discardAudio(\'' + ctx + '\')">Discard</button>'
      + '</div>'
      + '<div class="secondary-audio">'
      +   '<span class="secondary-label">or upload an existing file</span>'
      +   '<button type="button" class="btn-upload" id="btn-upload-' + ctx + '" onclick="document.getElementById(\'audio-file-' + ctx + '\').click()">📁 Upload audio file</button>'
      +   '<input type="file" id="audio-file-' + ctx + '" accept=".mp3,.m4a,.wav,.ogg,audio/mpeg,audio/mp4,audio/x-m4a,audio/wav,audio/ogg" onchange="handleAudioUpload(event,\'' + ctx + '\')">'
      +   '<div class="upload-name" id="upload-name-' + ctx + '"></div>'
      + '</div>'
      + '<div class="field-row stage1-row" style="margin-top:18px">'
      +   '<label>Stage 1 · Exact seeing</label>'
      +   '<textarea id="prompt-response-' + ctx + '" placeholder="What do you actually see?"></textarea>'
      +   '<div class="stage1-hint">Colour, form, number, texture -- only what\'s in front of you. No naming yet.</div>'
      + '</div>'
      + '<div class="field-row" style="margin-top:10px">'
      +   '<label style="color:#666">Optional note</label>'
      +   '<textarea id="text-note-' + ctx + '" placeholder="Smell, texture, habitat context..." style="min-height:54px"></textarea>'
      + '</div>'
      + '<button class="btn-save" id="btn-save-' + ctx + '" onclick="saveEncounter(\'' + ctx + '\')">Save encounter</button>'
      + '<div class="save-msg" id="save-msg-' + ctx + '"></div>';
  }

  function _mountCapture(ctx) {
    var mount = document.getElementById('cap-mount-' + ctx);
    if (mount) mount.innerHTML = _buildCaptureHTML(ctx);
  }

  function _fmtDateTime(d) {
    var mo = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var pad = function (n) { return String(n).padStart(2, '0'); };
    return pad(d.getDate()) + ' ' + mo[d.getMonth()] + ' ' + d.getFullYear() +
           ', ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
  }
  function _fmtDur(sec) {
    var m = Math.floor(sec / 60), s = sec % 60;
    return m + ':' + String(s).padStart(2, '0');
  }

  // -- Audio recorder -----------------------------------------
  window.startRecording = async function (ctx) {
    _activeCtx = ctx;
    // Silent GPS auto-capture -- fire in the background, store on save. Never
    // blocks recording and never surfaces an error if location is unavailable.
    _lat = null; _lng = null;
    if (window.GPS && GPS.getOnce) {
      // Fresh fix (maxAge:0) so successive recordings while walking never share one.
      GPS.getOnce({ maxAge: 0, timeout: 8000 }).then(function (p) { _lat = p.lat; _lng = p.lng; }).catch(function () {});
    }
    try {
      _stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      _chunks = []; _audioBlob = null; _audioName = null;
      _recorder = new MediaRecorder(_stream);
      _recorder.ondataavailable = function (e) { if (e.data.size) _chunks.push(e.data); };
      _recorder.onstop = function () {
        _audioBlob = new Blob(_chunks, { type: 'audio/webm' });
        _audioName = 'recording.webm';
        _recDurationSec = Math.max(0, Math.round((Date.now() - _recStartMs) / 1000));
        var url = URL.createObjectURL(_audioBlob);
        var preview = _cap(ctx, 'audio-preview');
        preview.src = url; preview.style.display = '';
        _capShow(ctx, 'post-rec-row');
        var hint = _cap(ctx, 'rec-hint');
        if (hint) { hint.textContent = 'Recording ready'; hint.className = 'rec-hint'; }
      };
      _recorder.start();
      _recStartMs = Date.now();
      _startVisualiser(ctx, _stream);
      _requestWakeLock(ctx);
      _capHide(ctx, 'btn-rec-start'); _capHide(ctx, 'post-rec-row'); _capHide(ctx, 'rec-saved');
      _capShow(ctx, 'btn-rec-stop'); _capShow(ctx, 'rec-status');
      _clearUploadName(ctx);
      _cap(ctx, 'audio-preview').style.display = 'none';
      var hint = _cap(ctx, 'rec-hint');
      if (hint) { hint.textContent = 'Recording...'; hint.className = 'rec-hint recording'; }
    } catch (e) { alert('Microphone access denied or unavailable.'); }
  };

  window.stopRecording = function (ctx) {
    if (_recorder && _recorder.state !== 'inactive') {
      _recorder.stop();
      _recorder.stream.getTracks().forEach(function (t) { t.stop(); });
    }
    _stopVisualiser(ctx); _releaseWakeLock();
    _capHide(ctx, 'btn-rec-stop'); _capHide(ctx, 'rec-status');
    _capShow(ctx, 'btn-rec-start');
  };

  // -- Dandelion-leaf waveform visualiser ---------------------
  function _startVisualiser(ctx, stream) {
    var canvas = _cap(ctx, 'waveform');
    canvas.style.display = '';
    try {
      _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      var src = _audioCtx.createMediaStreamSource(stream);
      _analyser = _audioCtx.createAnalyser();
      _analyser.fftSize = 1024;
      src.connect(_analyser);
      _drawDandelion(ctx);
    } catch (e) { canvas.style.display = 'none'; }
  }

  function _stopVisualiser(ctx) {
    if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
    if (_audioCtx) { _audioCtx.close().catch(function () {}); _audioCtx = null; }
    _analyser = null;
    var canvas = _cap(ctx, 'waveform');
    if (canvas) { canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height); canvas.style.display = 'none'; }
  }

  function _drawDandelion(ctx0) {
    var canvas = _cap(ctx0, 'waveform');
    var ctx = canvas.getContext('2d');
    var W = canvas.width, H = canvas.height;
    var buf = new Uint8Array(_analyser.fftSize);
    var LOBES = 9, phase = 0;
    // Deterministic per-index pseudo-random -> a stable, irregular silhouette
    // (only the amplitude/wobble animates; the jagged geometry never flickers).
    function rnd(n) { var s = Math.sin(n * 12.9898 + 78.233) * 43758.5453; return s - Math.floor(s); }
    function frame() {
      _rafId = requestAnimationFrame(frame);
      _analyser.getByteTimeDomainData(buf);
      var sum = 0;
      for (var i = 0; i < buf.length; i++) { var v = (buf[i] - 128) / 128; sum += v * v; }
      var drive = Math.min(1, Math.sqrt(sum / buf.length) * 4);
      phase += 0.05;
      ctx.clearRect(0, 0, W, H);
      var midY = H / 2, baseX = 14, tipX = W - 12, span = tipX - baseX;
      var maxTooth = (H / 2) - 5, step = span / LOBES;

      // Runcinate ("lion's tooth") dandelion outline: narrow at the petiole,
      // backward-pointing triangular lobes that enlarge toward the apex, with
      // deep irregular sinuses cut almost to the midrib. Top and bottom use
      // different seeds so the leaf is asymmetric, as in the botanical plate.
      // drive still scales serration length -- the amplitude mapping is unchanged.
      var lobe = function (t, seed) {
        var jit   = (rnd(t * 1.7 + seed) - 0.5) * step * 0.40;
        var x     = baseX + (t / LOBES) * span + jit;
        var grow  = 0.30 + 0.70 * (t / LOBES);              // lobes enlarge toward the apex
        var irr   = 0.35 + 0.65 * rnd(t * 3.3 + seed);      // per-lobe depth variance
        var env   = grow * irr;
        var lean  = step * (0.24 + 0.36 * rnd(t * 5.1 + seed)); // backward lean of the tip
        var sinus = 1.5 + rnd(t * 2.2 + seed) * 4.5;        // sinus depth (cut toward midrib)
        var wob   = 0.60 + 0.40 * Math.sin(phase + t * 0.9 + seed);
        // Bold resting silhouette (0.55) so the lobed leaf always reads; audio adds
        // up to 0.45 more -- the serrations still animate with level (unchanged mapping).
        var amp   = env * (0.55 + 0.45 * drive * wob);
        return { x: x, len: 6 + amp * maxTooth, lean: lean, sinus: sinus };
      };

      ctx.beginPath();
      ctx.moveTo(baseX, midY);
      // Top edge: petiole -> apex
      for (var t = 1; t <= LOBES; t++) {
        var u = lobe(t, 0);
        ctx.lineTo(u.x - step * 0.55, midY - u.sinus);     // deep sinus
        ctx.lineTo(u.x - u.lean,      midY - u.len);        // lobe apex, leaning back
        ctx.lineTo(u.x,               midY - u.sinus * 0.5);
      }
      ctx.lineTo(tipX, midY);                               // pointed terminal lobe
      // Bottom edge: apex -> petiole (reverse order, different seed -> asymmetric)
      for (var b = LOBES; b >= 1; b--) {
        var d = lobe(b, 50);
        ctx.lineTo(d.x,               midY + d.sinus * 0.5);
        ctx.lineTo(d.x - d.lean,      midY + d.len);
        ctx.lineTo(d.x - step * 0.55, midY + d.sinus);
      }
      ctx.closePath();

      var green = 120 + Math.round(drive * 90);
      ctx.fillStyle = 'rgba(58,' + green + ',42,0.5)';
      ctx.strokeStyle = 'rgba(150,215,125,0.9)'; ctx.lineWidth = 1.3;
      ctx.fill(); ctx.stroke();

      // Pronounced central midrib -- the calm baseline, with a short petiole tail.
      ctx.beginPath();
      ctx.moveTo(baseX - 4, midY); ctx.lineTo(tipX, midY);
      ctx.strokeStyle = 'rgba(205,238,175,0.9)'; ctx.lineWidth = 2.6; ctx.stroke();
    }
    frame();
  }

  // -- Wake Lock ----------------------------------------------
  function _requestWakeLock(ctx) {
    var toggle = _cap(ctx || _activeCtx, 'wakelock-toggle');
    if (!toggle || !toggle.checked || !('wakeLock' in navigator)) return;
    navigator.wakeLock.request('screen').then(function (lock) {
      _wakeLock = lock;
      _wakeLock.addEventListener('release', function () { _wakeLock = null; });
    }).catch(function () {});
  }
  function _releaseWakeLock() {
    if (_wakeLock) { _wakeLock.release().catch(function () {}); _wakeLock = null; }
  }
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'visible' && _recorder && _recorder.state === 'recording') _requestWakeLock(_activeCtx);
  });
  window.addEventListener('pagehide', _releaseWakeLock);

  // -- Upload fallback ----------------------------------------
  window.handleAudioUpload = function (ev, ctx) {
    var file = ev.target.files && ev.target.files[0];
    if (!file) return;
    _activeCtx = ctx;
    _audioBlob = file; _audioName = file.name;
    _recDurationSec = null;  // uploaded file -- no recording duration
    var preview = _cap(ctx, 'audio-preview');
    preview.src = URL.createObjectURL(file); preview.style.display = '';
    _capShow(ctx, 'post-rec-row'); _capHide(ctx, 'rec-saved');
    _cap(ctx, 'upload-name').textContent = 'Selected: ' + file.name;
    var hint = _cap(ctx, 'rec-hint');
    if (hint) { hint.textContent = 'File ready'; hint.className = 'rec-hint'; }
  };
  function _clearUploadName(ctx) {
    var el = _cap(ctx, 'upload-name'); if (el) el.textContent = '';
    var fi = _cap(ctx, 'audio-file'); if (fi) fi.value = '';
  }
  window.playRecording = function (ctx) {
    var preview = _cap(ctx, 'audio-preview');
    preview.style.display = ''; preview.play();
  };
  window.discardAudio = function (ctx) {
    _audioBlob = null; _audioName = null; _chunks = []; _recDurationSec = null;
    _capHide(ctx, 'post-rec-row');
    var preview = _cap(ctx, 'audio-preview');
    if (preview) { preview.style.display = 'none'; preview.src = ''; }
    _clearUploadName(ctx); _capShow(ctx, 'btn-rec-start');
    var hint = _cap(ctx, 'rec-hint');
    if (hint) { hint.textContent = 'Tap to record a voice note'; hint.className = 'rec-hint'; }
  };

  // -- Save encounter -----------------------------------------
  // Text / location / prompt captures go through the durable outbox
  // (EncounterQueue, Phase 13.10b): write locally first, confirm immediately,
  // sync when signal allows -- so no encounter is lost to flaky cellular.
  // Audio captures keep the direct online send path: Blob queueing is out of
  // scope this phase. Both paths attach the participant token the same way.
  window.saveEncounter = async function (ctx) {
    var btn = _cap(ctx, 'btn-save');
    btn.disabled = true; btn.textContent = 'Saving...'; _msg(ctx, '', '');
    var hadAudio = !!_audioBlob, dur = _recDurationSec;
    // species_id is optional -- species linking happens in the laptop/archive view
    var textNote = _cap(ctx, 'text-note').value.trim();
    var promptResp = _cap(ctx, 'prompt-response').value.trim();
    if (!_audioBlob && !textNote && !promptResp) {
      _msg(ctx, 'Add a voice note or write something first.', 'err');
      btn.disabled = false; btn.textContent = 'Save encounter';
      return;
    }
    // ISO 8601 with explicit +00:00 offset. The backend parses with Python 3.9's
    // datetime.fromisoformat(), which rejects the bare 'Z' that toISOString() emits.
    var encDate = new Date().toISOString().replace('Z', '+00:00');
    // Season-tab captures are tagged 'season'; New Encounter captures 'field'.
    var encType = ctx === 'season' ? 'season' : 'field';

    // -- Audio present -> direct send (no Blob queueing this phase) --
    if (_audioBlob) {
      try {
        var fd = new FormData();
        fd.append('encounter_date', encDate);
        if (_lat != null) fd.append('latitude', _lat);
        if (_lng != null) fd.append('longitude', _lng);
        if (textNote) fd.append('text_note', textNote);
        if (promptResp) fd.append('prompt_response', promptResp);
        fd.append('encounter_type', encType);
        fd.append('audio', _audioBlob, _audioName || 'recording.webm');
        var headers = { 'ngrok-skip-browser-warning': 'true' };
        var hdr = window.EncounterQueue && EncounterQueue.authHeader();
        if (hdr) headers['Authorization'] = hdr;
        var resp = await fetch('/api/encounters', { method: 'POST', body: fd, headers: headers });
        if (!resp.ok) { var err = await resp.json().catch(function () { return {}; }); throw new Error(err.detail || resp.status); }
        _resetForm(ctx);
        _recSaved(ctx, hadAudio, dur);
        loadEncounters();
      } catch (e) {
        _msg(ctx, 'Error: ' + e.message, 'err');
      } finally {
        btn.disabled = false; btn.textContent = 'Save encounter';
      }
      return;
    }

    // -- Text / location / prompt -> durable outbox --
    try {
      var uuid = EncounterQueue.newUUID();      // idempotency key, before any network
      var payload = {
        client_uuid: uuid,
        encounter_date: encDate,
        encounter_type: encType,
      };
      // Use an explicit recent fix if the recorder already captured one this session.
      if (_lat != null) payload.latitude = _lat;
      if (_lng != null) payload.longitude = _lng;
      if (textNote) payload.text_note = textNote;
      if (promptResp) payload.prompt_response = promptResp;
      var haveFix = (_lat != null && _lng != null);

      // Durable write first; the outbox briefly holds a coord-less record for a fresh
      // fix (awaitLocation) so the encounter lands located rather than pending.
      await EncounterQueue.enqueue(payload, { awaitLocation: !haveFix });
      // Confirmation is immediate and independent of sync state.
      _resetForm(ctx);
      _recSaved(ctx, hadAudio, dur);

      // Location status, updated in place (the save never waits on GPS).
      var savedEl = _cap(ctx, 'rec-saved');
      var locNonce = String(Date.now()) + ':' + Math.random();
      if (savedEl) savedEl.dataset.locNonce = locNonce;
      var _setLoc = function (suffix) {
        if (savedEl && savedEl.dataset.locNonce === locNonce) {
          savedEl.textContent = savedEl.textContent.replace(/ · 📍.*$/, '') + ' · 📍 ' + suffix;
        }
      };
      if (haveFix) {
        _setLoc('located');
      } else if (window.GPS && GPS.getOnce) {
        _setLoc('locating...');
        GPS.getOnce({ maxAge: 0, timeout: 8000 }).then(function (p) {
          EncounterQueue.attachLocation(uuid, { latitude: p.lat, longitude: p.lng });
          _setLoc('±' + Math.round(p.accuracy || 0) + 'm');
        }).catch(function () {
          _setLoc('location pending -- pin on map later');
        });
      } else {
        _setLoc('location pending');
      }
    } catch (e) {
      _msg(ctx, 'Could not save locally: ' + e.message, 'err');
    } finally {
      btn.disabled = false; btn.textContent = 'Save encounter';
    }
  };

  // Inline "Recording saved" confirmation beneath the record button.
  function _recSaved(ctx, hadAudio, durationSec) {
    var el = _cap(ctx, 'rec-saved'); if (!el) return;
    var stamp = _fmtDateTime(new Date());
    var txt = (hadAudio ? 'Recording saved · ' : 'Note saved · ') + stamp;
    if (hadAudio && durationSec != null) txt += ' · ' + _fmtDur(durationSec);
    el.textContent = txt; el.style.display = '';
  }

  function _resetForm(ctx) {
    var t = _cap(ctx, 'text-note'); if (t) t.value = '';
    var p = _cap(ctx, 'prompt-response'); if (p) p.value = '';
    _lat = null; _lng = null;
    discardAudio(ctx);
  }

  function _msg(ctx, text, type) {
    var el = _cap(ctx, 'save-msg');
    if (el) { el.textContent = text; el.className = 'save-msg ' + type; }
  }

  function _setDefaultDate() {
    var now = new Date(), pad = function (n) { return String(n).padStart(2, '0'); };
    var el = document.getElementById('enc-date');
    if (el) el.value = now.getFullYear() + '-' + pad(now.getMonth() + 1) + '-' + pad(now.getDate()) +
      'T' + pad(now.getHours()) + ':' + pad(now.getMinutes());
  }

  // -- Encounter card rendering (full -- transcript/suggestions) -
  var _SUGG_META = {
    species:       { ico: '🌿', kind: 'Species -- link to card' },
    phenology:     { ico: '📅', kind: 'Phenological stage' },
    field_recipe:  { ico: '🍲', kind: 'Field recipe' },
    foraging_note: { ico: '📝', kind: 'Foraging note' },
    safety_note:   { ico: '⚠️', kind: 'Safety note' },
    recipe:        { ico: '🍽', kind: 'Recipe / edibility note' },  // legacy data
    location:      { ico: '📍', kind: 'Location' }
  };

  // Cache the most recent encounter objects by id so save/edit handlers can
  // read a suggestion's structured payload without re-fetching.
  var _encById = {};

  function _renderCard(enc) {
    _encById[enc.id] = enc;
    var date = enc.encounter_date ? new Date(enc.encounter_date).toLocaleString() : '--';
    var parts = [date];
    if (enc.location_name) parts.push(enc.location_name);
    else if (enc.latitude != null) parts.push(enc.latitude.toFixed(4) + ', ' + enc.longitude.toFixed(4));

    var audioHtml = enc.audio_url
      ? '<div class="enc-audio"><audio src="' + _esc(enc.audio_url) + '" controls preload="none"></audio></div>'
      : '';
    var noteHtml = enc.text_note ? '<div class="enc-note">' + _esc(enc.text_note) + '</div>' : '';
    var promptHtml = enc.prompt_response
      ? '<div class="enc-prompt"><span class="enc-prompt-tag">Stage 1 · what do you actually see?</span>' +
        _esc(enc.prompt_response) + '</div>'
      : '';

    // Transcript -- visible on both laptop and phone (no data-guest-hide)
    var transcriptHtml = enc.transcript
      ? '<div class="enc-transcript" id="trx-' + enc.id + '"><span class="tlabel">Transcript</span>' +
        _esc(enc.transcript) + '</div>'
      : '';

    // Tool buttons -- laptop/admin only (data-guest-hide)
    var toolsHtml = '';
    if (enc.has_audio) {
      toolsHtml += '<button class="btn-tool" onclick="transcribeEncounter(' + enc.id + ', this)">' +
        (enc.transcript ? '🔁 Re-transcribe' : '📝 Transcribe') + '</button>';
    }
    if (enc.transcript) {
      toolsHtml += '<button class="btn-tool extract" onclick="extractEncounter(' + enc.id + ', this)">' +
        ((enc.suggestions && enc.suggestions.length) ? '🔁 Re-tag' : '🏷 Tag') + '</button>';
    }
    var toolsBlock = (enc.has_audio || enc.transcript)
      ? '<div class="enc-tools" data-guest-hide>' + toolsHtml +
        '</div><div class="tool-msg" id="toolmsg-' + enc.id + '"></div>'
      : '';

    return '<div class="enc-card">' +
      '<div class="enc-icon">🌿</div>' +
      '<div class="enc-body">' +
        '<div class="enc-species">' + _esc(enc.species_name || '--') + '</div>' +
        '<div class="enc-meta">' + parts.map(_esc).join(' · ') + '</div>' +
        promptHtml + noteHtml + audioHtml + transcriptHtml + toolsBlock +
        _renderSuggestions(enc) +
        _renderFieldRecipeBlock(enc) +
      '</div>' +
      '<div class="enc-actions">' +
        '<button class="btn-del" data-guest-hide onclick="deleteEncounter(' + enc.id + ')">✕</button>' +
      '</div>' +
    '</div>';
  }

  function _renderSuggestions(enc) {
    var sugg = enc.suggestions || [];
    if (!sugg.length) return '';
    var rows = sugg.map(function (s) {
      // Field recipe suggestions carry a structured payload (title/body/ingredients)
      // rather than a plain value -- render a dedicated save-card.
      if (s.type === 'field_recipe') return _renderRecipeSuggestion(enc, s);
      // Confirmed non-recipe suggestions are resolved -- remove from the action panel.
      // Dismissed suggestions are already removed server-side (never reach here).
      if (s.status === 'confirmed') return '';
      var meta = _SUGG_META[s.type] || { ico: '*', kind: s.type };
      var matchHtml = '';
      if (s.type === 'species' && s.matched_species_name) {
        matchHtml = '<div class="sugg-match">✓ <a href="/species?s=' +
          encodeURIComponent(s.matched_species_name) +
          '" target="_blank" rel="noopener" style="color:#7ec850;text-decoration:none">' +
          'view card: ' + _esc(s.matched_species_name) + ' ↗</a>' +
          '<span style="font-size:0.66rem;color:#888;margin-left:6px">(confirm links this encounter)</span></div>';
      } else if (s.type === 'species') {
        matchHtml = '<div class="sugg-quote">No matching species card -- confirm to note the mention</div>';
      }
      var quoteHtml = s.quote ? '<div class="sugg-quote">"' + _esc(s.quote) + '"</div>' : '';
      var acts = '<div class="sugg-acts" data-guest-hide>' +
          '<button class="btn-sugg ok" onclick="resolveSuggestion(' + enc.id + ',\'' + _esc(s.id) + '\',\'confirm\')">✓</button>' +
          '<button class="btn-sugg no" onclick="resolveSuggestion(' + enc.id + ',\'' + _esc(s.id) + '\',\'dismiss\')">✕</button>' +
        '</div>';
      return '<div class="sugg-item">' +
        '<div class="sugg-ico">' + meta.ico + '</div>' +
        '<div class="sugg-body">' +
          '<div class="sugg-kind">' + _esc(meta.kind) + '</div>' +
          '<div class="sugg-val">' + _esc(s.value) + '</div>' +
          matchHtml + quoteHtml +
        '</div>' + acts +
      '</div>';
    }).join('');
    // Hide the panel entirely when no actionable suggestions remain.
    // field_recipe confirmed cards return empty string from _renderRecipeSuggestion
    // only when status is not confirmed -- so a mix is fine; trim() catches all-empty.
    if (!rows.replace(/\s/g, '')) return '';
    return '<div class="sugg-list">' + rows + '</div>';
  }

  // -- Field recipes (Phase 12) -------------------------------
  // Shared ingredient-chip renderer. Matched ingredients link to their species card.
  function _recipeIngChips(ings, cls) {
    return (ings || []).map(function (ing) {
      var label = _esc(ing.name) + (ing.quantity ? ' -- ' + _esc(ing.quantity) : '');
      if (ing.species_id && ing.matched_species_name) {
        return '<a class="' + cls + ' matched" href="/species?s=' +
          encodeURIComponent(ing.matched_species_name) +
          '" target="_blank" rel="noopener" style="text-decoration:none" ' +
          'title="View ' + _esc(ing.matched_species_name) + '">' + label + '</a>';
      }
      return '<span class="' + cls + '">' + label + '</span>';
    }).join('');
  }

  // A field_recipe suggestion from extraction -- render a save-card.
  // Returns '' when confirmed so the suggestions panel hides cleanly once
  // all items have been actioned.
  function _renderRecipeSuggestion(enc, s) {
    if (s.status === 'confirmed') {
      return '';   // confirmed -- hide from panel; recipe is in the recipe bank
    }
    var ings  = _recipeIngChips(s.ingredients, 'src-ing');
    var body  = s.body ? '<div class="src-body">' + _esc(s.body).replace(/\n/g, '<br>') + '</div>' : '';
    var quote = s.quote ? '<div class="sugg-quote">"' + _esc(s.quote) + '"</div>' : '';
    return '<div class="sugg-recipe-card">' +
      '<div class="src-title">🍲 ' + _esc(s.title || 'Field recipe') +
        '<span style="font-size:0.66rem;color:#888;margin-left:8px;font-weight:400">detected recipe -- review &amp; save</span></div>' +
      (ings ? '<div class="src-ings">' + ings + '</div>' : '') +
      body + quote +
      '<div class="src-acts" data-guest-hide>' +
        '<button class="btn-fr-save" onclick="saveFieldRecipeFromSuggestion(' + enc.id + ',\'' + _esc(s.id) + '\')">💾 Save as field recipe</button>' +
        '<button class="btn-sugg no" onclick="resolveSuggestion(' + enc.id + ',\'' + _esc(s.id) + '\',\'dismiss\')">✕</button>' +
      '</div>' +
    '</div>';
  }

  // A saved field recipe stored on the encounter.
  function _renderFieldRecipeBlock(enc) {
    var fr = enc.field_recipe;
    if (!fr) return '';
    var ings = _recipeIngChips(fr.ingredients, 'fr-ing-chip');
    var body = fr.body ? '<div class="fr-body">' + _esc(fr.body).replace(/\n/g, '<br>') + '</div>' : '';
    var meta = fr.location_name ? '<span class="fr-meta">' + _esc(fr.location_name) + '</span>' : '';
    return '<div class="field-recipe-block" id="fr-block-' + enc.id + '">' +
      '<div class="fr-header"><span class="fr-title">🍲 ' + _esc(fr.title || 'Field recipe') + '</span>' + meta + '</div>' +
      (ings ? '<div class="fr-ings">' + ings + '</div>' : '') +
      body +
      '<div class="fr-actions" data-guest-hide>' +
        '<button class="btn-fr-edit" onclick="editFieldRecipe(' + enc.id + ')">✎ Edit</button>' +
        '<button class="btn-fr-del" onclick="deleteFieldRecipe(' + enc.id + ')">🗑 Remove</button>' +
      '</div>' +
    '</div>';
  }

  async function _patchFieldRecipe(encId, payload) {
    var resp = await fetch('/api/encounters/' + encId + '/field-recipe', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!resp.ok) {
      var e = await resp.json().catch(function () { return {}; });
      throw new Error(e.detail || resp.status);
    }
    return resp.json();
  }

  window.saveFieldRecipeFromSuggestion = async function (encId, suggId) {
    var enc = _encById[encId];
    if (!enc) return;
    var s = (enc.suggestions || []).find(function (x) { return x.id === suggId; });
    if (!s) return;
    _toolMsg(encId, 'Saving field recipe...', false);
    try {
      await _patchFieldRecipe(encId, {
        title:         s.title || 'Field recipe',
        body:          s.body || '',
        ingredients:   s.ingredients || [],
        date:          enc.encounter_date || null,
        location_name: enc.location_name || null,
      });
      // Dismiss the suggestion so only the saved recipe shows on reload.
      await fetch('/api/encounters/' + encId + '/suggestions/' + suggId + '/dismiss',
                  { method: 'POST' }).catch(function () {});
      _toolMsg(encId, 'Field recipe saved ✓', false);
      loadEncounters();
    } catch (e) { _toolMsg(encId, 'Could not save recipe: ' + e.message, true); }
  };

  window.deleteFieldRecipe = async function (encId) {
    if (!confirm('Remove this field recipe? (The encounter and its transcript are kept.)')) return;
    try {
      var resp = await fetch('/api/encounters/' + encId + '/field-recipe', { method: 'DELETE' });
      if (!resp.ok) throw new Error(resp.status);
      loadEncounters();
    } catch (e) { _toolMsg(encId, 'Could not remove recipe: ' + e.message, true); }
  };

  window.editFieldRecipe = function (encId) {
    var enc = _encById[encId];
    if (!enc || !enc.field_recipe) return;
    var fr = enc.field_recipe;
    var block = document.getElementById('fr-block-' + encId);
    if (!block) return;
    block.innerHTML =
      '<input class="fr-edit-input" id="fr-title-' + encId + '" value="' + _esc(fr.title || '') + '" placeholder="Recipe title">' +
      '<textarea class="fr-edit-input" id="fr-body-' + encId + '" placeholder="Preparation notes">' + _esc(fr.body || '') + '</textarea>' +
      '<div class="fr-actions">' +
        '<button class="btn-fr-save" onclick="saveFieldRecipeEdit(' + encId + ')">Save</button>' +
        '<button class="btn-fr-edit" onclick="loadEncounters()">Cancel</button>' +
      '</div>';
  };

  window.saveFieldRecipeEdit = async function (encId) {
    var enc = _encById[encId];
    if (!enc) return;
    var fr = enc.field_recipe || {};
    var titleEl = document.getElementById('fr-title-' + encId);
    var bodyEl  = document.getElementById('fr-body-' + encId);
    try {
      await _patchFieldRecipe(encId, {
        title:         (titleEl ? titleEl.value : '').trim() || 'Field recipe',
        body:          bodyEl ? bodyEl.value : '',
        ingredients:   fr.ingredients || [],
        date:          enc.encounter_date || null,
        location_name: fr.location_name || enc.location_name || null,
      });
      loadEncounters();
    } catch (e) { _toolMsg(encId, 'Could not save edit: ' + e.message, true); }
  };

  // -- Transcription + extraction (laptop-side, data-guest-hide) -
  function _toolMsg(id, text, isErr) {
    var el = document.getElementById('toolmsg-' + id);
    if (el) { el.textContent = text; el.className = 'tool-msg' + (isErr ? ' err' : ''); }
  }

  window.transcribeEncounter = async function (id, btn) {
    var prev = btn.textContent;
    btn.disabled = true; btn.textContent = 'Transcribing...';
    _toolMsg(id, 'Sending audio to Whisper... (~£0.006/min)', false);
    try {
      var resp = await fetch('/api/encounters/' + id + '/transcribe', { method: 'POST' });
      var data = await resp.json().catch(function () { return {}; });
      if (!resp.ok) throw new Error(data.detail || resp.status);
      _toolMsg(id, 'Transcribed ✓', false);
      loadEncounters();
    } catch (e) {
      btn.disabled = false; btn.textContent = prev;
      _toolMsg(id, 'Transcription failed: ' + e.message, true);
    }
  };

  window.extractEncounter = async function (id, btn) {
    var prev = btn.textContent;
    btn.disabled = true; btn.textContent = 'Tagging...';
    _toolMsg(id, 'Reading transcript for cues...', false);
    try {
      var resp = await fetch('/api/encounters/' + id + '/extract', { method: 'POST' });
      var data = await resp.json().catch(function () { return {}; });
      if (!resp.ok) throw new Error(data.detail || resp.status);
      var n = (data.suggestions || []).length;
      _toolMsg(id, n ? ('Found ' + n + ' suggestion' + (n === 1 ? '' : 's')) : 'No cues found in transcript', false);
      loadEncounters();
    } catch (e) {
      btn.disabled = false; btn.textContent = prev;
      _toolMsg(id, 'Tagging failed: ' + e.message, true);
    }
  };

  window.resolveSuggestion = async function (encId, suggId, action) {
    try {
      var resp = await fetch('/api/encounters/' + encId + '/suggestions/' + suggId + '/' + action,
                             { method: 'POST' });
      if (!resp.ok) { var err = await resp.json().catch(function () { return {}; }); throw new Error(err.detail || resp.status); }
      loadEncounters();
      if (_browseLoaded) loadBrowseTab();
    } catch (e) { _toolMsg(encId, 'Could not ' + action + ' suggestion: ' + e.message, true); }
  };

  // -- Delete encounter ---------------------------------------
  window.deleteEncounter = async function (id) {
    if (!confirm('Delete this encounter?')) return;
    try {
      await fetch('/api/encounters/' + id, { method: 'DELETE' });
      loadEncounters();
    } catch (e) { alert('Delete failed.'); }
  };

  // -- My Season standing list --------------------------------
  window.loadMySeason = async function () {
    var grid = document.getElementById('season-grid');
    try {
      var data = await (await fetch('/api/personal-lists/my-season')).json();
      var sp = data.species || [];
      if (!sp.length) {
        grid.innerHTML = '<div class="empty-msg">No species in My Season yet -- add one above, ' +
          'or open a species card and use "Add to My Season".</div>';
        return;
      }
      grid.innerHTML = sp.map(_seasonCard).join('');
    } catch (e) {
      grid.innerHTML = '<div class="empty-msg" style="color:#f87171">Failed to load My Season.</div>';
    }
  };

  function _seasonCard(s) {
    var thumb = s.thumbnail
      ? '<img class="season-thumb" src="/thumbnails/' + _esc(s.thumbnail.split('/').pop()) +
        '" onerror="this.outerHTML=\'<div class=&quot;season-thumb placeholder&quot;>🌿</div>\'">'
      : '<div class="season-thumb placeholder">🌿</div>';
    var edib = (s.edibility_status || 'none').toLowerCase();
    var countTxt = s.encounter_count
      ? s.encounter_count + ' encounter' + (s.encounter_count === 1 ? '' : 's')
      : 'No encounters yet';
    return '<div class="season-card" onclick="openCard(' + s.species_id + ')">' +
      '<button class="season-remove" data-guest-hide title="Remove from My Season" ' +
        'onclick="event.stopPropagation();removeSpecies(' + s.species_id + ')">✕</button>' +
      thumb +
      '<div class="season-body">' +
        '<div class="season-sci">' + _esc(s.scientific_name) + '</div>' +
        '<div class="season-common">' + _esc(s.common_name || '') + '</div>' +
        '<span class="pill ' + edib + '">' + _esc(s.edibility_status || 'unknown') + '</span>' +
        '<div class="season-count">' + countTxt + '</div>' +
      '</div>' +
    '</div>';
  }

  window.addSpecies = async function () {
    var sel = document.getElementById('add-species-select');
    var id = sel.value; if (!id) return;
    var btn = document.getElementById('btn-add-species'); btn.disabled = true;
    try {
      var resp = await fetch('/api/personal-lists/my-season/species', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ species_id: parseInt(id, 10) }),
      });
      if (!resp.ok) throw new Error((await resp.json().catch(function () { return {}; })).detail || resp.status);
      sel.value = ''; loadMySeason();
    } catch (e) { alert('Could not add: ' + e.message); }
    finally { btn.disabled = false; }
  };

  window.removeSpecies = async function (speciesId) {
    if (!confirm('Remove this species from My Season? (Your encounters are kept.)')) return;
    try {
      await fetch('/api/personal-lists/my-season/species/' + speciesId, { method: 'DELETE' });
      loadMySeason();
    } catch (e) { alert('Remove failed.'); }
  };

  // -- Encounter lists -- split by pipeline --------------------
  // One fetch, split client-side by encounter_type. The New Encounter tab shows
  // the observation pipeline (encounter_type 'field' or legacy/null); the My
  // Season tab shows season recordings. foraging_note recordings belong to the
  // species-card pipeline and are intentionally not shown on either tab here.
  // An empty list renders "No recordings yet" rather than hanging on "Loading...".
  function _renderList(el, encs) {
    if (!el) return;
    if (!encs.length) { el.innerHTML = '<div class="empty-msg">No recordings yet</div>'; return; }
    el.innerHTML = encs.map(_renderCard).join('');
  }

  async function _initViewMode(uid) {
    var banner = document.getElementById('view-banner');
    if (!banner) return;
    var name = 'participant ' + uid;
    try {
      var parts = await (await fetch('/api/workshop/participants')).json();
      var p = Array.isArray(parts) ? parts.find(function(x) { return x.id === uid; }) : null;
      if (p) name = p.name;
    } catch(_) {}
    banner.innerHTML = '&#128065; Encounters for: <strong>' + _esc(name) + '</strong>' +
      ' <a href="/encounters"><- Back to your own</a>';
    banner.style.display = '';
  }

  window.loadEncounters = async function () {
    var listNew    = document.getElementById('enc-list-new');
    var listSeason = document.getElementById('enc-list-season');
    try {
      var encUrl = '/api/encounters' + (_viewUserId ? '?user_id=' + _viewUserId : '');
      var data = await (await fetch(encUrl)).json();
      var encs = data.encounters || [];
      var fieldEncs  = encs.filter(function (e) {
        return e.encounter_type === 'field' || e.encounter_type == null;
      });
      var seasonEncs = encs.filter(function (e) { return e.encounter_type === 'season'; });
      _renderList(listNew, fieldEncs);
      _renderList(listSeason, seasonEncs);
    } catch (e) {
      var errHtml = '<div class="empty-msg" style="color:#f87171">Failed to load recordings.</div>';
      if (listNew)    listNew.innerHTML = errHtml;
      if (listSeason) listSeason.innerHTML = errHtml;
    }
  };

  // -- Personal card overlay ----------------------------------
  window.openCard = async function (speciesId) {
    var overlay = document.getElementById('card-overlay');
    var card = document.getElementById('personal-card');
    card.innerHTML = '<div style="padding:30px;text-align:center;color:#777">Loading card...</div>';
    overlay.classList.add('open');
    try {
      var d = await (await fetch('/api/personal-lists/card/' + speciesId)).json();
      card.innerHTML = _buildPersonalCard(d);
    } catch (e) {
      card.innerHTML = '<div style="padding:30px;color:#a33">Failed to load personal card.</div>';
    }
  };

  window.closeCard = function () {
    document.getElementById('card-overlay').classList.remove('open');
    if (new URLSearchParams(location.search).get('species')) {
      history.replaceState({}, '', '/encounters');
    }
  };

  function _buildPersonalCard(d) {
    var sp = d.species || {};
    var photo = sp.thumbnail
      ? '<img class="pc-photo" src="/thumbnails/' + _esc(sp.thumbnail.split('/').pop()) +
        '" onerror="this.outerHTML=\'<div class=&quot;pc-photo placeholder&quot;>🌿</div>\'">'
      : '<div class="pc-photo placeholder">🌿</div>';

    var meta = [];
    if (sp.edibility_status) meta.push('<span class="pc-edib">' + _esc(sp.edibility_status) + '</span>');
    if (sp.peak_season) meta.push(_esc(sp.peak_season));

    var html = '<div class="pc-head">' + photo +
      '<div class="pc-title">' +
        '<div class="pc-sci">' + _esc(sp.scientific_name || '--') + '</div>' +
        (sp.common_name ? '<div class="pc-common">' + _esc(sp.common_name) + '</div>' : '') +
        (meta.length ? '<div class="pc-meta">' + meta.join(' ') + '</div>' : '') +
      '</div></div>';

    if (d.recipe && d.recipe.body) {
      html += '<div class="pc-section"><h4>Recipe</h4>' +
        (d.recipe.title ? '<div class="pc-recipe-title">' + _esc(d.recipe.title) + '</div>' : '') +
        '<div class="pc-text">' + _esc(d.recipe.body) + '</div></div>';
    }
    var notes = d.notes || {};
    if (notes.id_notes)    html += '<div class="pc-section"><h4>Identification notes</h4><div class="pc-text">' + _esc(notes.id_notes) + '</div></div>';
    if (notes.taste_notes) html += '<div class="pc-section"><h4>Taste &amp; texture</h4><div class="pc-text">' + _esc(notes.taste_notes) + '</div></div>';

    html += '<div class="pc-section"><h4>Your encounters (' + (d.encounter_count || 0) + ')</h4>';
    if (!d.encounters || !d.encounters.length) {
      html += '<div class="pc-text" style="color:#888">No encounters recorded yet for this species.</div>';
    } else {
      d.encounters.forEach(function (e) {
        var when = e.encounter_date ? new Date(e.encounter_date).toLocaleString() : '--';
        var where = e.location_name || (e.latitude != null ? e.latitude.toFixed(4) + ', ' + e.longitude.toFixed(4) : '');
        html += '<div class="pc-enc">' +
          '<div class="pc-enc-date">' + _esc(when) + (where ? ' · ' + _esc(where) : '') + '</div>' +
          (e.prompt_response ? '<div class="pc-enc-prompt"><span class="tag">Stage 1 · what do you actually see?</span>' + _esc(e.prompt_response) + '</div>' : '') +
          (e.text_note ? '<div class="pc-enc-note">' + _esc(e.text_note) + '</div>' : '') +
          (e.audio_url ? '<div class="pc-enc-audio">🎙 Audio note recorded</div>' : '') +
        '</div>';
      });
    }
    html += '</div>';
    html += '<div class="pc-readonly-note">Species name, photo, recipe and notes are drawn read-only from the shared species record. ' +
            'Your encounters are personal to you.</div>';
    html += '<div class="pc-credit">ForagingID · Melvin Jarman</div>';
    return html;
  }

  // -- Helpers ------------------------------------------------
  function _esc(s) {
    if (s == null) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // -- Reading note capture ------------------------------------
  // Separate recorder state -- isolated from the field-encounter recorder so
  // both tabs can exist without cross-contamination.
  var _rnRecorder = null, _rnChunks = [], _rnBlob = null, _rnName = null;
  var _rnStream = null, _rnAudioCtx = null, _rnAnalyser = null, _rnRafId = null;
  var _rnWakeLock = null;

  window.rnStartRecording = async function () {
    try {
      _rnStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      _rnChunks = []; _rnBlob = null; _rnName = null;
      _rnRecorder = new MediaRecorder(_rnStream);
      _rnRecorder.ondataavailable = function (e) { if (e.data.size) _rnChunks.push(e.data); };
      _rnRecorder.onstop = function () {
        _rnBlob = new Blob(_rnChunks, { type: 'audio/webm' });
        _rnName = 'reading-note.webm';
        var url = URL.createObjectURL(_rnBlob);
        var prev = document.getElementById('rn-audio-preview');
        prev.src = url; prev.style.display = '';
        document.getElementById('rn-post-rec-row').style.display = '';
        document.getElementById('rn-rec-hint').textContent = 'Recording ready';
        document.getElementById('rn-rec-hint').className = 'rec-hint';
      };
      _rnRecorder.start();
      _rnStartVisualiser();
      _rnRequestWakeLock();
      document.getElementById('rn-btn-start').style.display = 'none';
      document.getElementById('rn-btn-stop').style.display = '';
      document.getElementById('rn-rec-status').style.display = '';
      document.getElementById('rn-post-rec-row').style.display = 'none';
      document.getElementById('rn-audio-preview').style.display = 'none';
      document.getElementById('rn-rec-hint').textContent = 'Recording...';
      document.getElementById('rn-rec-hint').className = 'rec-hint recording';
    } catch (e) { alert('Microphone access denied or unavailable.'); }
  };

  window.rnStopRecording = function () {
    if (_rnRecorder && _rnRecorder.state !== 'inactive') {
      _rnRecorder.stop();
      _rnRecorder.stream.getTracks().forEach(function (t) { t.stop(); });
    }
    _rnStopVisualiser();
    _rnReleaseWakeLock();
    document.getElementById('rn-btn-stop').style.display = 'none';
    document.getElementById('rn-rec-status').style.display = 'none';
    document.getElementById('rn-btn-start').style.display = '';
  };

  window.rnPlayBack = function () {
    var prev = document.getElementById('rn-audio-preview');
    prev.style.display = ''; prev.play();
  };

  window.rnDiscard = function () {
    _rnBlob = null; _rnName = null; _rnChunks = [];
    document.getElementById('rn-post-rec-row').style.display = 'none';
    document.getElementById('rn-audio-preview').style.display = 'none';
    document.getElementById('rn-audio-preview').src = '';
    document.getElementById('rn-upload-name').textContent = '';
    document.getElementById('rn-file-input').value = '';
    document.getElementById('rn-rec-hint').textContent = 'Tap to record';
    document.getElementById('rn-rec-hint').className = 'rec-hint';
  };

  window.rnHandleUpload = function (ev) {
    var file = ev.target.files && ev.target.files[0];
    if (!file) return;
    _rnBlob = file; _rnName = file.name;
    var prev = document.getElementById('rn-audio-preview');
    prev.src = URL.createObjectURL(file); prev.style.display = '';
    document.getElementById('rn-post-rec-row').style.display = '';
    document.getElementById('rn-upload-name').textContent = 'Selected: ' + file.name;
    document.getElementById('rn-rec-hint').textContent = 'File ready';
    document.getElementById('rn-rec-hint').className = 'rec-hint';
  };

  window.rnSave = async function () {
    var source = document.getElementById('rn-source').value.trim();
    var msgEl = document.getElementById('rn-save-msg');
    var btn = document.getElementById('rn-btn-save');

    if (!source) {
      msgEl.textContent = 'Enter a source name before saving.';
      msgEl.className = 'save-msg err';
      document.getElementById('rn-source').focus();
      return;
    }
    if (!_rnBlob) {
      msgEl.textContent = 'Record or upload audio first.';
      msgEl.className = 'save-msg err';
      return;
    }

    btn.disabled = true; btn.textContent = 'Transcribing...';
    msgEl.textContent = ''; msgEl.className = 'save-msg';

    try {
      var fd = new FormData();
      fd.append('source', source);
      fd.append('audio', _rnBlob, _rnName || 'reading-note.webm');
      var resp = await fetch('/api/encounters/reading-note', { method: 'POST', body: fd });
      if (!resp.ok) {
        var err = await resp.json().catch(function () { return {}; });
        throw new Error(err.detail || resp.status);
      }
      var data = await resp.json();
      msgEl.innerHTML = '✓ Note saved to goethean_sources.md<br><span style="color:#aaa;font-size:0.82rem">' + _esc(data.transcript.slice(0, 200)) + (data.transcript.length > 200 ? '...' : '') + '</span>';
      msgEl.className = 'save-msg ok';
      // Reset form
      document.getElementById('rn-source').value = '';
      rnDiscard();
    } catch (e) {
      msgEl.textContent = 'Error: ' + e.message;
      msgEl.className = 'save-msg err';
    } finally {
      btn.disabled = false; btn.textContent = 'Save reading note';
    }
  };

  // Waveform visualiser for reading-note tab (reuses dandelion draw logic via _drawDandelion
  // -- but _drawDandelion references _cap(ctx, 'waveform') which won't find 'rn-waveform').
  // So we inline a lightweight version that targets the rn canvas directly.
  function _rnStartVisualiser() {
    var canvas = document.getElementById('rn-waveform');
    canvas.style.display = '';
    try {
      _rnAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
      var src = _rnAudioCtx.createMediaStreamSource(_rnStream);
      _rnAnalyser = _rnAudioCtx.createAnalyser();
      _rnAnalyser.fftSize = 1024;
      src.connect(_rnAnalyser);
      _rnDrawFrame(canvas);
    } catch (e) { canvas.style.display = 'none'; }
  }

  function _rnStopVisualiser() {
    if (_rnRafId) { cancelAnimationFrame(_rnRafId); _rnRafId = null; }
    if (_rnAudioCtx) { _rnAudioCtx.close().catch(function () {}); _rnAudioCtx = null; }
    _rnAnalyser = null;
    var canvas = document.getElementById('rn-waveform');
    if (canvas) { canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height); canvas.style.display = 'none'; }
  }

  function _rnDrawFrame(canvas) {
    var ctx = canvas.getContext('2d');
    var W = canvas.width, H = canvas.height;
    var buf = new Uint8Array(_rnAnalyser.fftSize);
    var LOBES = 9, phase = 0;
    function rnd(n) { var s = Math.sin(n * 12.9898 + 78.233) * 43758.5453; return s - Math.floor(s); }
    function frame() {
      _rnRafId = requestAnimationFrame(frame);
      _rnAnalyser.getByteTimeDomainData(buf);
      var sum = 0;
      for (var i = 0; i < buf.length; i++) { var v = (buf[i] - 128) / 128; sum += v * v; }
      var drive = Math.min(1, Math.sqrt(sum / buf.length) * 4);
      phase += 0.05;
      ctx.clearRect(0, 0, W, H);
      var midY = H / 2, baseX = 14, tipX = W - 12, span = tipX - baseX;
      var maxTooth = (H / 2) - 5, step = span / LOBES;
      var lobe = function (t, seed) {
        var jit = (rnd(t * 1.7 + seed) - 0.5) * step * 0.40;
        var x = baseX + (t / LOBES) * span + jit;
        var grow = 0.30 + 0.70 * (t / LOBES);
        var irr = 0.35 + 0.65 * rnd(t * 3.3 + seed);
        var env = grow * irr;
        var lean = step * (0.24 + 0.36 * rnd(t * 5.1 + seed));
        var sinus = 1.5 + rnd(t * 2.2 + seed) * 4.5;
        var wob = 0.60 + 0.40 * Math.sin(phase + t * 0.9 + seed);
        var amp = env * (0.55 + 0.45 * drive * wob);
        return { x: x, len: 6 + amp * maxTooth, lean: lean, sinus: sinus };
      };
      ctx.beginPath();
      ctx.moveTo(baseX, midY);
      for (var t = 1; t <= LOBES; t++) {
        var u = lobe(t, 0);
        ctx.lineTo(u.x - step * 0.55, midY - u.sinus);
        ctx.lineTo(u.x - u.lean, midY - u.len);
        ctx.lineTo(u.x, midY - u.sinus * 0.5);
      }
      ctx.lineTo(tipX, midY);
      for (var b = LOBES; b >= 1; b--) {
        var d = lobe(b, 50);
        ctx.lineTo(d.x, midY + d.sinus * 0.5);
        ctx.lineTo(d.x - d.lean, midY + d.len);
        ctx.lineTo(d.x - step * 0.55, midY + d.sinus);
      }
      ctx.closePath();
      var green = 120 + Math.round(drive * 90);
      ctx.fillStyle = 'rgba(58,' + green + ',42,0.5)';
      ctx.strokeStyle = 'rgba(150,215,125,0.9)'; ctx.lineWidth = 1.3;
      ctx.fill(); ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(baseX - 4, midY); ctx.lineTo(tipX, midY);
      ctx.strokeStyle = 'rgba(205,238,175,0.9)'; ctx.lineWidth = 2.6; ctx.stroke();
    }
    frame();
  }

  function _rnRequestWakeLock() {
    var toggle = document.getElementById('rn-wakelock');
    if (!toggle || !toggle.checked || !('wakeLock' in navigator)) return;
    navigator.wakeLock.request('screen').then(function (lock) {
      _rnWakeLock = lock;
      _rnWakeLock.addEventListener('release', function () { _rnWakeLock = null; });
    }).catch(function () {});
  }
  function _rnReleaseWakeLock() {
    if (_rnWakeLock) { _rnWakeLock.release().catch(function () {}); _rnWakeLock = null; }
  }

})();
