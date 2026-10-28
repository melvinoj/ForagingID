// ── Pin icons ─────────────────────────────────────────────────────────────

// ── Shared pin geometry — matches note pin (amber circle reference) ───────
// All observation pins: 16px visible circle, 2px white border, same shadow.
// Mobile: transparent 44px touch area wraps the visible circle.
const _PIN_VIS = 16;  // visible dot diameter — matches makeNoteIcon default

function _pinHtml(visSize, style, touchSize) {
  const dot = `<div style="width:${visSize}px;height:${visSize}px;border-radius:50%;${style}"></div>`;
  if (touchSize > visSize) {
    return `<div style="width:${touchSize}px;height:${touchSize}px;display:flex;align-items:center;justify-content:center;">${dot}</div>`;
  }
  return dot;
}

// Category → fill and ring colours for pins.
// plant=green, fungi=amber, landscape=blue
function _pinColor(category) {
  const cat = (category || 'plant').toLowerCase();
  if (cat === 'landscape') return { fill: '#3b82f6', ring: '#2563eb' };
  if (cat === 'fungi')     return { fill: '#f59e0b', ring: '#d97706' };
  return                          { fill: '#2d8016', ring: '#4a8c3f' };  // plant (default)
}

function makeIcon(hasEnrichment, isHighlighted, category) {
  const vis   = _PIN_VIS;
  const touch = isMobile() ? 44 : vis;
  const off   = touch / 2;
  const { fill, ring } = _pinColor(category);
  let style;
  if (isHighlighted) {
    style = `background:${fill};border:2px solid white;box-shadow:0 0 0 4px ${fill}59,0 1px 4px rgba(0,0,0,.35)`;
  } else if (hasEnrichment) {
    style = `background:${fill};border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.35)`;
  } else {
    // Hollow ring — confirmed, enrichment pending
    style = `background:white;border:2px solid ${ring};box-shadow:0 1px 4px rgba(0,0,0,.25)`;
  }
  return L.divIcon({
    className: '',
    html:      _pinHtml(vis, style, touch),
    iconSize:   [touch, touch],
    iconAnchor: [off, off],
  });
}

function makeHighlightIcon(category) {
  // Slightly larger than base to maintain visual hierarchy; pulsing ring
  const vis   = _PIN_VIS + 4;  // 20px
  const touch = isMobile() ? 44 : vis;
  const off   = touch / 2;
  const { fill } = _pinColor(category);
  const style = `background:${fill};border:2px solid white;box-shadow:0 1px 8px ${fill}99`;
  const dot = `<div class="pin-pulse" style="width:${vis}px;height:${vis}px;border-radius:50%;${style}"></div>`;
  const html = touch > vis
    ? `<div style="width:${touch}px;height:${touch}px;display:flex;align-items:center;justify-content:center;">${dot}</div>`
    : dot;
  return L.divIcon({ className:'', html, iconSize:[touch,touch], iconAnchor:[off,off] });
}

function makeSelectedIcon() {
  // Amber — selected state, larger than base for clear hierarchy
  const vis   = _PIN_VIS + 4;  // 20px
  const touch = isMobile() ? 52 : vis;
  const off   = touch / 2;
  const style = `background:#e07b20;border:2px solid white;box-shadow:0 2px 10px rgba(0,0,0,.45),0 0 0 4px rgba(224,123,32,.35)`;
  const dot = `<div style="width:${vis}px;height:${vis}px;border-radius:50%;${style}"></div>`;
  const html = touch > vis
    ? `<div style="width:${touch}px;height:${touch}px;display:flex;align-items:center;justify-content:center;">${dot}</div>`
    : dot;
  return L.divIcon({ className:'', html, iconSize:[touch,touch], iconAnchor:[off,off] });
}

// Pins layer — same visual as cluster layer (both use _PIN_VIS circle)
function makePinDotIcon(isHighlighted, category) {
  if (isHighlighted) return makeHighlightIcon(category);
  const vis   = _PIN_VIS;
  const touch = isMobile() ? 44 : vis;
  const off   = touch / 2;
  const { fill } = _pinColor(category);
  const style = `background:${fill};border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.35)`;
  return L.divIcon({
    className: '',
    html:      _pinHtml(vis, style, touch),
    iconSize:   [touch, touch],
    iconAnchor: [off, off],
  });
}

// Green ring — pin whose species is in the current /lists selection (select mode).
function makeSelectRingIcon(category) {
  const vis   = _PIN_VIS;
  const touch = isMobile() ? 44 : vis + 8;
  const off   = touch / 2;
  const { fill } = _pinColor(category);
  const style = `background:${fill};border:2px solid white;box-shadow:0 0 0 4px rgba(45,128,22,.95),0 1px 4px rgba(0,0,0,.35)`;
  return L.divIcon({
    className: '',
    html:      _pinHtml(vis, style, touch),
    iconSize:   [touch, touch],
    iconAnchor: [off, off],
  });
}

let highlightedMarkerId = null;
let _highlightTimer     = null;

// ── Map select mode (reach-back from /lists) ───────────────────────────────
let _selectMode = false;

function _initSelectMode() {
  if (new URLSearchParams(location.search).get('select') !== '1') return;
  _selectMode = true;
  document.body.classList.add('select-mode');
  const bar = document.getElementById('select-bar');
  if (bar) bar.style.display = 'flex';
  setLayer('pins');                 // pins are tappable; heatmap is not
  _updateSelectCount();
}

function _updateSelectCount() {
  const el = document.getElementById('sb-count');
  if (el) el.textContent = ForagingList.count();
}

function _selectModeToggle(p) {
  if (!p || !p.species_primary) return;
  ForagingList.toggle(p.species_primary);
  _updateSelectCount();
  renderMarkers();                  // refresh green rings
}

const _MAP_SNAP_KEY = 'foragingid_list_map_snapshot';

function finishSelectMode() {
  _exitLassoSelect();
  // Capture the exact viewport at current zoom using the active base layer.
  try {
    const z = map.getZoom();
    const n = 1 << z;
    const c = map.getCenter();

    // Build tile URL for the active base layer.
    function _tileUrl(tz, tx, ty) {
      const layer = _baseLayers[_currentBaseLayerKey];
      if (!layer || !layer._url) return `https://tile.openstreetmap.org/${tz}/${tx}/${ty}.png`;
      const subs = layer.options && layer.options.subdomains || 'abc';
      const s = typeof subs === 'string' ? subs[0] : subs[0];
      return layer._url.replace('{s}', s).replace('{z}', tz).replace('{x}', tx).replace('{y}', ty);
    }

    function _latToTileY(lat) {
      const ry = Math.log(Math.tan(lat * Math.PI / 180) + 1 / Math.cos(lat * Math.PI / 180));
      return Math.floor((1 - ry / Math.PI) / 2 * n);
    }

    // Tile range covering the visible viewport, capped at ±5 from centre.
    const b = map.getBounds();
    const cx = Math.floor((c.lng + 180) / 360 * n);
    const cy = _latToTileY(c.lat);
    const CAP = 5;
    const minTx = Math.max(Math.floor((b.getWest()  + 180) / 360 * n), cx - CAP);
    const maxTx = Math.min(Math.floor((b.getEast()  + 180) / 360 * n), cx + CAP);
    const minTy = Math.max(_latToTileY(b.getNorth()), cy - CAP);
    const maxTy = Math.min(_latToTileY(b.getSouth()), cy + CAP);
    const cols  = maxTx - minTx + 1;

    const tiles = [];
    for (let ty = minTy; ty <= maxTy; ty++)
      for (let tx = minTx; tx <= maxTx; tx++)
        tiles.push(_tileUrl(z, Math.max(0, tx), Math.max(0, ty)));

    // Raw lat/lng of selected pins — reprojected at render time.
    const selectedSet = new Set(ForagingList.species());
    const rawPins = [];
    for (const f of allFeatures) {
      const p = f.properties;
      if (!p.species_primary || !selectedSet.has(p.species_primary)) continue;
      const [lng, lat] = f.geometry.coordinates;
      rawPins.push([lat, lng]);
    }

    localStorage.setItem(_MAP_SNAP_KEY, JSON.stringify({
      tiles, cols, rawPins,
      center: { lat: c.lat, lng: c.lng }, snapZoom: z,
      minTx, minTy,
      date: new Date().toISOString(),
    }));
  } catch (_) {}
  location.href = '/lists';
}

// ── Select all visible ────────────────────────────────────────────────────
// Adds every pin in the current viewport that passes active filters.
function selectAllVisible() {
  // Exit lasso mode if active so the two selection tools are mutually exclusive
  if (_lassoActive) _exitLassoSelect();
  let added = 0;
  for (const f of allFeatures) {
    const p = f.properties;
    if (!p.species_primary || !_passesFilters(p)) continue;
    if (!ForagingList.has(p.species_primary)) {
      ForagingList.add(p.species_primary);
      added++;
    }
  }
  _updateSelectCount();
  renderMarkers();
  if (added > 0) _showLocateToast(`${added} species added`);
  else           _showLocateToast('All visible species already selected');
}

// ── Lasso select ──────────────────────────────────────────────────────────
// Rectangle draw mode: drag on the map to select all pins in the drawn area.
// Uses its own event handlers so it doesn't conflict with walk-mode drawing.

let _lassoActive  = false;
let _lassoDrawing = false;
let _lassoDragStart = null;

function toggleLassoSelect() {
  if (_lassoActive) _exitLassoSelect();
  else              _enterLassoSelect();
}

function _lassoKeyDown(e) {
  if (e.key === 'Escape' && _lassoActive) { _hideLassoRect(); _exitLassoSelect(); }
}
function _lassoDocClick(e) {
  if (!_lassoActive) return;
  const mapEl = document.getElementById('map');
  if (mapEl && !mapEl.contains(e.target)) { _hideLassoRect(); _exitLassoSelect(); }
}

function _enterLassoSelect() {
  _lassoActive = true;
  const btn = document.getElementById('sb-lasso-btn');
  if (btn) btn.classList.add('active');
  // Show instruction hint (laptop only — CSS hides it on mobile)
  const hint = document.getElementById('lasso-hint');
  if (hint) hint.style.display = 'block';
  // Disable map drag so the rect-draw doesn't pan
  map.dragging.disable();
  map.touchZoom.disable();
  const mapEl = document.getElementById('map');
  mapEl.style.cursor = 'crosshair';
  mapEl.addEventListener('mousedown',  _lassoMouseDown);
  mapEl.addEventListener('touchstart', _lassoTouchStart, { passive: false });
  document.addEventListener('keydown', _lassoKeyDown);
  document.addEventListener('click',   _lassoDocClick,  true);
}

function _exitLassoSelect() {
  const _sheet = document.getElementById('walk-bottom-sheet');
  if (_sheet) _sheet.classList.remove('wbs-drawing');   // "Create from map" sheet comes back
  if (!_lassoActive) return;
  _lassoActive  = false;
  _lassoDrawing = false;
  _lassoDragStart = null;
  const btn = document.getElementById('sb-lasso-btn');
  if (btn) btn.classList.remove('active');
  // Always hide hint and clear ghost rect on exit
  const hint = document.getElementById('lasso-hint');
  if (hint) hint.style.display = 'none';
  _hideLassoRect();
  map.dragging.enable();
  map.touchZoom.enable();
  const mapEl = document.getElementById('map');
  mapEl.style.cursor = '';
  mapEl.removeEventListener('mousedown',  _lassoMouseDown);
  mapEl.removeEventListener('touchstart', _lassoTouchStart);
  document.removeEventListener('mousemove', _lassoMouseMove);
  document.removeEventListener('mouseup',   _lassoMouseUp);
  document.removeEventListener('touchmove', _lassoTouchMove);
  document.removeEventListener('touchend',  _lassoTouchEnd);
  document.removeEventListener('keydown', _lassoKeyDown);
  document.removeEventListener('click',   _lassoDocClick,  true);
}

function _lassoMouseDown(e) {
  if (!_lassoActive) return;
  e.preventDefault();
  _lassoDrawing   = true;
  _lassoDragStart = { x: e.clientX, y: e.clientY };
  document.addEventListener('mousemove', _lassoMouseMove);
  document.addEventListener('mouseup',   _lassoMouseUp);
}

function _lassoMouseMove(e) {
  if (!_lassoDrawing) return;
  _updateLassoRect(_lassoDragStart, { x: e.clientX, y: e.clientY });
}

function _lassoMouseUp(e) {
  if (!_lassoDrawing) return;
  _lassoDrawing = false;
  document.removeEventListener('mousemove', _lassoMouseMove);
  document.removeEventListener('mouseup',   _lassoMouseUp);
  _finishLassoDraw(_lassoDragStart, { x: e.clientX, y: e.clientY });
}

function _lassoTouchStart(e) {
  if (!_lassoActive || e.touches.length !== 1) return;
  e.preventDefault();
  const t = e.touches[0];
  _lassoDrawing   = true;
  _lassoDragStart = { x: t.clientX, y: t.clientY };
  document.addEventListener('touchmove', _lassoTouchMove, { passive: false });
  document.addEventListener('touchend',  _lassoTouchEnd);
}

function _lassoTouchMove(e) {
  if (!_lassoDrawing || e.touches.length !== 1) return;
  e.preventDefault();
  const t = e.touches[0];
  _updateLassoRect(_lassoDragStart, { x: t.clientX, y: t.clientY });
}

function _lassoTouchEnd(e) {
  if (!_lassoDrawing) return;
  _lassoDrawing = false;
  document.removeEventListener('touchmove', _lassoTouchMove);
  document.removeEventListener('touchend',  _lassoTouchEnd);
  const t = e.changedTouches[0];
  _finishLassoDraw(_lassoDragStart, { x: t.clientX, y: t.clientY });
}

function _updateLassoRect(start, end) {
  const canvas  = document.getElementById('lasso-canvas');
  const mapRect = document.getElementById('map').getBoundingClientRect();
  const x1 = Math.min(start.x, end.x) - mapRect.left;
  const y1 = Math.min(start.y, end.y) - mapRect.top;
  const x2 = Math.max(start.x, end.x) - mapRect.left;
  const y2 = Math.max(start.y, end.y) - mapRect.top;
  canvas.style.cssText = `display:block;position:absolute;left:${x1}px;top:${y1}px;`
    + `width:${x2 - x1}px;height:${y2 - y1}px;`;
}

function _hideLassoRect() {
  const c = document.getElementById('lasso-canvas');
  if (c) c.style.display = 'none';
}

function _finishLassoDraw(start, end) {
  _hideLassoRect();
  // Ignore tiny drags (accidental taps) — exit lasso so cursor is always restored
  if (Math.abs(start.x - end.x) < 8 || Math.abs(start.y - end.y) < 8) {
    _exitLassoSelect();
    return;
  }

  const mapEl   = document.getElementById('map');
  const mapRect = mapEl.getBoundingClientRect();
  // Pixel bounding box relative to map container — exact match to visual lasso rect
  const px1 = Math.min(start.x, end.x) - mapRect.left;
  const py1 = Math.min(start.y, end.y) - mapRect.top;
  const px2 = Math.max(start.x, end.x) - mapRect.left;
  const py2 = Math.max(start.y, end.y) - mapRect.top;

  let added = 0;
  const _inBox = [];                 // Edit walk lasso: the pins inside the box
  for (const f of allFeatures) {
    const p = f.properties;
    if (!p.species_primary || !_passesFilters(p)) continue;
    const [lng, lat] = f.geometry.coordinates;
    if (lng == null || lat == null) continue;
    // Convert pin lat/lng → container pixel — stays exact regardless of projection
    const pt = map.latLngToContainerPoint([lat, lng]);
    if (pt.x < px1 || pt.x > px2 || pt.y < py1 || pt.y > py2) continue;
    if (_walkPinSel) { _inBox.push(p); continue; }
    if (!ForagingList.has(p.species_primary)) {
      ForagingList.add(p.species_primary);
      added++;
    }
  }
  if (_walkPinSel) {
    // Edit walk: marks only — nothing written until Save changes.
    const n = _walkLassoToggle(_inBox);
    renderMarkers();
    _exitLassoSelect();
    _showLocateToast(n ? `${n} pin${n === 1 ? '' : 's'} marked — Save changes to apply` : 'No pins in that area');
    return;
  }
  _updateSelectCount();
  renderMarkers();
  // Exit lasso mode automatically after each draw so the user can pan/tap
  _exitLassoSelect();
  if (added > 0) _showLocateToast(`${added} species added`);
  else           _showLocateToast('No new species in that area');
  // Update bottom sheet lasso section (walk mode, phone)
  if (_walkActive) _wbsRenderLasso();
}

// ── Pin selection state ────────────────────────────────────────────────────
let _selectedPinMarker = null;   // the currently selected L.Marker
let _selectedPinObs    = null;   // its properties object

function _deselectPin() {
  if (_selectedPinMarker && _selectedPinObs) {
    const wasHighlighted = _selectedPinObs.id === highlightedMarkerId;
    const cat = _selectedPinObs.obs_category;
    // Restore layer-appropriate icon (pass category for correct colour)
    const inPinsLayer = pinsGroup.hasLayer(_selectedPinMarker);
    _selectedPinMarker.setIcon(
      wasHighlighted
        ? makeHighlightIcon(cat)
        : inPinsLayer
          ? makePinDotIcon(false, cat)
          : makeIcon(_selectedPinObs.has_enrichment, false, cat)
    );
  }
  _selectedPinMarker = null;
  _selectedPinObs    = null;
}

// Clicking the map background deselects any pin; geology layer adds rock unit lookup
map.on('click', function(e) {
  // Bug 2 fix: suppress all map-click side-effects during GPS walk recording.
  if (window.WalkRecorder && WalkRecorder.isRecording()) return;
  // Fix 0: click on map background closes the detail panel back to collapsed tab strip
  if (_currentDetailObs) {
    closeSidebar();
    document.getElementById('detail-view').style.display = 'none';
    document.getElementById('sidebar').classList.remove('rp-detail');
    _currentDetailObs = null;
    _deselectPin();
  }
  if (_currentBaseLayerKey === 'geology') {
    _queryGeology(e.latlng.lat, e.latlng.lng);
  } else {
    _hideGeoToast();
  }
});

// ── Fix 2: Geology click identification ──────────────────────────────────
let _geoToastTimer = null;

function _hideGeoToast() {
  clearTimeout(_geoToastTimer);
  document.getElementById('geo-toast').classList.remove('visible');
}

async function _queryGeology(lat, lng) {
  const toast = document.getElementById('geo-toast');
  // Show loading state immediately
  document.getElementById('gt-name').textContent = 'Identifying rock unit…';
  document.getElementById('gt-lith').textContent = '';
  document.getElementById('gt-age').textContent  = '';
  toast.classList.add('visible');
  clearTimeout(_geoToastTimer);

  try {
    const r = await fetch(
      `https://macrostrat.org/api/v2/geologic_units/map?lat=${lat}&lng=${lng}&response=short`
    );
    if (!r.ok) throw new Error('API error');
    const data = await r.json();
    const rows = (data.success && data.success.data) || [];
    if (!rows.length) {
      document.getElementById('gt-name').textContent = 'No geology data for this location';
    } else {
      const u = rows[0];
      const name = u.name || u.strat_name || 'Unknown unit';
      const lith = u.lith || '';
      const period = u.best_int_name || '';
      const ages = (u.b_age && u.t_age)
        ? `${u.b_age}–${u.t_age} Ma`
        : '';
      const ageStr = [period, ages].filter(Boolean).join(' · ');

      document.getElementById('gt-name').textContent = name;
      document.getElementById('gt-lith').textContent = lith;
      document.getElementById('gt-age').textContent  = ageStr;
    }
  } catch (_) {
    document.getElementById('gt-name').textContent = 'Could not load geology data';
  }

  // Auto-dismiss after 8 seconds
  _geoToastTimer = setTimeout(_hideGeoToast, 8000);
}

// ── Data loading ──────────────────────────────────────────────────────────

function _bboxQuery() {
  const b = map.getBounds();
  return `min_lng=${b.getWest()}&min_lat=${b.getSouth()}`
       + `&max_lng=${b.getEast()}&max_lat=${b.getNorth()}`;
}

// Bbox-bounded pin layer for the current viewport. Refetched on pan/zoom.
// Pins drive marker rendering and walk-building (both viewport-relative).
async function loadFeatures() {
  const seq = ++_pinLoadSeq;
  let geo;
  try {
    geo = await (await fetch(`/api/map/geojson?${_bboxQuery()}`)).json();
  } catch (_) { return; }
  if (seq !== _pinLoadSeq) return;  // a newer viewport request superseded us
  allFeatures = geo.features || [];
  renderMarkers();
}

// Whole-archive heat points + stats-bar totals. Loaded once at init and after
// data mutations; never bbox-bounded (the heatmap shows global density).
async function loadHeat() {
  try {
    const r = await fetch('/api/map/heat');
    if (!r.ok) return;
    const d = await r.json();
    _heatAll = d.points || [];
    // Whole-archive totals are no longer shown in the map chrome (Map Redesign
    // P1 — the counts pill shows in-view sightings only, see renderMarkers()).
    renderMarkers();
  } catch (_) {}
}

// Deep-link highlight (?highlight=ID) from the species gallery. The target may
// be outside the initial viewport, so fall back to an unbounded lookup.
async function _initHighlight() {
  const highlightId = parseInt(new URLSearchParams(location.search).get('highlight'));
  if (!highlightId || isNaN(highlightId)) return;
  let target = allFeatures.find(f => f.properties.id === highlightId);
  if (!target) {
    try {
      const geo = await (await fetch('/api/map/geojson')).json();
      target = (geo.features || []).find(f => f.properties.id === highlightId);
    } catch (_) {}
  }
  if (!target) return;
  if (_highlightTimer) { clearTimeout(_highlightTimer); _highlightTimer = null; }
  highlightedMarkerId = highlightId;
  const [tLng, tLat] = target.geometry.coordinates;
  // flyTo triggers moveend → bbox refetch → target rendered (highlighted).
  map.flyTo([tLat, tLng], 15, { duration: 1.2, easeLinearity: 0.4 });
  setTimeout(() => {
    showDetail(target.properties);
    if (isMobile()) openSidebar();
  }, 250);
  _highlightTimer = setTimeout(() => {
    highlightedMarkerId = null;
    _highlightTimer = null;
    renderMarkers();
  }, 5000);
}

// Generic deep-link centre + standalone target marker (?lat=..&lng=..&z=..[&obs=..]).
// Unlike ?highlight (which resolves the obs through the /api/map/geojson pin layer
// and therefore CANNOT show needs_review / unapproved observations), this drops a
// marker at the exact coords independent of any layer — so a review card's ↗ works
// for any observation regardless of review_status. Reusable from species cards,
// encounters, etc. Full-precision lat/lng come straight from the source record.
let _deepLinkMarker = null;
function _initLatLngDeepLink() {
  const q = new URLSearchParams(location.search);
  const lat = parseFloat(q.get('lat'));
  const lng = parseFloat(q.get('lng'));
  if (!isFinite(lat) || !isFinite(lng)) return;
  let z = parseInt(q.get('z'), 10);
  if (!isFinite(z)) z = 17;
  const obsId = parseInt(q.get('obs'), 10);  // parsed as int → safe to interpolate

  // Authoritative initial view (the position-memory restore is skipped when these
  // params are present, so nothing overrides this).
  map.setView([lat, lng], z);

  const icon = L.divIcon({
    className: 'fid-deeplink-icon',
    html: '<div class="fid-deeplink-pin"></div>',
    iconSize: [22, 22], iconAnchor: [11, 11],
  });
  if (_deepLinkMarker) map.removeLayer(_deepLinkMarker);
  _deepLinkMarker = L.marker([lat, lng], {
    icon: icon, zIndexOffset: 1200, keyboard: false,
    title: isFinite(obsId) ? ('Observation #' + obsId) : 'Target location',
  }).addTo(map);
  if (isFinite(obsId)) _deepLinkMarker.bindPopup('Observation #' + obsId).openPopup();
}

// Deep-link species filter (?species=<scientific_name>) from a species card map
// thumbnail. Applies the species filter and centres the map on all of that
// species' observations.
async function _initSpeciesFilter() {
  // filterState.species was already populated by _readFiltersFromUrl(); this
  // step just zooms to the selected species when arriving via a deep link.
  if (!filterState.species.size) return;
  const sel = filterState.species;
  setLayer('pins');               // arrive in pins view, not the default heatmap
  // Gather all observation coords for the selected species (may be outside viewport).
  let feats = (allFeatures || []).filter(f => sel.has(f.properties.species_primary));
  if (!feats.length) {
    try {
      const geo = await (await fetch('/api/map/geojson')).json();
      feats = (geo.features || []).filter(f => sel.has(f.properties.species_primary));
    } catch (_) {}
  }
  if (feats.length) {
    const latLngs = feats.map(f => [f.geometry.coordinates[1], f.geometry.coordinates[0]]);
    if (latLngs.length === 1) {
      map.flyTo(latLngs[0], 14, { duration: 1.0, easeLinearity: 0.4 });
    } else {
      map.fitBounds(L.latLngBounds(latLngs), { padding: [50, 50], maxZoom: 14 });
    }
  }
  renderMarkers();
}

// Review-count badge now populated by site-header.js's _initReviewBadge() (Map Redesign P3-nav).

// ── Species filter (now a multi-select) ──────────────────────────────────

let _allSpeciesList = [];
let _allSpeciesOptions = [];  // full option list for search filtering

async function loadSpeciesFilter() {
  try {
    const r = await fetch('/api/species/');
    if (!r.ok) return;
    const data = await r.json();
    _allSpeciesList = data.slice().sort((a, b) => a.scientific_name.localeCompare(b.scientific_name));
    _allSpeciesOptions = _allSpeciesList.map(sp => ({
      value: sp.scientific_name,
      label: spNameText(sp.scientific_name, spPickCommon(sp.preferred_common_name, sp.common_names)),
    }));
    _populateSpeciesSelect('');
  } catch (_) { /* non-fatal */ }
}

function _populateSpeciesSelect(query) {
  const sel = document.getElementById('fp-species-select');
  if (!sel) return;
  const q = (query || '').toLowerCase().trim();
  const visible = q
    ? _allSpeciesOptions.filter(o =>
        o.value.toLowerCase().includes(q) || o.label.toLowerCase().includes(q))
    : _allSpeciesOptions;
  sel.innerHTML = visible.map(o => {
    const selected = filterState.species.has(o.value) ? ' selected' : '';
    return `<option value="${_esc(o.value)}"${selected}>${_esc(o.label)}</option>`;
  }).join('');
}

// Called when user types in species search box
function _filterSpeciesSelect(query) {
  _populateSpeciesSelect(query);
}

// Called when selection in species <select multiple> changes
function _onSpeciesSelectChange() {
  const sel = document.getElementById('fp-species-select');
  if (!sel) return;
  filterState.species.clear();
  Array.from(sel.selectedOptions).forEach(o => filterState.species.add(o.value));
  _updateFilterFab(); renderMarkers();
}

// Called when month <select multiple> changes
function _onMonthSelectChange() {
  const sel = document.getElementById('fp-month-select');
  if (!sel) return;
  filterState.months.clear();
  Array.from(sel.selectedOptions).forEach(o => filterState.months.add(parseInt(o.value)));
  _updateFilterFab(); renderMarkers();
}

// Called when source <select> changes
function _onSourceSelectChange() {
  const sel = document.getElementById('fp-source-select');
  filterState.source = sel ? sel.value : '';
  _updateFilterFab(); renderMarkers();
}

// Legacy: _renderSpeciesChecklist is still called in clearAllFilters — keep as no-op alias
function _renderSpeciesChecklist() { _populateSpeciesSelect(''); }

// ── Toolbar panel toggle — superseded by the config sheet (Map Redesign P1).
// _openToolbarPanel is kept (always null) because a handful of defensive
// guards elsewhere in this file still reference it; they no-op harmlessly.

let _openToolbarPanel = null;

// Close the config sheet without toggling — used by walk/find/nearme/detail
// views so the sheet doesn't visually compete with the view being shown.
function _closeTabPanels() {
  closeConfigSheet();
}

// ── Filter toggles ────────────────────────────────────────────────────────


const _SEASON_MONTHS = {
  spring: [3, 4, 5],
  summer: [6, 7, 8],
  autumn: [9, 10, 11],
  winter: [12, 1, 2],
};


function _toggleSeason(season) {
  const months = _SEASON_MONTHS[season];
  if (!months) return;
  const allActive = months.every(m => filterState.months.has(m));
  if (allActive) months.forEach(m => filterState.months.delete(m));
  else           months.forEach(m => filterState.months.add(m));
  _syncMonthBtns();
  _syncSeasonBtns();
  _updateFilterFab();
  renderMarkers();
}

function _syncMonthBtns() {
  for (let m = 1; m <= 12; m++) {
    const btn = document.getElementById(`fp-month-${m}`);
    if (btn) btn.classList.toggle('active', filterState.months.has(m));
  }
}

function _syncSeasonBtns() {
  for (const [season, months] of Object.entries(_SEASON_MONTHS)) {
    const btn = document.getElementById(`fp-season-${season}`);
    if (btn) btn.classList.toggle('active', months.some(m => filterState.months.has(m)));
  }
}

function clearAllFilters() {
  filterState.species.clear();
  filterState.months.clear();
  filterState.source    = '';
  filterState.workshop  = false;
  filterState.humanOnly = false;
  filterState.inSeason  = false;
  // Reset species select
  const spSel = document.getElementById('fp-species-select');
  if (spSel) Array.from(spSel.options).forEach(o => { o.selected = false; });
  document.getElementById('fp-species-search') && (document.getElementById('fp-species-search').value = '');
  _populateSpeciesSelect('');
  // Reset month select
  const moSel = document.getElementById('fp-month-select');
  if (moSel) Array.from(moSel.options).forEach(o => { o.selected = false; });
  // Reset source select
  const srcSel = document.getElementById('fp-source-select');
  if (srcSel) srcSel.value = '';
  _syncSeasonBtns();
  const wsCb  = document.getElementById('filter-workshop');
  const humCb = document.getElementById('filter-human-only');
  const isCb  = document.getElementById('filter-in-season');
  const osCb  = document.getElementById('overlay-in-season');
  if (wsCb)  wsCb.checked  = false;
  if (humCb) humCb.checked = false;
  if (isCb)  isCb.checked  = false;
  if (osCb)  osCb.checked  = false;
  _updateFilterFab();
  renderMarkers();
}

// ── Filter state (Feature 1) ──────────────────────────────────────────────
// All filter criteria live here; renderMarkers() and _buildWalkRoute() both
// read from this single source of truth.

const filterState = {
  species:   new Set(),   // scientific names; empty = all species shown
  months:    new Set(),   // 1–12; empty = all months shown
  source:    '',          // '' = all, 'syncthing', 'file_upload'
  workshop:  false,
  humanOnly: false,
  inSeason:  false,       // "In season now" — server flags p.in_season per pin
};

function _passesFilters(p) {
  if (filterState.species.size > 0 && !filterState.species.has(p.species_primary)) return false;
  if (filterState.humanOnly && !p.human_corrected) return false;
  if (filterState.workshop  && !p.workshop_suitable) return false;
  if (filterState.inSeason  && !p.in_season) return false;
  if (filterState.source && p.upload_source !== filterState.source) return false;
  if (filterState.months.size > 0) {
    const m = monthOfDate(p.taken_at);
    if (!m || !filterState.months.has(m)) return false;
  }
  return true;
}

// Same filter logic as _passesFilters, but for the compact heat-point arrays
// [lat, lng, species_primary, human_corrected, workshop_suitable, month, in_season, upload_source].
function _heatPassesFilters(pt) {
  if (filterState.species.size > 0 && !filterState.species.has(pt[2])) return false;
  if (filterState.humanOnly && !pt[3]) return false;
  if (filterState.workshop  && !pt[4]) return false;
  if (filterState.inSeason  && !pt[6]) return false;
  if (filterState.months.size > 0 && (!pt[5] || !filterState.months.has(pt[5]))) return false;
  // pt[7] = upload_source (if present; heat data may not include it — skip if absent)
  if (filterState.source && pt[7] != null && pt[7] !== filterState.source) return false;
  return true;
}

function _countActiveFilters() {
  let n = 0;
  if (filterState.species.size > 0) n++;
  if (filterState.months.size  > 0) n++;
  if (filterState.source)           n++;
  if (filterState.workshop)         n++;
  if (filterState.humanOnly)        n++;
  if (filterState.inSeason)         n++;
  return n;
}

function _updateFilterFab() {
  _writeFiltersToUrl();
  const n      = _countActiveFilters();
  const btn    = document.getElementById('btn-panel-filters');
  const badge  = document.getElementById('filter-count-badge');
  if (btn && n > 0 && _openToolbarPanel !== 'filters') btn.style.borderColor = '#2d5016';
  else if (btn) btn.style.borderColor = '';
  if (badge) {
    badge.textContent = n > 0 ? n : '';
    badge.classList.toggle('visible', n > 0);
  }
  const clearBtn    = document.getElementById('fp-clear-btn');
  const activeLabel = document.getElementById('fp-active-label');
  if (clearBtn)    clearBtn.disabled = (n === 0);
  if (activeLabel) activeLabel.textContent = n === 0
    ? 'No filters active'
    : `${n} filter${n !== 1 ? 's' : ''} active`;
}

// ── Filter ↔ URL serialization (Fix #1) ───────────────────────────────────
// filterState is mirrored into the query string so it survives navigation and
// is shareable/addressable. _writeFiltersToUrl() runs inside _updateFilterFab
// (the single chokepoint every filter mutation calls); _readFiltersFromUrl()
// runs once on load, before the species checklist renders.

function _writeFiltersToUrl() {
  const params = new URLSearchParams(location.search);
  if (filterState.species.size) params.set('species', [...filterState.species].join(','));
  else                          params.delete('species');
  if (filterState.months.size)  params.set('months', [...filterState.months].sort((a, b) => a - b).join(','));
  else                          params.delete('months');
  if (filterState.workshop)  params.set('workshop', '1'); else params.delete('workshop');
  if (filterState.humanOnly) params.set('human', '1');    else params.delete('human');
  const qs = params.toString();
  history.replaceState(null, '', location.pathname + (qs ? '?' + qs : '') + location.hash);
}

function _readFiltersFromUrl() {
  const params = new URLSearchParams(location.search);
  const sp = params.get('species');
  if (sp) sp.split(',').map(s => s.trim()).filter(Boolean).forEach(s => filterState.species.add(s));
  const mo = params.get('months');
  if (mo) mo.split(',').map(s => parseInt(s, 10)).filter(m => m >= 1 && m <= 12).forEach(m => filterState.months.add(m));
  filterState.workshop  = params.get('workshop') === '1';
  filterState.humanOnly = params.get('human') === '1';
  // Reflect into the static controls (species checklist syncs itself on render).
  const wsCb  = document.getElementById('filter-workshop');
  const humCb = document.getElementById('filter-human-only');
  if (wsCb)  wsCb.checked  = filterState.workshop;
  if (humCb) humCb.checked = filterState.humanOnly;
  _syncMonthBtns();
  _syncSeasonBtns();
  _updateFilterFab();
}

// ── Filtering ─────────────────────────────────────────────────────────────

function monthOfDate(isoStr) {
  if (!isoStr) return null;
  return new Date(isoStr).getMonth() + 1;
}

function seasonOfMonth(m) {
  if (!m) return null;
  if (m >= 3 && m <= 5)  return 'spring';
  if (m >= 6 && m <= 8)  return 'summer';
  if (m >= 9 && m <= 11) return 'autumn';
  return 'winter';
}

function renderMarkers() {
  clusterGroup.clearLayers();
  pinsGroup.clearLayers();

  // ── Pins — bbox-bounded viewport set, filter-applied ────────────────────
  let visible = 0;
  const _wMembers = _walkPinSel ? _walkMemberSet() : null;   // walk "✎ Edit walk" mode
  const visibleSpecies = new Set();
  for (const f of allFeatures) {
    const p = f.properties;
    // All features from the API are confirmed — no status filter needed here.
    if (!_passesFilters(p)) continue;
    if (p.species_primary) visibleSpecies.add(p.species_primary);

    const [lng, lat] = f.geometry.coordinates;
    const isHighlighted = p.id === highlightedMarkerId;
    const cat = p.obs_category || 'plant';
    const isSelected = _selectMode && p.species_primary && ForagingList.has(p.species_primary);
    const clusterIcon = isSelected ? makeSelectRingIcon(cat)
      : isHighlighted ? makeHighlightIcon(cat) : makeIcon(p.has_enrichment, false, cat);
    const pinIcon     = isSelected ? makeSelectRingIcon(cat) : makePinDotIcon(isHighlighted, cat);

    // Walk "✎ Edit walk" mode: on-walk / not-on-walk / selected rings, drawn
    // above the walk's stop markers so every pin can be tapped.
    const wsel = _walkPinSel ? _walkSelIcon(Number(p.id), cat, _wMembers) : null;
    const mkCluster = L.marker([lat, lng], wsel ? { icon: wsel, zIndexOffset: 1000 } : { icon: clusterIcon });
    mkCluster.on('click', () => handlePinClick(p, lat, lng, mkCluster));
    clusterGroup.addLayer(mkCluster);

    const mkPins = L.marker([lat, lng], wsel ? { icon: wsel, zIndexOffset: 1000 } : { icon: pinIcon });
    if (wsel && p.species_primary) {
      // Edit walk: pending pins keep their name label; any other pin shows it on hover
      // (desktop). Pins layer only (walk mode always uses it); a label can never break the redraw.
      const sel = _walkPending.add.has(Number(p.id)) || _walkPending.remove.has(Number(p.id));   // pending
      try {
        mkPins.bindTooltip(spNameHtml(p.species_primary, p.common_name),
          { permanent: sel, direction: 'top', offset: [0, -10], className: 'walk-pin-label' });
      } catch (_) {}
    }
    mkPins.on('click', () => handlePinClick(p, lat, lng, mkPins));
    pinsGroup.addLayer(mkPins);

    visible++;
  }

  // ── Heatmap — whole-archive density (filter-responsive), bbox-independent.
  // Landscape pins are already excluded by the /api/map/heat query.
  const heatPoints = [];
  for (const pt of _heatAll) {
    if (!_heatPassesFilters(pt)) continue;
    heatPoints.push([pt[0], pt[1], 1.0]);
  }

  // Add note pins to heatmap density (weight 0.7 — slightly lower than photo pins)
  for (const f of noteFeatures) {
    const [lng, lat] = f.geometry.coordinates;
    heatPoints.push([lat, lng, 0.7]);
  }

  _heatPoints = heatPoints;
  _heatSetLatLngs(heatPoints);
  _recalcHeatMax();
  // Sync canvas opacity with brightness slider on every render.
  // updateHeatmapOptions() only fires on slider input, so without this the canvas
  // starts at opacity 1.0 regardless of the 80% default, making every point a
  // distinct full-opacity blob rather than a density-graduated field.
  if (heatLayer._canvas) {
    heatLayer._canvas.style.opacity = (parseInt(document.getElementById('hc-brightness').value) || 80) / 100;
  }
  // Counts pill (Map Redesign P1 Step 7 / P3 species count) — sightings and
  // distinct species in the current viewport matching active filters. Both
  // numbers come from the same _passesFilters loop above, so they always
  // describe the identical filtered in-view set.
  const pillSightings = document.getElementById('pill-sightings');
  const pillSpecies   = document.getElementById('pill-species');
  if (pillSightings) pillSightings.textContent = visible;
  if (pillSpecies)   pillSpecies.textContent   = visibleSpecies.size;
  _applyLayer();
}

