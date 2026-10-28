// ── Save / recall walks ────────────────────────────────────────────────────

async function promptSaveWalk() {
  if (!_activeWalkRoute || !_activeWalkRoute.length) {
    alert('No walk route to save. Draw a selection area first.');
    return;
  }
  // One save at a time — a second click while the prompt or request is open is ignored.
  if (_walkSaving) return;
  _walkSaving = true;
  const btn = document.getElementById('walk-save-btn');
  if (btn) btn.disabled = true;
  let saved = false;
  try {
    await _saveWalk(btn, () => { saved = true; });
  } finally {
    _walkSaving = false;
    if (btn) {
      btn.disabled = false;
      if (!saved) btn.textContent = '💾 Save walk';
    }
  }
}

function _showWalkSaveStatus(text, ok) {
  const el = document.getElementById('walk-save-status');
  if (!el) return;
  el.textContent = text;
  el.style.color = ok ? '#166534' : '#b91c1c';
  el.style.display = 'block';
  clearTimeout(_showWalkSaveStatus._t);
  _showWalkSaveStatus._t = setTimeout(() => { el.style.display = 'none'; }, 8000);
}

async function _saveWalk(btn, onSaved) {
  const sig = _walkRouteSig(_activeWalkRoute);
  // Same route as the walk just saved / loaded → warn before making a copy.
  if (_walkSaved && _walkSaved.sig === sig &&
      !confirm(`This route is already saved as "${_walkSaved.name}".\n\nSave another copy?`)) {
    return;
  }

  const name = prompt('Name this walk:');
  if (!name || !name.trim()) return;

  // Same name already in the saved list → warn (the list is the source of truth,
  // so this also catches copies saved in an earlier session).
  try {
    const lr = await fetch('/api/walk/saves');
    if (lr.ok) {
      const { walks } = await lr.json();
      const lower = name.trim().toLowerCase();
      const n = (walks || []).filter(w => (w.name || '').trim().toLowerCase() === lower).length;
      if (n && !confirm(`${n === 1 ? 'A walk' : n + ' walks'} named "${name.trim()}" already saved.\n\nSave another with the same name?`)) {
        return;
      }
    }
  } catch (_) { /* list unavailable — save anyway, the POST reports real failures */ }

  if (btn) btn.textContent = '⏳ Saving…';

  // Straight-line distance fallback
  let distM = _walkOrsDistM;
  if (!distM) {
    for (let i = 1; i < _activeWalkRoute.length; i++) {
      distM += _haversineM(
        _activeWalkRoute[i-1].lat, _activeWalkRoute[i-1].lng,
        _activeWalkRoute[i].lat,   _activeWalkRoute[i].lng
      );
    }
  }

  const payload = {
    name: name.trim(),
    // Observation ids only — field-note stops carry a NOTE id in p.id and must
    // never be stored as observation ids.
    obs_ids:     _activeWalkRoute.filter(s => !s.p.is_note)
                   .flatMap(s => (s.obs_ids && s.obs_ids.length) ? s.obs_ids : [s.p.id])
                   .filter(Boolean),
    // One waypoint per STOP (a stop can hold several species/observations).
    waypoints:   _activeWalkRoute.map((s, i) => s.p.is_note
      ? { type: 'note', lat: s.lat, lng: s.lng, note_id: s.p.id || null, label: 'Note' }
      : { type: 'obs',  lat: s.lat, lng: s.lng,
          obs_ids: (s.obs_ids && s.obs_ids.length) ? s.obs_ids : (s.p.id != null ? [s.p.id] : []),
          labels:  _stopSpecies(s).length ? _stopSpecies(s) : [`Stop ${i+1}`] }),
    // Route shape + walk options, stored without a migration (route_geojson is
    // a free-form JSON column). `foragingid` is a GeoJSON foreign member holding
    // our own metadata; features is empty when ORS was unavailable.
    route_geojson: {
      type: 'FeatureCollection',
      features: _walkRouteGeom
        ? [{ type: 'Feature', geometry: _walkRouteGeom, properties: {} }]
        : [],
      foragingid: Object.assign(
        { version: 2, circular: !!_walkCircular, stop_radius_m: _walkStopRadiusM },
        // Re-saving a loaded walk keeps its dashed straight legs.
        (_walkRouteGeom && _walkStraightRanges.length) ? { straight_ranges: _walkStraightRanges } : {}),
    },
    distance_m:  Math.round(distM),
    duration_min: _walkOrsDurMin > 0 ? _walkOrsDurMin : Math.round(distM / 80),
  };

  try {
    const r = await fetch('/api/walk/saves', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `HTTP ${r.status}`);
    const d = await r.json();
    _walkSaved = { id: d.id, name: d.name || payload.name, sig };
    onSaved();
    if (btn) {
      btn.textContent = '✓ Saved';
      setTimeout(() => { if (!_walkSaving) btn.textContent = '💾 Save walk'; }, 4000);
    }
    _showWalkSaveStatus(`✓ Saved as "${_walkSaved.name}"`, true);
    _walkRefreshTitles();
    loadSavedWalksList();
  } catch (e) {
    _showWalkSaveStatus('Save failed: ' + e.message, false);
    alert('Save failed: ' + e.message);
  }
}

async function loadSavedWalksList() {
  const listEl = document.getElementById('wbs-saved-walks-list');
  if (!listEl) return;
  try {
    const r = await fetch('/api/walk/saves');
    if (!r.ok) return;
    const { walks } = await r.json();
    listEl.innerHTML = !walks.length
      ? '<div style="font-size:0.75rem;color:#aaa;padding:6px 4px">No saved walks yet</div>'
      : walks.map(w => {
          const d = w.distance_m < 1000 ? `${Math.round(w.distance_m)}m` : `${(w.distance_m/1000).toFixed(1)}km`;
          const date = w.created_at ? new Date(w.created_at).toLocaleDateString() : '';
          return `<div class="saved-walk-row">
            <div class="saved-walk-info" onclick="loadSavedWalk(${w.id})">
              <div class="saved-walk-name">${_esc(w.name)}</div>
              <div class="saved-walk-meta">${w.stop_count} stop${w.stop_count!==1?'s':''} · ${d}${date?' · '+date:''}</div>
            </div>
            <button class="saved-walk-del" onclick="deleteSavedWalk(${w.id})">✕</button>
          </div>`;
        }).join('');
  } catch (_) {}
}


// Load-sequence token: a load is "current" only while no newer loadSavedWalk has
// started. Every step after an await checks it, so two loads clicked back to
// back (id 3 then id 4) end with the map AND panel on the later one.
let _walkLoadSeq = 0;

async function loadSavedWalk(id) {
  const mySeq = ++_walkLoadSeq;
  const stale = () => mySeq !== _walkLoadSeq;
  let myBuild = null;                       // _walkBuildSeq of the route build this load started
  // A stale load leaves nothing of its own on the map: the route layer goes only
  // if THIS load's build drew it (tagged in _drawWalkLayer) — never a newer one's.
  const dropStale = () => {
    if (myBuild !== null && _walkRouteLayer && _walkRouteLayer._walkBuildSeq === myBuild) {
      map.removeLayer(_walkRouteLayer);
      _walkRouteLayer = null;
    }
  };
  try {
    const r = await fetch(`/api/walk/saves/${id}`);
    if (stale()) return;
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const w = await r.json();
    if (stale()) return;
    _walkPinSelExit();              // another walk: marks and highlights belong to the old one
    _walkPendingClear();
    _walkHighlightClear();
    if (!w.waypoints || !w.waypoints.length) {
      alert('This saved walk has no waypoints.');
      return;
    }
    // Stops come from the server (walk_membership.py): species resolved from the
    // CURRENT observations, plus photos that joined by route proximity ("7a").
    // The stored waypoint labels below are only a fallback for a response
    // without `stops` (older server).
    _savedWalkData = Array.isArray(w.stops)
      ? { id: w.id, name: w.name, stops: w.stops, membership: w.membership || null, names: w.names || {} }
      : null;
    // Legacy rebuild, matching _buildWalkRoute output shape.
    // v2 walks (stop clustering): an obs waypoint is a STOP — obs_ids[] + labels[].
    // v1 walks: type 'obs' (single obs_id + label) or 'note' (note_id).
    // Old walks (no type): a note is label 'Note', and its note id was stored
    // in obs_id — read it as the note id, never as an observation id.
    const route = _savedWalkData ? _savedWalkRoute() : w.waypoints.map(wp => {
      const isNote = wp.type === 'note' || (!wp.type && wp.label === 'Note');
      if (isNote) {
        return {
          lat: wp.lat, lng: wp.lng, pins: null, species: [], obs_ids: [],
          p: { species_primary: null, is_note: true,
               id: wp.note_id != null ? wp.note_id : (wp.obs_id != null ? wp.obs_id : null) },
        };
      }
      const labels = Array.isArray(wp.labels) ? wp.labels.filter(Boolean)
                   : (wp.label ? [wp.label] : []);
      const ids    = Array.isArray(wp.obs_ids) ? wp.obs_ids.filter(x => x != null)
                   : (wp.obs_id != null ? [wp.obs_id] : []);
      return {
        lat: wp.lat, lng: wp.lng, pins: null, species: labels, obs_ids: ids,
        p: { species_primary: labels[0] || null, is_note: false, id: ids[0] != null ? ids[0] : null },
      };
    });
    // Saved shape + options (new walks); old walks have neither → one-way, re-route.
    const _meta      = (w.route_geojson && w.route_geojson.foragingid) || null;
    // The line AS SHOWN (circular / point-to-point view of the stored line) when
    // the server sends it; else the stored geometry (older server).
    const _shown     = w.shown && Array.isArray(w.shown.coordinates) && w.shown.coordinates.length > 1 ? w.shown : null;
    const _savedGeom = _shown ? { type: 'LineString', coordinates: _shown.coordinates }
                     : (w.route_geojson && w.route_geojson.features
                        && w.route_geojson.features[0] && w.route_geojson.features[0].geometry);
    _walkCircular     = _shown ? !!_shown.circular : (_meta ? !!_meta.circular : false);
    _walkLineClosed   = _shown ? !!_shown.line_closed : false;
    _syncWalkLoopUi();
    // A loaded walk is not a drawn area: forget any earlier rectangle/circle so
    // the circular toggle can never rebuild an old area over this walk.
    _lastWalkBounds   = null;
    _lastWalkCircle   = null;
    // A loaded walk's stops are fixed (no raw pins to regroup): show the radius
    // it was saved with, slider disabled.
    _walkLastPins     = null;
    _walkStraightLine = false;
    if (_meta && _meta.stop_radius_m) _walkStopRadiusM = _meta.stop_radius_m;
    _syncWalkRadiusUi(false);
    _walkTidySeq++;              // a build still waiting for its stop order is dropped
    _activeWalkRoute  = route;
    _walkSelected     = route;
    _activeWalkEnrich = {};
    // Header shows the walk's name (after _walkCircular is set — it is part of the signature).
    _walkSaved        = { id: w.id, name: w.name, sig: _walkRouteSig(route) };
    // Distance/duration for the shape shown (shown_line scales the saved figures
    // by line length; equal to them when nothing is cut or added). The saved
    // figures themselves are never overwritten.
    _walkOrsDistM     = (_shown ? _shown.distance_m : w.distance_m) || 0;
    _walkOrsDurMin    = (_shown ? _shown.duration_min : w.duration_min) || 0;
    // Remember the layer + view to return to on clear (first load only — a
    // second saved walk opened on top keeps the original), and hide every
    // other pin by default.
    if (!_savedWalkView) {
      _savedWalkView = {
        prevLayer:  ['pins', 'clusters', 'heatmap'].includes(currentLayer) ? currentLayer : 'pins',
        prevCenter: map.getCenter(),
        prevZoom:   map.getZoom(),
      };
    }
    _savedWalkView.hidePins = true;
    // Coming from "Build a walk" the rectangle/circle draw is attached, which
    // disables map dragging — a loaded walk has fixed stops, so drop it.
    _detachWalkDraw();
    _hideWalkRect();
    _hideWalkCircle();
    // Enter walk mode so clear-btn and proximity watch work correctly
    _walkActive = true;
    currentLayer = 'pins';
    _applyLayer();
    // Mark Walk layer button active
    _LAYER_BTNS.forEach(m => {
      const b = document.getElementById(`btn-layer-${m}`);
      if (b) b.classList.toggle('active', m === 'walk');
    });
    _startProxWatch();

    // Draw: the saved shape when there is one (no ORS call); old walks without a
    // shape ask ORS to DRAW only. Failures show the reason; the straight line is
    // only drawn if the user chooses it. Saved distance/duration kept.
    // fitBounds is done below by _fitSavedWalk, once the panel layout is known.
    myBuild = _walkBuildSeq + 1;            // _routeWalk takes ++_walkBuildSeq synchronously
    const _routed = await _routeWalk({ savedGeom: _savedGeom || null, keepSaved: true, suppressFitBounds: true,
                                      routeMeta: _shown ? { straight_ranges: _shown.straight_ranges } : _meta });
    if (stale()) { dropStale(); return; }
    if (!_routed) return;

    // Panel layout first (laptop: right-hand panel; phone: peek bar), then fit
    // the whole walk into the map area the panel leaves free.
    _savedWalkLayout(w.name);
    _syncWalkPinsBtn();
    _fitSavedWalk();

    // Enrich species (+ toxicity, for the walk panel's toxic guard)
    const uniqueSpecies = [...new Set(route.flatMap(_stopSpecies))];
    const _enrich = await _fetchWalkEnrich(uniqueSpecies);
    if (stale()) { dropStale(); return; }
    _activeWalkEnrich = _enrich;

    // Show walk panel — sheet is opened by _buildWalkRoute and renderWalkPanel
    _closeTabPanels();
    document.getElementById('filter-view').style.display = 'none';
    document.getElementById('detail-view').style.display = 'none';
    document.getElementById('walk-clear-btn').classList.add('visible');
    document.getElementById('walk-mode-toggle').classList.remove('visible');

    renderWalkPanel(route, _activeWalkEnrich);
    _renderWalkMembership();
    const _wbsBodyEl = document.getElementById('wbs-body');
    if (_wbsBodyEl) _wbsBodyEl.scrollTop = 0;   // header + Export summary, not the saved-walks list the click came from
  } catch (e) {
    if (stale()) { dropStale(); return; }     // a newer load is in charge — no alert for this one
    alert('Failed to load walk: ' + e.message);
  }
}

// Loaded saved walk layout. Laptop: the sheet becomes a full-height right-hand
// panel (.wbs-side). Phone: collapsed to a peek bar (.wbs-peek) the user drags
// up by the handle (the handle has no tap action). Both clear any inline
// transform left by a handle drag.
function _savedWalkLayout(name) {
  const sheet = document.getElementById('walk-bottom-sheet');
  if (!sheet) return;
  sheet.style.transform  = '';
  sheet.style.transition = '';
  sheet.classList.add('wbs-active', 'wbs-route-active');
  const chev = document.getElementById('wbs-chevron');
  if (isMobile()) {
    sheet.classList.remove('wbs-side', 'wbs-open');
    sheet.classList.add('wbs-peek');
    if (chev) chev.textContent = '▴';
  } else {
    sheet.classList.remove('wbs-peek');
    sheet.classList.add('wbs-side', 'wbs-open');
    if (chev) chev.textContent = '▾';
  }
  const lbl = document.getElementById('wbs-label');
  if (lbl) lbl.textContent = `${name} — pull up for stops`;
}

// Fit the whole loaded walk (stops + saved line) into the map area left free
// by the panel: right-hand panel width on laptop, peek bar height on phone.
function _fitSavedWalk() {
  const pts = (_activeWalkRoute || []).map(s => [s.lat, s.lng]);
  if (_walkRouteGeom && Array.isArray(_walkRouteGeom.coordinates)) {
    _walkRouteGeom.coordinates.forEach(([lng, lat]) => pts.push([lat, lng]));
  }
  if (!pts.length) return;
  const sheet = document.getElementById('walk-bottom-sheet');
  const side  = sheet && sheet.classList.contains('wbs-side') ? sheet.offsetWidth : 0;
  const peek  = sheet && sheet.classList.contains('wbs-peek') ? 62 : 0;   // = .wbs-peek translateY offset
  map.fitBounds(L.latLngBounds(pts), {
    paddingTopLeft:     [40, 80],               // clear of the top chips / ✕ Clear button
    paddingBottomRight: [40 + side, 40 + peek],
    maxZoom: 18,
  });
}

// Loaded saved walk buttons: shown only while a saved walk is open. "✎ Edit
// walk" (all pins shown + tap to select) replaced "Show all pins" and
// "◎ Select pins" — off = only the walk's own markers (Melvin, 20 Oct 2026).
function _syncWalkPinsBtn() {
  ['walk-saved-btn', 'walk-reverse-btn', 'walk-edit-btn', 'walk-reroute-btn', 'walk-tidy-btn'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = _savedWalkView ? '' : 'none';
  });
  const edit = document.getElementById('walk-edit-btn');
  if (edit) {
    edit.textContent = _walkPinSel ? '✓ Editing walk' : '✎ Edit walk';
    edit.style.background = _walkPinSel ? '#fde7d4' : '#fff';
  }
  // ⬚ Lasso: only while Edit walk is on (batch 15b).
  const lasso = document.getElementById('walk-lasso-btn');
  if (lasso) lasso.style.display = _walkPinSel ? '' : 'none';
  _syncWalkSaveBtn();
}

// Names rule (static/js/species-names.js formats): the common name for a species
// on the loaded walk — the walk API's names map (display_common_name on the
// server), else the culinary profile already fetched for the panel.
function _spCommonFor(sci, hint) {
  if (hint) return hint;
  const names = _savedWalkData && _savedWalkData.names;
  if (names && names[sci]) return names[sci];
  const sp = _activeWalkEnrich && _activeWalkEnrich[sci] && _activeWalkEnrich[sci].species;
  if (sp) return spPickCommon(sp.preferred_common_name, sp.common_names);
  return '';
}

// Loaded saved walk: take the line AS SHOWN from a server walk response
// (walk_route.shown_line — the circular / point-to-point view of the stored
// line): geometry, dashed legs, view flag and the distance/time for that shape.
// The stored line and its saved figures are never changed by the view.
function _applyShownLine(w) {
  const sh = w && w.shown;
  if (!sh || !Array.isArray(sh.coordinates) || sh.coordinates.length < 2) return false;
  _walkRouteGeom      = { type: 'LineString', coordinates: sh.coordinates };
  _walkStraightRanges = _walkStraightRangesOf({ straight_ranges: sh.straight_ranges }, sh.coordinates.length);
  _walkCircular       = !!sh.circular;
  _walkLineClosed     = !!sh.line_closed;
  _walkOrsDistM       = sh.distance_m || 0;
  _walkOrsDurMin      = sh.duration_min || 0;
  _syncWalkLoopUi();
  return true;
}

// The walk panel is showing the loaded saved walk itself (not a route rebuilt
// from a drawn area meanwhile) — saved-walk actions act on that row.
function _onSavedRoute(route) {
  return !!(_savedWalkView && _savedWalkData && _walkSaved && _walkSaved.id === _savedWalkData.id
            && _walkSavedNameFor(route) !== null);
}

// "← Saved walks" on a loaded walk: the panel's saved-walks list (the same view
// as Tools → Open a saved walk), scrolled into sight. Picking a walk there
// loads it; the current walk stays on the map until then.
function walkBackToSaved() {
  _wbsLoadSaved();
  const sec = document.getElementById('wbs-saved-walks-section');
  if (sec) sec.scrollIntoView({ block: 'start', behavior: 'smooth' });
}

// ── Loaded saved walk: route-proximity membership (walk_membership.py) ─────
// The server decides membership; this only draws it and sends the curator's
// actions (buffer, accept older, remove joined, renumber). "Human-confirmed
// only" is a per-walk display filter remembered in this browser — it changes
// what the panel, map, proximity alerts and Export summary show, never the walk.

const _walkHumanOnlyMem = {};   // fallback when localStorage is unavailable
let _walkOlderOpen = false;

function _walkHumanOnly(id, set) {
  const key = `foragingid_walk_human_only_${id}`;
  if (set !== undefined) {
    _walkHumanOnlyMem[id] = !!set;
    try { if (set) localStorage.setItem(key, '1'); else localStorage.removeItem(key); } catch (_) {}
  }
  try { return localStorage.getItem(key) === '1'; } catch (_) { return !!_walkHumanOnlyMem[id]; }
}

// Server stops → route entries (shape of _buildWalkRoute output + label/origin/spInfo).
function _savedWalkRoute() {
  const d = _savedWalkData;
  if (!d) return [];
  const humanOnly = _walkHumanOnly(d.id);
  const route = [];
  for (const st of d.stops) {
    if (st.is_note) {
      route.push({ lat: st.lat, lng: st.lng, pins: null, species: [], obs_ids: [],
                   label: st.label, origin: st.origin,
                   p: { species_primary: null, is_note: true, id: st.note_id != null ? st.note_id : null } });
      continue;
    }
    const sp = humanOnly ? st.species.filter(x => x.human) : st.species;
    // A stop left with no species under the filter (or a joined stop with
    // none) is dropped; labels keep every other stop's number unchanged.
    if (!sp.length && (humanOnly || st.origin === 'joined')) continue;
    const firstObs = (sp.length && sp[0].obs_ids.length) ? sp[0].obs_ids[0]
                   : (st.obs_ids.length ? st.obs_ids[0] : null);
    route.push({ lat: st.lat, lng: st.lng, pins: null,
                 species: sp.map(x => x.name), spInfo: sp,
                 obs_ids: st.obs_ids, joined_obs_ids: st.joined_obs_ids || [],
                 label: st.label, origin: st.origin, off_route_m: st.off_route_m || null,
                 p: { species_primary: sp.length ? sp[0].name : null, is_note: false, id: firstObs } });
  }
  return route;
}

function _renderWalkMembership() {
  _walkHighlightClear();            // ticks start empty on every render (list closed, accepted, refreshed)
  const el = document.getElementById('walk-membership');
  if (!el) return;
  const d = _savedWalkData;
  if (!d || !d.membership) { el.style.display = 'none'; el.innerHTML = ''; return; }
  const m = d.membership, rule = m.rule || {};
  const humanOnly = _walkHumanOnly(d.id);
  const nNew  = d.stops.reduce((a, st) => a + (st.joined_obs_ids || []).length, 0);
  const nAi   = new Set(d.stops.flatMap(st => st.species.filter(x => !x.human).map(x => x.name))).size;
  const since = rule.since ? String(rule.since).slice(0, 16) : '—';
  const cands = m.older_candidates || [];
  const btn   = 'font-size:0.7rem;padding:2px 8px;border-radius:5px;border:1px solid #b8d48a;background:#f0f4e8;color:#2d5016;cursor:pointer;font-family:inherit';
  el.style.display = 'block';
  el.innerHTML = `
    <div style="display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px">
      <label data-guest-hide title="Confirmed photos within this distance of the walk's line join it"
             style="display:flex;align-items:center;gap:5px;white-space:nowrap">
        Route buffer
        <input type="range" min="10" max="60" step="5" value="${Number(rule.buffer_m) || 25}"
               oninput="this.nextElementSibling.textContent = this.value + ' m'"
               onchange="walkSetBuffer(this.value)" style="width:80px;accent-color:#2d5016">
        <span style="min-width:34px">${Number(rule.buffer_m) || 25} m</span>
      </label>
      <label title="Hide species confirmed only by two identification services agreeing (AI-agreed)"
             style="display:flex;align-items:center;gap:4px;white-space:nowrap;cursor:pointer">
        <input type="checkbox" ${humanOnly ? 'checked' : ''} onchange="walkToggleHumanOnly(this.checked)">
        Human-confirmed only
      </label>
      <button data-guest-hide onclick="walkRenumber()" style="${btn}"
              title="Make the current stops (including 7a-style new ones) the saved walk, numbered 1–N">Renumber stops</button>
    </div>
    <div style="margin-top:3px;color:#777">
      ${nNew} photo${nNew !== 1 ? 's' : ''} joined since ${_esc(since)}${nAi ? ` · ${nAi} AI-agreed species` : ''}
    </div>
    ${cands.length ? `
    <div data-guest-hide style="margin-top:5px">
      <button onclick="walkToggleOlderList()" style="${btn}">
        Older photos near this route: ${cands.length} species ${_walkOlderOpen ? '▾' : '▸'}</button>
      <div id="walk-older-list" style="display:${_walkOlderOpen ? 'block' : 'none'};margin-top:4px;max-height:220px;overflow-y:auto">
        ${cands.map(c => `
          <label style="display:flex;align-items:baseline;gap:5px;padding:2px 0;cursor:pointer">
            <input type="checkbox" class="walk-older-cb" value="${c.obs_ids.map(Number).join(',')}" onchange="walkOlderHighlight()">
            <span style="color:#2d5016">${spNameHtml(c.species, _spCommonFor(c.species))}</span>
            <span style="color:#999">${c.n} photo${c.n !== 1 ? 's' : ''} · ${Number(c.nearest_m)} m${c.human ? '' : ' · AI-agreed'}</span>
          </label>`).join('')}
        <div style="display:flex;gap:6px;margin-top:4px">
          <button onclick="walkAcceptOlder(false)" style="${btn}">Accept selected</button>
          <button onclick="walkAcceptOlder(true)"  style="${btn}">Accept all</button>
        </div>
      </div>
    </div>` : ''}`;
}

// Redraw from a server walk response (GET shape) without re-fitting the map.
async function _refreshSavedWalk(w) {
  if (!_savedWalkView || !w || !Array.isArray(w.stops)) return;   // walk was cleared meanwhile
  _savedWalkData = { id: w.id, name: w.name, stops: w.stops, membership: w.membership || null,
                     names: w.names || (_savedWalkData && _savedWalkData.names) || {} };
  // A response that carries the line as shown (reorder: reversed / rotated;
  // loop: circular / point-to-point) replaces the drawn one, its dashed legs,
  // the view flag and the distance/time for that shape — set BEFORE the
  // signature below, so the title keeps the walk's name.
  _applyShownLine(w);
  const route = _savedWalkRoute();
  _walkTidySeq++;                // a build still waiting for its stop order is dropped
  _activeWalkRoute = route;
  _walkSelected    = route;
  _walkSaved       = { id: w.id, name: w.name, sig: _walkRouteSig(route) };
  _drawWalkLayer(true);
  const need = [...new Set(route.flatMap(_stopSpecies))].filter(n => !(_activeWalkEnrich && _activeWalkEnrich[n]));
  if (need.length) {
    const more = await _fetchWalkEnrich(need);
    if (!_savedWalkView) return;
    _activeWalkEnrich = Object.assign(_activeWalkEnrich || {}, more);
  }
  renderWalkPanel(route, _activeWalkEnrich || {});
  _renderWalkMembership();
}

async function _walkMembershipCall(path, method, body) {
  const d = _savedWalkData;
  if (!d) return null;
  try {
    const r = await fetch(`/api/walk/saves/${d.id}/${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body ? JSON.stringify(body) : undefined,
    });
    const out = await r.json().catch(() => ({}));
    if (!r.ok) {
      const det = out.detail;
      throw new Error(det ? (typeof det === 'string' ? det : JSON.stringify(det)) : `HTTP ${r.status}`);
    }
    await _refreshSavedWalk(out);
    return out;
  } catch (e) {
    alert('Walk update failed: ' + e.message);
    return null;
  }
}

function walkToggleHumanOnly(on) {
  if (!_savedWalkData) return;
  _walkHumanOnly(_savedWalkData.id, !!on);
  _refreshSavedWalk(Object.assign({}, _savedWalkData));
}

function walkSetBuffer(v) {
  _walkMembershipCall('membership', 'PATCH', { buffer_m: Number(v) });
}

function walkToggleOlderList() {
  _walkOlderOpen = !_walkOlderOpen;
  _renderWalkMembership();          // re-render clears the tick highlights
}

function walkAcceptOlder(all) {
  const boxes = [...document.querySelectorAll('#walk-older-list .walk-older-cb')]
    .filter(cb => all || cb.checked);
  const ids = boxes.flatMap(cb => cb.value.split(',').map(Number).filter(Boolean));
  if (!ids.length) { alert('Tick at least one species first.'); return; }
  if (!confirm(`Add ${boxes.length} species (${ids.length} older photo${ids.length !== 1 ? 's' : ''}) to this walk?`)) return;
  _walkMembershipCall('accept', 'POST', { obs_ids: ids });
}

function walkExcludeJoined(ids) {
  if (!ids || !ids.length) return;
  if (!confirm(`Remove ${ids.length} new photo${ids.length !== 1 ? 's' : ''} of this species from the walk?`)) return;
  _walkMembershipCall('exclude', 'POST', { obs_ids: ids });
}

// ── Older-photos list: ticked species light up their pins ──────────────────
// Rings on their own layer (above every pin, shown even while other pins are
// hidden), positions from the server's older_candidates[].points. Cleared when
// the list closes or re-renders, another walk loads, or walk mode exits.
var _walkHiLayer = null;       // var: read by _exitWalkMode / loadSavedWalk, declared below them

function _walkHighlightClear() {
  if (_walkHiLayer) { map.removeLayer(_walkHiLayer); _walkHiLayer = null; }
}

function walkOlderHighlight() {
  _walkHighlightClear();
  const cands = (_savedWalkData && _savedWalkData.membership && _savedWalkData.membership.older_candidates) || [];
  const ticked = new Set([...document.querySelectorAll('#walk-older-list .walk-older-cb')]
    .filter(cb => cb.checked).map(cb => cb.value));
  const pts = cands.filter(c => ticked.has(c.obs_ids.map(Number).join(','))).flatMap(c => c.points || []);
  if (!pts.length) return;
  const icon = L.divIcon({ className: '', iconSize: [26, 26], iconAnchor: [13, 13],
    html: '<div style="width:26px;height:26px;border-radius:50%;border:3px solid #ea580c;box-shadow:0 0 0 2px #fff,0 1px 4px rgba(0,0,0,.4);box-sizing:border-box"></div>' });
  _walkHiLayer = L.layerGroup(pts.map(([lat, lng]) =>
    L.marker([lat, lng], { icon, interactive: false, zIndexOffset: 2000 }))).addTo(map);
}

// ── "✎ Edit walk" (loaded saved walk, curator) — was "Select pins" ──────────
// A tap toggles a pin's selection instead of opening its card. Pins already
// on the walk are drawn differently from the rest. The bar adds the selection
// (accept path — any distance; it becomes a side-stop exactly as a joined
// photo does) or removes it (exclude path; saved stops stay on the line).
// No ORS call; the line, distance and time never change. Leaving the mode
// clears the selection and restores the pins-hidden setting.
var _walkPinSel = null;          // {} while "✎ Edit walk" is on (var: renderMarkers reads it)
// Pending marks — kept when Edit walk is switched off (so "Save changes (N)"
// still saves them); dropped only on Save, loading another walk, or leaving
// walk mode (Melvin 20 Oct 2026: a discard on leaving edit mode lost his marks).
var _walkPending = { add: new Set(), remove: new Set() };

function _walkPendingClear() {
  _walkPending.add.clear();
  _walkPending.remove.clear();
}

function _walkMemberSet() {
  return new Set(((_savedWalkData && _savedWalkData.membership && _savedWalkData.membership.member_obs_ids) || []).map(Number));
}

// Pin icon in select mode: on the walk = solid green ring, not on it = grey
// hollow ring; selected = thick orange ring. Same touch target as other pins.
// Pin icon in Edit walk: on the walk = green ring, not on it = grey ring;
// pending add = green "+" disc, pending remove = red "−" disc. Same touch target.
function _walkSelIcon(id, category, members) {
  const vis   = _PIN_VIS;
  const touch = isMobile() ? 44 : vis + 12;
  const add   = _walkPending.add.has(id);
  const rem   = _walkPending.remove.has(id);
  const mem   = members.has(id);
  if (add || rem) {
    const d = 20, bg = add ? '#16a34a' : '#dc2626';
    const disc = `<div style="width:${d}px;height:${d}px;border-radius:50%;background:${bg};border:2px solid #fff;`
      + `box-shadow:0 0 0 2px ${bg},0 1px 4px rgba(0,0,0,.4);color:#fff;font:700 15px/1 sans-serif;`
      + `display:flex;align-items:center;justify-content:center">${add ? '+' : '−'}</div>`;
    const html = `<div style="width:${touch}px;height:${touch}px;display:flex;align-items:center;justify-content:center">${disc}</div>`;
    return L.divIcon({ className: '', html, iconSize: [touch, touch], iconAnchor: [touch / 2, touch / 2] });
  }
  const { fill } = _pinColor(category);
  const style = mem ? `background:${fill};border:2px solid white;box-shadow:0 0 0 3px #2d5016,0 1px 4px rgba(0,0,0,.35)`
              :       `background:#fff;border:3px solid #9ca3af;box-shadow:0 1px 3px rgba(0,0,0,.3)`;
  return L.divIcon({ className: '', html: _pinHtml(vis, style, touch), iconSize: [touch, touch], iconAnchor: [touch / 2, touch / 2] });
}

function walkToggleEdit() {
  if (_walkPinSel) { _walkPinSelExit(); return; }
  if (!_savedWalkView || !_onSavedRoute(_activeWalkRoute)) return;
  _walkPinSel = {};                          // marks go to _walkPending — nothing written until Save changes
  _savedWalkView.hidePins = false;           // every pin is selectable
  _applyLayer();
  renderMarkers();
  _drawWalkLayer(true);                      // stop markers: marked-stop rings + tap to mark (batch 15b)
  _syncWalkPinsBtn();
}

// Leave Edit walk: back to the walk's own markers only. Pending marks are KEPT
// (Save changes still shows and saves them); loading another walk or leaving
// walk mode drops them (_walkPendingClear).
function _walkPinSelExit() {
  if (!_walkPinSel) return;
  if (_lassoActive) _exitLassoSelect();       // an Edit-walk lasso ends with Edit walk
  _walkPinSel = null;
  if (_savedWalkView) _savedWalkView.hidePins = true;
  _applyLayer();
  renderMarkers();
  // Drop the Edit-walk stop rings (batch 15b) — only while the walk layer is on
  // the map: _exitWalkMode removes it first and must not get it back.
  if (_walkRouteLayer && _activeWalkRoute) _drawWalkLayer(true);
  _syncWalkPinsBtn();
}

// Tap in Edit walk: a pin not on the walk → pending add; on the walk →
// pending remove; tap again → unmarked. Nothing is written until Save changes.
function _walkPinToggle(p) {
  if (!_walkPinSel || p.id == null) return;
  const id = Number(p.id);
  const set = _walkMemberSet().has(id) ? _walkPending.remove : _walkPending.add;
  if (set.has(id)) set.delete(id); else set.add(id);
  _syncWalkSaveBtn();          // first — the count must update even if a redraw fails
  renderMarkers();
}

// Tap a numbered stop in Edit walk (batch 15b): every photo at the stop is
// marked for removal; tap again → unmarked. A stop is only ever removed (its
// photos are on the walk). Pending until Save changes, like pin marks.
function _walkStopIds(stop) {
  return [...new Set([...(stop.obs_ids || []), ...(stop.joined_obs_ids || [])].map(Number))];
}
function _walkStopMarked(stop) {
  const ids = _walkStopIds(stop);
  return ids.length > 0 && ids.every(id => _walkPending.remove.has(id));
}
function _walkStopToggle(stop) {
  if (!_walkPinSel || !stop || (stop.p && stop.p.is_note)) return;
  const ids = _walkStopIds(stop);
  if (!ids.length) return;
  if (_walkStopMarked(stop)) ids.forEach(id => _walkPending.remove.delete(id));
  else ids.forEach(id => { _walkPending.add.delete(id); _walkPending.remove.add(id); });
  _syncWalkSaveBtn();          // first — the count must update even if a redraw fails
  renderMarkers();
  // Redraw the stop markers (marked ring) after this click has finished.
  setTimeout(() => { if (_walkRouteLayer) _drawWalkLayer(true); }, 0);
}

// Lasso in Edit walk (batch 15b): each pin inside the box toggles exactly as a
// tap does (_walkPinToggle's rule) — not on the walk → pending add, on it →
// pending remove, already marked → unmarked. Returns how many pins changed.
function _walkLassoToggle(pins) {
  const members = _walkMemberSet();
  let n = 0;
  for (const p of pins) {
    if (p.id == null) continue;
    const id = Number(p.id);
    const set = members.has(id) ? _walkPending.remove : _walkPending.add;
    if (set.has(id)) set.delete(id); else set.add(id);
    n++;
  }
  _syncWalkSaveBtn();
  return n;
}

function _walkPendingCount() {
  return _walkPending.add.size + _walkPending.remove.size;
}

// The panel's save button. Loaded saved walk → "Save changes (N)": commits the
// pending marks to THIS walk (never prompts for a name, never makes a copy),
// disabled when nothing is pending. New, unsaved walks → "Save walk" as before.
function _syncWalkSaveBtn() {
  const btn = document.getElementById('walk-save-btn');
  if (!btn || _walkSaving) return;
  if (_savedWalkView && _onSavedRoute(_activeWalkRoute)) {
    const n = _walkPendingCount();
    btn.textContent = n ? `💾 Save changes (${n})` : '💾 Save changes';
    btn.disabled = !n;
    btn.title = n ? `${_walkPending.add.size} to add · ${_walkPending.remove.size} to remove`
                  : 'Turn on ✎ Edit walk and tap pins to add or remove them';
  } else if (btn.textContent.startsWith('💾 Save changes')) {
    btn.textContent = '💾 Save walk';
    btn.disabled = false;
    btn.title = '';
  }
}

function walkSaveClick() {
  if (_savedWalkView && _onSavedRoute(_activeWalkRoute)) { walkSaveChanges(); return; }
  promptSaveWalk();
}

// Commit: pending adds → accept path, pending removes → exclude path (each
// read back by id on the server). The result is checked against the returned
// members before the marks are cleared; the outcome goes to the status line.
async function walkSaveChanges() {
  if (_walkSaving) return;
  const adds = [..._walkPending.add], rems = [..._walkPending.remove];
  if (!adds.length && !rems.length) {
    _showWalkSaveStatus('Nothing to save — turn on ✎ Edit walk and tap pins to mark them', false);
    return;
  }
  _walkSaving = true;
  const btn = document.getElementById('walk-save-btn');
  if (btn) { btn.disabled = true; btn.textContent = '💾 Saving…'; }
  const notes = [], why = {};
  const tally = o => (o.skipped || []).forEach(k => { const r = k.reason.replace(/ \(.*\)$/, ''); why[r] = (why[r] || 0) + 1; });
  let out = null, ok = true;
  try {
    if (adds.length) { out = await _walkMembershipCall('accept', 'POST', { obs_ids: adds }); if (out) tally(out); else ok = false; }
    if (ok && rems.length) { out = await _walkMembershipCall('exclude', 'POST', { obs_ids: rems }); if (out) tally(out); else ok = false; }
    if (ok && out) {
      const mem = new Set((out.membership.member_obs_ids || []).map(Number));
      notes.push(`${adds.filter(id => mem.has(id)).length} added`, `${rems.filter(id => !mem.has(id)).length} removed`);
      Object.entries(why).forEach(([r, n]) => notes.push(`${n} ${r} — skipped`));
      _walkPendingClear();
      _showWalkSaveStatus('Saved changes: ' + notes.join(' · '), true);
      // New stops are side-stops until the line goes through them, and a stop
      // left with no species is dropped by a re-route (batch 15b): go straight
      // on to the Re-route preview (same dialog as ↻ Re-route — cancel keeps
      // them as they are; an empty stop then stays hidden).
      const _emptied = (_activeWalkRoute || []).some(_walkStopEmpty);
      if (adds.some(id => mem.has(id)) || _emptied) setTimeout(walkReroute, 0);
    } else {
      _showWalkSaveStatus('Changes not saved — they are still marked; try Save changes again', false);
    }
  } catch (e) {
    _showWalkSaveStatus('Save changes failed: ' + e.message, false);
  } finally {
    _walkSaving = false;
    _syncWalkSaveBtn();
    try { renderMarkers(); } catch (_) {}
  }
}

// "⤳ Tidy route order" (walk.py tidy_walk / walk_route.tidy_order): the saved
// stops in an order with no crossing legs (2-opt from the current order, stop 1
// first). Dry run shown first; on OK the server snapshots, routes only the new
// legs (stored legs are kept, also when walked backwards), refuses if the
// walk's members would change, then writes and reads back.
async function walkTidyOrder() {
  const d = _savedWalkData;
  if (!d) return;
  let t;
  try {
    const r = await fetch(`/api/walk/saves/${d.id}/tidy`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ confirm: false }),
    });
    t = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(typeof t.detail === 'string' ? t.detail : `HTTP ${r.status}`);
  } catch (e) {
    alert('Tidy route order: ' + e.message);
    return;
  }
  const km = m => (m / 1000).toFixed(1) + ' km';
  const lines = [
    `Tidy the stop order of "${d.name}"?`, '',
    `Crossing legs: ${t.crossings_before} → ${t.crossings_after}`,
    `Distance: ${km(t.distance_before_m)} now → about ${km(t.estimated_distance_m)} (new legs counted straight; ORS paths can add a little)`,
    `Legs changed (${t.legs_changed.length}, old stop numbers): ${t.legs_changed.join(', ')}`,
    `Legs kept as stored: ${t.legs_kept}${t.legs_kept_reversed ? ` (${t.legs_kept_reversed} walked the other way)` : ''} · ORS requests: ${t.ors_requests}`,
    '', 'Same stops and members; stop 1 stays first. Stops are renumbered in the new order.',
    'A database snapshot is taken first. Refused if the new line would change the walk\'s members.',
    'Printed sheets and published pages will no longer match until reprinted / republished.',
  ];
  if (!confirm(lines.join('\n'))) return;
  const out = await _walkMembershipCall('tidy', 'POST', { confirm: true });
  if (!out || !out.tidy) return;
  const tt = out.tidy;
  _fitSavedWalk();
  alert(`Tidied: ${km(tt.distance_before_m)} → ${km(tt.distance_m)}, ${tt.duration_min} min. `
    + `Crossing legs ${tt.crossings_before} → ${tt.crossings_after}.\n\nSnapshot: ${String(tt.snapshot || '').split('/').pop()}`);
}

// "↻ Re-route" (walk.py reroute_walk / walk_route.plan_reroute): dry run first,
// shown in a confirm dialog; only then the server snapshots the DB, routes the
// CHANGED legs via ORS (kept legs and their dashes stay exactly as stored) and
// writes. The current stops — side-stops included, empty saved stops dropped —
// become stops 1..N; distance and time are recalculated.
// startLabel (batch 15b, "Start here" on an open line): that saved stop
// becomes stop 1 — k…N, then back k−1…1; only the new leg N → k−1 is routed.
async function walkReroute(startLabel) {
  const d = _savedWalkData;
  if (!d || !_onSavedRoute(_activeWalkRoute)) return;
  const start = typeof startLabel === 'string' ? startLabel : null;
  let plan;
  try {
    const r = await fetch(`/api/walk/saves/${d.id}/reroute`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm: false, start_label: start }),
    });
    plan = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(plan.detail || `HTTP ${r.status}`);
  } catch (e) {
    alert('Re-route: ' + e.message);
    return;
  }
  const lines = [
    start ? `Start "${d.name}" at stop ${start}? It walks on to the last stop, then back the other way to stop 1.`
          : `Re-route "${d.name}" through its current stops?`, '',
    `Stops: ${plan.stops_before} now → ${plan.stops_after}, numbered 1–${plan.stops_after}`,
    plan.added_stops.length   ? `New stops kept: ${plan.added_stops.join(', ')}` : '',
    plan.dropped_stops.length ? `Dropped (no species left): ${plan.dropped_stops.join(', ')}` : '',
    `Legs kept exactly as they are (dashed legs stay dashed): ${plan.legs_kept}`,
    `Legs routed by ORS: ${plan.legs_to_route.join(', ') || 'none'} (${plan.ors_requests} request${plan.ors_requests === 1 ? '' : 's'})`,
    '', 'A database snapshot is taken first. Distance and time are recalculated.',
    'Printed sheets and published pages will no longer match until reprinted / republished.',
  ].filter((x, k) => x || k === 1 || k === 7);
  if (!confirm(lines.join('\n'))) return;
  const out = await _walkMembershipCall('reroute', 'POST', { confirm: true, start_label: start });
  if (!out || !out.reroute) return;
  const rr = out.reroute;
  const straight = (rr.legs || []).filter(l => l.kind === 'straight');
  _fitSavedWalk();
  alert(`Re-routed: ${Math.round(rr.distance_before_m)} m / ${rr.duration_before_min} min → ${rr.distance_m} m / ${rr.duration_min} min.`
    + (straight.length ? `\n\nKept straight (dashed) — ORS detoured: ${straight.map(l => `${l.leg} (${l.routed_m} m routed)`).join(', ')}` : '')
    + ((rr.newly_joined || []).length ? `\n\nJoined along the new legs (route proximity): ${rr.newly_joined.map(x => `${spNameText(x.species, _spCommonFor(x.species))} at ${x.stop}`).join(', ')} — remove with ✎ Edit walk if not wanted.` : '')
    + `\n\nSnapshot: ${String(rr.snapshot || '').split('/').pop()}`);
}

// "Start here" (mode 'start': same direction) and "⇄ Reverse" (mode 'reverse':
// circular keeps stop 1, the rest runs the other way) — walk_route.py on the
// server rotates / reverses the saved line: no ORS call, distance unchanged,
// stops renumbered. No confirm step (Melvin, 20 Oct 2026).
function walkReorder(mode, label) {
  _walkMembershipCall('reorder', 'POST', { mode, stop_label: label || null });
}

// "Start here" on any saved stop (batch 15b): a closed stored line is rotated
// (walkReorder 'start' — same line, no ORS); an open one is re-planned through
// the Re-route preview (k…N, then back k−1…1).
function walkStartHere(label) {
  if (_walkLineClosed) walkReorder('start', label);
  else walkReroute(label);
}

function walkRenumber() {
  if (!confirm('Renumber stops?\n\nNew stops (7a, 7b…) become part of the saved walk and every stop is numbered 1–N in route order. Printed sheets and published pages will no longer match until reprinted / republished.')) return;
  _walkMembershipCall('renumber', 'POST', null);
}

async function deleteSavedWalk(id) {
  if (!confirm('Delete this saved walk?')) return;
  try {
    const r = await fetch(`/api/walk/saves/${id}`, { method: 'DELETE' });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.detail || `HTTP ${r.status}`);   // 409 names the published slug
    }
    if (_walkSaved && _walkSaved.id === id) {
      _walkSaved = null;          // the shown walk is no longer saved — title back to stop count
      _walkRefreshTitles();
    }
    loadSavedWalksList();
  } catch (e) {
    alert('Delete failed: ' + e.message);
  }
}

// ── Walk summary export ────────────────────────────────────────────────────

async function exportWalkSummary() {
  if (!_activeWalkRoute || !_activeWalkRoute.length) {
    alert('No walk route to export. Draw a selection area first.');
    return;
  }
  const btn = document.getElementById('walk-export-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Generating…'; }

  const _season = _currentSeason();
  const _sIcon  = { spring: '🌱', summer: '☀️', autumn: '🍂', winter: '❄️', 'year-round': '🔄' };

  // Build total distance
  let totalM = 0;
  for (let i = 1; i < _activeWalkRoute.length; i++) {
    totalM += _haversineM(
      _activeWalkRoute[i-1].lat, _activeWalkRoute[i-1].lng,
      _activeWalkRoute[i].lat,   _activeWalkRoute[i].lng
    );
  }

  // Build stops payload — EVERY species at each stop (_stopSpecies), each
  // through the toxic guard. Blocked species are still listed, with no
  // culinary/recipe/edibility content, only the warning (rendered as the badge
  // by /api/sharing/export-walk).
  // A species already listed at an earlier stop becomes a compact "also here"
  // line (with its ☠ warning if blocked) instead of a second full block.
  const _repeatSplit = _walkRepeatSplit(_activeWalkRoute);   // shared with the walk panel
  const _dishesShown = new Set();   // summary-wide: the same dish is never shown twice
  const stops = _activeWalkRoute.map((stop, i) => {
    const { p, lat, lng } = stop;
    const distFromPrev = i === 0 ? null
      : _haversineM(
          _activeWalkRoute[i-1].lat, _activeWalkRoute[i-1].lng,
          lat, lng
        );
    const label = _repeatSplit[i].label;
    const names = _repeatSplit[i].full;
    const also_here = _repeatSplit[i].repeats.map(rp => {
      const ed = _activeWalkEnrich?.[rp.name];
      const gate = _culinaryGate(ed ? ed._safety : null);
      return { species_scientific: rp.name, species_common: _spCommonFor(rp.name) || null,
               first_label: rp.first_label, toxicity_warning: gate.ok ? null : (gate.label || null) };
    });
    const species = names.map(spName => {
      const ed = _activeWalkEnrich?.[spName];
      const gate = _culinaryGate(ed ? ed._safety : null);
      // Outgoing surface (batch 6): a caution species without a curator-authored
      // warning sends no culinary content. The server re-checks (apply_walk_safety)
      // and adds the warnings from the DB.
      const _hOk = SafetyGate.handoutAllowed(gate.safety);
      const ci = _hOk ? (ed?.culinary || null) : null;
      const spData = ed?.species || null;
      const recipes = _hOk ? (ed?.recipes || []) : [];
      const picked = _summaryRecipe(recipes, _dishesShown);
      // Pin props for this species (new walks); loaded walks have no pins.
      const pinP = (stop.pins || []).map(x => x.p).find(pp => pp.species_primary === spName)
                   || (spName === p.species_primary ? p : {});
      const allCommon = (pinP.common_names && pinP.common_names.length) ? pinP.common_names
                      : (spData?.common_names || []);
      return {
        species_scientific: spName,
        species_common: allCommon[0] || null,
        all_common: allCommon,
        edibility: (gate.ok || !gate.label) ? (spData?.edibility_status || pinP.edibility_status || null) : null,
        toxicity_warning: gate.ok ? null : (gate.label || null),
        culinary_notes: ci ? (ci.edible_parts || ci.taste_notes || ci.preparation_methods || null) : null,
        recipe_title: picked ? (_recipeTitle(picked) || null) : null,
        recipe_body:  picked ? (picked.body  || null) : null,
        recipe_season: picked ? picked.season : null,
        is_medicinal_prep: picked ? !!picked.is_medicinal_prep : null,
      };
    });
    return {
      num: i + 1,
      label,                        // "7a" for joined stops; rendered by export-walk when present
      dist_from_prev: distFromPrev,
      note_text: p.is_note ? (p.text || '') : null,
      species,
      also_here,
    };
  });

  try {
    const r = await fetch('/api/sharing/export-walk', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        // An empty saved stop (no species left) is hidden here as on the panel (batch 15b).
        stops: stops.filter((_, i) => !_walkStopEmpty(_activeWalkRoute[i])),
        // Same distance the panel shows: the routed/saved distance when there
        // is one, else the straight-line sum between stops.
        total_distance_m: _walkOrsDistM > 0 ? _walkOrsDistM : totalM,
        season: _season,
        // Saved walk name while the route still matches it; else the server default.
        title: _walkSavedNameFor(_activeWalkRoute) || null,
      }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      throw new Error(d.detail || `HTTP ${r.status}`);
    }
    const html = await r.text();
    // Open in new tab
    const blob = new Blob([html], { type: 'text/html' });
    const url  = URL.createObjectURL(blob);
    window.open(url, '_blank');
  } catch (e) {
    alert('Export failed: ' + e.message);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '📋 Export summary'; }
  }
}

