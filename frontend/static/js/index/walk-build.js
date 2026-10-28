// ═══════════════════════════════════════════════════════════════════════════
// Walk mode — pin selection, nearest-neighbour route, export to maps
// ═══════════════════════════════════════════════════════════════════════════

let _walkActive       = false;   // walk mode on/off
let _walkDrawing      = false;   // mouse down, dragging
let _walkDragStart    = null;    // {x, y} in page coords
let _walkDrawMode     = 'rect';  // 'rect' | 'circle'
let _walkRouteLayer   = null;    // L.layerGroup for walk-route pins
let _walkSelected     = [];      // sorted stops [{p, lat, lng}]
let _activeWalkRoute  = null;    // last built route (for export)
let _activeWalkEnrich = null;    // last enrichment map (for export)
let _walkOrsFallback  = false;   // true when ORS was unavailable
let _walkOrsDistM     = 0;       // ORS-reported distance in metres
let _walkOrsDurMin    = 0;       // ORS-reported duration in minutes
let _walkCircular     = true;    // close the loop back to start
// GPS walk recording start controls are hidden (batch 15b); see .rec-ui-off.
const WALK_RECORDING_UI = false;
let _walkRouteGeom    = null;    // ORS LineString geometry of the current route (saved with the walk)
let _walkStraightRanges = [];    // saved walks: vertex ranges [[a, b], …] of _walkRouteGeom drawn dashed —
                                 // straight legs between stops (no mapped path / ORS detour). Read by
                                 // _walkStraightRangesOf (meta.straight_ranges, legacy meta.straight_from)
let _walkStopRadiusM  = 30;      // stop grouping radius (slider, 10–100 m)
let _walkLastPins     = null;    // raw pins + notes from the last drawn area — regroup source
                                 // (null for a loaded saved walk: its stops are fixed)
let _walkRouteStatus  = null;    // {kind:'ok'|'single'|'capped'|'failed', reason, n, max}
let _walkStraightLine = false;   // user chose the straight-line fallback after an ORS failure
let _walkBuildSeq     = 0;       // guards against stale ORS responses after a regroup
let _walkRadiusTimer  = null;    // debounce for the radius slider
let _walkSaved        = null;    // {id, name, sig} — walk last saved or loaded; header shows its name while the route still matches sig
let _walkSaving       = false;   // a save is in progress (prompt or request) — blocks a second save
let _walkLineClosed   = false;   // loaded saved walk: the STORED line is a closed loop (Start here / Reverse
                                 // work in either view) — from the server's shown.line_closed
let _lastWalkBounds   = null;    // last drawn rect bounds (for re-route)
let _lastWalkCircle   = null;    // last drawn circle spec (for re-route)

// ── Enter / exit walk mode ─────────────────────────────────────────────────

function _enterWalkMode() {
  _walkActive = true;
  _pinsExplicit = false;
  const _wbs = document.getElementById('walk-bottom-sheet');
  if (_wbs) { _wbs.classList.add('wbs-active', 'wbs-open'); }
  const _wbsChev = document.getElementById('wbs-chevron');
  if (_wbsChev) _wbsChev.textContent = '▾';
  _wbsShowEmptyState();   // show three option cards in wbs-body
  const _wrecBtn = document.getElementById('wrec-float-btn');
  if (_wrecBtn && WALK_RECORDING_UI) _wrecBtn.style.display = 'flex';
  // Walk mode draws over Pins layer (which it enables)
  _applyLayer();
  _attachWalkDraw();
  // Show upload button if there are pending walks in IndexedDB
  // Audio notes are saved as walk-note.webm (audio/webm via MediaRecorder)
  _walkUpdateSyncBtn();
  // Laptop: quickbar appears above handle via CSS (wbs-active + no wbs-route-active)
}

function _exitWalkMode() {
  _walkActive = false;
  _walkDrawing = false;
  _walkDragStart = null;
  document.getElementById('walk-clear-btn').classList.remove('visible');
  document.getElementById('walk-mode-toggle').classList.remove('visible');
  const _walkTabBtn = document.getElementById('btn-layer-walk');
  if (_walkTabBtn) _walkTabBtn.classList.remove('active');
  _hideWalkRect();
  _hideWalkCircle();
  _detachWalkDraw();
  if (_walkRouteLayer) { map.removeLayer(_walkRouteLayer); _walkRouteLayer = null; }
  _walkTidySeq++;                // a build still waiting for its stop order is dropped
  _walkSelected = [];
  _walkLastPins = null;
  _walkRouteStatus = null;
  _walkPinSelExit();
  _walkPendingClear();
  _walkHighlightClear();
  _walkSaved = null;
  _walkLineClosed = false;
  _walkStraightLine = false;
  _walkBuildSeq++;              // any ORS response still in flight is now stale
  clearTimeout(_walkRadiusTimer);
  _stopProxWatch();             // 10a.5 — clear GPS watch and dismiss all alerts
  const _wrecBtn2 = document.getElementById('wrec-float-btn');
  if (_wrecBtn2) _wrecBtn2.style.display = 'none';
  // Hide walk view in sidebar and return to Filters tab
  
  // Reset bottom-sheet sections
  const _wbsSum = document.getElementById('wbs-summary');
  if (_wbsSum) _wbsSum.style.display = 'none';
  const _wbsLasso = document.getElementById('wbs-lasso');
  if (_wbsLasso) _wbsLasso.style.display = 'none';
  const _wbsUp = document.getElementById('wbs-upload');
  if (_wbsUp) _wbsUp.style.display = 'none';
  // Reset empty state and route content to default visibility
  var _esEl = document.getElementById('wbs-empty-state');
  if (_esEl) _esEl.style.display = 'none';
  _wbsRestoreRouteContent();
  _closeWalkSheet();
  // Loaded saved walk: drop the side-panel layout and hidden pins, and go back
  // to the layer + map view from before it was opened.
  const _sv = _savedWalkView;
  _savedWalkView = null;
  _savedWalkData = null;
  _renderWalkMembership();
  const _wbsSide = document.getElementById('walk-bottom-sheet');
  if (_wbsSide) _wbsSide.classList.remove('wbs-side', 'wbs-peek');
  const _wbsLbl = document.getElementById('wbs-label');
  if (_wbsLbl) _wbsLbl.textContent = 'Select walk';
  _syncWalkPinsBtn();
  if (_sv) {
    currentLayer = _sv.prevLayer;
    ['pins', 'clusters', 'heatmap'].forEach(m => {
      const b = document.getElementById(`btn-layer-${m}`);
      if (b) b.classList.toggle('active', m === currentLayer);
    });
    map.setView(_sv.prevCenter, _sv.prevZoom);
  }
  _applyLayer();
}

// ── Walk bottom sheet empty state helpers (laptop only) ───────────────────

function _wbsShowEmptyState() {
  var es = document.getElementById('wbs-empty-state');
  if (es) es.style.display = 'block';
  // Hide route-specific controls so they don't show over the entry cards
  ['walk-tabs', 'walk-tab-stops', 'walk-tab-stats', 'wbs-bottom-actions', 'walk-ors-note', 'walk-sync-btn'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
}

function _wbsHideEmptyState() {
  var es = document.getElementById('wbs-empty-state');
  if (es) es.style.display = 'none';
}

function _wbsRestoreRouteContent() {
  // Return route controls to their default display state (renderWalkPanel will re-populate them)
  var tabsEl = document.getElementById('walk-tabs');
  if (tabsEl) tabsEl.style.display = '';
  var stopsEl = document.getElementById('walk-tab-stops');
  if (stopsEl) stopsEl.style.display = '';
  var statsEl = document.getElementById('walk-tab-stats');
  if (statsEl) statsEl.style.display = '';
  var baEl = document.getElementById('wbs-bottom-actions');
  if (baEl) baEl.style.display = '';
}

// Quickbar / entry card actions (laptop only — phone guards via CSS + isMobile checks)
window._wbsStartLasso = function() {
  // The whole sheet retracts so all the map is free to draw on (Melvin 20 Oct
  // 2026); _exitLassoSelect brings it back — on a drawn area or a cancel.
  const sheet = document.getElementById('walk-bottom-sheet');
  if (sheet) sheet.classList.add('wbs-drawing');
  _enterLassoSelect();
};

window._wbsStartRecording = function() {
  if (document.body.classList.contains('guest-mode')) return;  // curator only
  if (!isMobile()) {
    // Laptop: open sheet and show info message — no GPS attempt
    var sheet = document.getElementById('walk-bottom-sheet');
    if (sheet && !sheet.classList.contains('wbs-open')) {
      sheet.classList.add('wbs-open');
      var chev = document.getElementById('wbs-chevron');
      if (chev) chev.textContent = '▾';
    }
    var msgEl = document.getElementById('wbs-laptop-record-msg');
    if (msgEl) msgEl.style.display = 'block';
    return;
  }
  // Mobile: mark route-active, open sheet to show live stats, start recording
  var sheet = document.getElementById('walk-bottom-sheet');
  if (sheet) {
    sheet.classList.add('wbs-route-active');
    if (!sheet.classList.contains('wbs-open')) {
      sheet.classList.add('wbs-open');
      var chev = document.getElementById('wbs-chevron');
      if (chev) chev.textContent = '▾';
    }
  }
  _wbsRestoreRouteContent();
  if (typeof _wrecToggle === 'function') _wrecToggle();
};

window._wbsLoadSaved = function() {
  // Hide route-specific controls so only saved/recorded sections show in the body
  ['walk-tabs', 'walk-tab-stops', 'walk-tab-stats', 'wbs-bottom-actions',
   'walk-ors-note', 'walk-sync-btn', 'wbs-empty-state'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) el.style.display = 'none';
  });
  // Open sheet to reveal the saved walks sections
  var sheet = document.getElementById('walk-bottom-sheet');
  if (sheet && !sheet.classList.contains('wbs-open')) {
    sheet.classList.add('wbs-open');
    var chev = document.getElementById('wbs-chevron');
    if (chev) chev.textContent = '▾';
  }
  // Expand both collapsibles
  var swList = document.getElementById('wbs-saved-walks-list');
  if (swList && swList.style.display === 'none') _wbsToggleSavedWalks();
  var rwList = document.getElementById('wbs-recorded-walks-list');
  if (rwList && rwList.style.display === 'none') _wbsToggleRecordedWalks();
};

// TOOLS → "Open a saved walk": straight to the saved-walks list. Enters walk
// mode first when it is off (setLayer('walk') also closes the config sheet);
// when it is already on, setLayer('walk') would EXIT it, so only close the sheet.
function openSavedWalksList() {
  if (!_walkActive) setLayer('walk');
  else closeConfigSheet();
  _wbsLoadSaved();
}

// ── Walk bottom sheet (phone only) ───────────────────────────────────────
// State: sheet fully hidden (translateY 100%) until Walk tapped.
// Walk tap / chevron tap → toggle wbs-open; handle always visible at bottom.
// Chevron / Walk tap → toggle wbs-open (body slides up/down; handle always visible).

function _openWalkSheet() {
  const sheet = document.getElementById('walk-bottom-sheet');
  if (!sheet) return;
  // Toggle: open if closed, close if already open
  const isOpen = sheet.classList.contains('wbs-open');
  sheet.classList.toggle('wbs-open', !isOpen);
  const chev = document.getElementById('wbs-chevron');
  if (chev) chev.textContent = !isOpen ? '▾' : '▴';
}

function _closeWalkSheet() {
  const sheet = document.getElementById('walk-bottom-sheet');
  if (!sheet) return;
  sheet.style.transform = '';        // clear any drag-set inline transform
  sheet.classList.remove('wbs-open', 'wbs-active', 'wbs-route-active');
  const chev = document.getElementById('wbs-chevron');
  if (chev) chev.textContent = '▴';
}

window._wbsToggle = function () {
  const sheet = document.getElementById('walk-bottom-sheet');
  if (!sheet) return;
  sheet.style.transform = '';        // clear any drag-set inline transform; let CSS class take over
  sheet.style.transition = '';       // restore transition if drag had disabled it
  _openWalkSheet();
  const nowOpen = sheet.classList.contains('wbs-open');
  document.getElementById('walk-mode-toggle').classList.toggle('visible', nowOpen);
};

// ── Walk handle drag — free-position drag with tap fallback ───────────────
(function () {
  const handle = document.getElementById('wbs-handle');
  const sheet  = document.getElementById('walk-bottom-sheet');
  if (!handle || !sheet) return;

  let _ptId        = null;   // captured pointer id
  let _startY      = 0;      // pointer clientY at drag start
  let _startTY     = 0;      // sheet translateY at drag start (px)
  let _moved       = false;  // true once pointer moves > threshold

  function _currentTranslateY() {
    const m = new DOMMatrix(window.getComputedStyle(sheet).transform);
    return m.m42;             // resolved pixel translateY
  }

  handle.addEventListener('pointerdown', function (e) {
    if (e.button && e.button !== 0) return;
    _ptId    = e.pointerId;
    _startY  = e.clientY;
    _startTY = _currentTranslateY();
    _moved   = false;
    sheet.style.transition = 'none';   // disable CSS transition during drag
    handle.setPointerCapture(e.pointerId);
    e.preventDefault();
  }, { passive: false });

  handle.addEventListener('pointermove', function (e) {
    if (e.pointerId !== _ptId) return;
    const delta = e.clientY - _startY;
    if (!_moved && Math.abs(delta) < 5) return;
    _moved = true;
    // Clamp: can't go above viewport top (0); always keep at least 44px visible at bottom
    const minTY = 0;
    const maxTY = sheet.offsetHeight - 44;
    const newTY = Math.max(minTY, Math.min(maxTY, _startTY + delta));
    sheet.style.transform = `translateY(${newTY}px)`;
  });

  handle.addEventListener('pointerup', function (e) {
    if (e.pointerId !== _ptId) return;
    _ptId = null;
    sheet.style.transition = '';       // restore CSS transition
    // Drag — leave sheet at dropped position (inline transform stays)
    // Tap — no action; drawer stays open
  });

  handle.addEventListener('pointercancel', function () {
    _ptId = null;
    sheet.style.transition = '';
    sheet.style.transform  = '';       // snap back to CSS class position on cancel
  });
}());

window._wbsToggleSavedWalks = function () {
  const listEl  = document.getElementById('wbs-saved-walks-list');
  const arrowEl = document.getElementById('wbs-saved-walks-arrow');
  if (!listEl) return;
  const open = listEl.style.display !== 'none';
  listEl.style.display = open ? 'none' : 'block';
  if (arrowEl) arrowEl.textContent = open ? '▸' : '▾';
  if (!open) loadSavedWalksList();   // reuses loadSavedWalksList which also populates wbs copy
};

window._wbsToggleRecordedWalks = function () {
  const listEl  = document.getElementById('wbs-recorded-walks-list');
  const arrowEl = document.getElementById('wbs-recorded-walks-arrow');
  if (!listEl) return;
  const open = listEl.style.display !== 'none';
  listEl.style.display = open ? 'none' : 'block';
  if (arrowEl) arrowEl.textContent = open ? '▸' : '▾';
  if (!open) loadRecordedWalksList();  // reuses loadRecordedWalksList which also populates wbs copy
};

function clearWalkMode() {
  _exitWalkMode();
  // Keep walk layer button active but re-enter drawing state
  if (currentLayer === 'walk') {
    _walkActive = true;
    document.getElementById('walk-clear-btn').classList.remove('visible');
    document.getElementById('walk-mode-toggle').classList.add('visible');
    _attachWalkDraw();
  }
}

// ── Rectangle drag drawing ────────────────────────────────────────────────

function _attachWalkDraw() {
  const mapEl = document.getElementById('map');
  mapEl.addEventListener('mousedown',  _walkMouseDown);
  mapEl.addEventListener('touchstart', _walkTouchStart, { passive: false });
  map.dragging.disable();
}

function _detachWalkDraw() {
  const mapEl = document.getElementById('map');
  mapEl.removeEventListener('mousedown',  _walkMouseDown);
  mapEl.removeEventListener('touchstart', _walkTouchStart);
  document.removeEventListener('mousemove', _walkMouseMove);
  document.removeEventListener('mouseup',   _walkMouseUp);
  document.removeEventListener('touchmove', _walkTouchMove);
  document.removeEventListener('touchend',  _walkTouchEnd);
  map.dragging.enable();
}

function _walkMouseDown(e) {
  if (!_walkActive) return;
  _walkDrawing = true;
  _walkDragStart = { x: e.clientX, y: e.clientY };
  document.addEventListener('mousemove', _walkMouseMove);
  document.addEventListener('mouseup',   _walkMouseUp);
}

function _walkMouseMove(e) {
  if (!_walkDrawing) return;
  const cur = { x: e.clientX, y: e.clientY };
  if (_walkDrawMode === 'circle') _updateWalkCircle(_walkDragStart, cur);
  else _updateWalkRect(_walkDragStart, cur);
}

function _walkMouseUp(e) {
  if (!_walkDrawing) return;
  _walkDrawing = false;
  document.removeEventListener('mousemove', _walkMouseMove);
  document.removeEventListener('mouseup',   _walkMouseUp);
  const cur = { x: e.clientX, y: e.clientY };
  if (_walkDrawMode === 'circle') _finishWalkCircle(_walkDragStart, cur);
  else _finishWalkDraw(_walkDragStart, cur);
}

function _walkTouchStart(e) {
  if (!_walkActive || e.touches.length !== 1) return;
  if (e.target.closest('button, a, input, select, [role="button"]')) return;
  e.preventDefault();
  const t = e.touches[0];
  _walkDrawing = true;
  _walkDragStart = { x: t.clientX, y: t.clientY };
  document.addEventListener('touchmove', _walkTouchMove, { passive: false });
  document.addEventListener('touchend',  _walkTouchEnd);
}

function _walkTouchMove(e) {
  if (!_walkDrawing || e.touches.length !== 1) return;
  e.preventDefault();
  const t = e.touches[0];
  const cur = { x: t.clientX, y: t.clientY };
  if (_walkDrawMode === 'circle') _updateWalkCircle(_walkDragStart, cur);
  else _updateWalkRect(_walkDragStart, cur);
}

function _walkTouchEnd(e) {
  if (!_walkDrawing) return;
  _walkDrawing = false;
  document.removeEventListener('touchmove', _walkTouchMove);
  document.removeEventListener('touchend',  _walkTouchEnd);
  const t = e.changedTouches[0];
  const cur = { x: t.clientX, y: t.clientY };
  if (_walkDrawMode === 'circle') _finishWalkCircle(_walkDragStart, cur);
  else _finishWalkDraw(_walkDragStart, cur);
}

function _updateWalkRect(start, end) {
  const rect = document.getElementById('walk-rect-canvas');
  const mapRect = document.getElementById('map').getBoundingClientRect();
  const x1 = Math.min(start.x, end.x) - mapRect.left;
  const y1 = Math.min(start.y, end.y) - mapRect.top;
  const x2 = Math.max(start.x, end.x) - mapRect.left;
  const y2 = Math.max(start.y, end.y) - mapRect.top;
  rect.style.cssText = `display:block;position:absolute;left:${x1}px;top:${y1}px;width:${x2-x1}px;height:${y2-y1}px;
    border:2px dashed #2d5016;background:rgba(45,80,22,0.12);pointer-events:none;z-index:499;`;
}

function _hideWalkRect() {
  const rect = document.getElementById('walk-rect-canvas');
  if (rect) rect.style.display = 'none';
}

function setWalkDrawMode(mode) {
  _walkDrawMode = mode;
  document.querySelectorAll('.wmt-btn').forEach(btn => {
    const isRect = btn.textContent.includes('Rect');
    btn.classList.toggle('active', mode === 'rect' ? isRect : !isRect);
  });
  _hideWalkRect();
  _hideWalkCircle();
}

function _updateWalkCircle(center, cur) {
  const canvas = document.getElementById('walk-circle-canvas');
  const dx = cur.x - center.x, dy = cur.y - center.y;
  const r = Math.sqrt(dx * dx + dy * dy);
  const mapRect = document.getElementById('map').getBoundingClientRect();
  canvas.style.cssText = `display:block;position:absolute;`
    + `left:${center.x - mapRect.left - r}px;top:${center.y - mapRect.top - r}px;`
    + `width:${r * 2}px;height:${r * 2}px;border-radius:50%;`
    + `border:2px dashed #2d5016;background:rgba(45,80,22,0.12);pointer-events:none;z-index:499;`;
}

function _hideWalkCircle() {
  const el = document.getElementById('walk-circle-canvas');
  if (el) el.style.display = 'none';
}

function _finishWalkCircle(center, end) {
  _hideWalkCircle();
  const dx = end.x - center.x, dy = end.y - center.y;
  const pixelRadius = Math.sqrt(dx * dx + dy * dy);
  if (pixelRadius < 10) return;
  const mapEl   = document.getElementById('map');
  const mapRect = mapEl.getBoundingClientRect();
  const centerLL = map.containerPointToLatLng(
    L.point(center.x - mapRect.left, center.y - mapRect.top)
  );
  // Metres per pixel at centre of map for current zoom
  const p1 = map.containerPointToLatLng(L.point(0, mapRect.height / 2));
  const p2 = map.containerPointToLatLng(L.point(1, mapRect.height / 2));
  const metersPerPixel = _haversineM(p1.lat, p1.lng, p2.lat, p2.lng);
  _buildWalkRoute(null, { center: centerLL, radiusM: pixelRadius * metersPerPixel });
}

function _finishWalkDraw(start, end) {
  _hideWalkRect();
  // Min drag size — ignore tiny accidental clicks
  if (Math.abs(start.x - end.x) < 10 || Math.abs(start.y - end.y) < 10) return;
  // Convert screen coords to lat/lng
  const mapEl   = document.getElementById('map');
  const mapRect = mapEl.getBoundingClientRect();
  const toLatLng = (cx, cy) => map.containerPointToLatLng(
    L.point(cx - mapRect.left, cy - mapRect.top)
  );
  const ll1 = toLatLng(start.x, start.y);
  const ll2 = toLatLng(end.x,   end.y);
  const bounds = L.latLngBounds(ll1, ll2);
  _buildWalkRoute(bounds, null);
}

// ── Build route from selected area ────────────────────────────────────────

function _haversineM(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const f1 = lat1 * Math.PI / 180, f2 = lat2 * Math.PI / 180;
  const df = (lat2 - lat1) * Math.PI / 180;
  const dl = (lng2 - lng1) * Math.PI / 180;
  const a  = Math.sin(df/2)**2 + Math.cos(f1)*Math.cos(f2)*Math.sin(dl/2)**2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
}

// Build walk's stop order: the server's walk_route.tidy_order (the ONE rule —
// nearest-neighbour from stop 1, the southernmost stop _clusterStops puts
// first, then 2-opt: no crossing legs). _nnRoute below is only the fallback
// when the server can't be asked (offline, or a guest session that may not POST).
let _walkTidySeq = 0;       // a newer build/regroup supersedes an older one's await
async function _tidyRoute(stops) {
  if (stops.length < 3) return stops;
  try {
    const r = await fetch('/api/walk/tidy-order', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stops: stops.map(s => ({ lat: s.lat, lng: s.lng })), circular: !!_walkCircular }),
    });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const d = await r.json();
    if (!Array.isArray(d.order) || d.order.length !== stops.length) throw new Error('bad order');
    return d.order.map(i => stops[i]);
  } catch (e) {
    return _nnRoute(stops);
  }
}

function _nnRoute(stops) {
  // Nearest-neighbour TSP starting from first stop (fallback — see _tidyRoute)
  if (!stops.length) return [];
  const unvisited = [...stops];
  const route = [unvisited.shift()];
  while (unvisited.length) {
    const last = route[route.length - 1];
    let bestIdx = 0, bestDist = Infinity;
    for (let i = 0; i < unvisited.length; i++) {
      const d = _haversineM(last.lat, last.lng, unvisited[i].lat, unvisited[i].lng);
      if (d < bestDist) { bestDist = d; bestIdx = i; }
    }
    route.push(unvisited.splice(bestIdx, 1)[0]);
  }
  return route;
}

// Loop / One-way label (batch 15b, Melvin 28 Oct 2026): "Loop" when the last
// stop is within 600 m of stop 1, else "One-way". A LABEL only — the shown line
// still follows the stored circular flag and the stored line, so no walk's line,
// distance or published page changes. Python twin: walk_route.loop_label.
const _WALK_LOOP_LABEL_MAX_M = 600;
function _walkLoopLabel(route) {
  const pts = (route || []).filter(s => s && s.lat != null && s.lng != null);
  if (pts.length < 2) return null;
  const a = pts[0], b = pts[pts.length - 1];
  return _haversineM(a.lat, a.lng, b.lat, b.lng) <= _WALK_LOOP_LABEL_MAX_M ? 'Loop' : 'One-way';
}

// The loop label + hint (on every route render and when a saved walk loads).
function _syncWalkLoopUi() {
  const lbl  = document.getElementById('walk-loop-label');
  const hint = document.getElementById('walk-loop-hint');
  if (lbl) {
    const l = _walkLoopLabel(_activeWalkRoute);
    lbl.textContent = l === 'Loop' ? '🔄 Loop' : l === 'One-way' ? '➡ One-way' : '';
    lbl.style.display = l ? '' : 'none';
  }
  if (!hint) return;
  // Loaded saved walk: say exactly what the view does to the saved line.
  const rt = _savedWalkView && _activeWalkRoute && _activeWalkRoute.length ? _activeWalkRoute : null;
  if (rt && _walkCircular) {
    hint.textContent = _walkLineClosed ? 'Returns to stop 1' : 'Dashed straight leg back to stop 1';
  } else if (rt) {
    const last = _stopLabel(rt[rt.length - 1], rt.length - 1);
    hint.textContent = _walkLineClosed ? `Ends at stop ${last} — leg back to stop 1 not drawn` : 'One-way route';
  } else {
    hint.textContent = _walkCircular ? 'Returns to start' : 'One-way route';
  }
}

// The circular / point-to-point toggle (toggleWalkLoop) was removed in batch
// 15b. PATCH /api/walk/saves/{id}/loop and the stored foragingid.circular flag
// stay; new walks keep the default _walkCircular = true.

// Toxic guard for the walk flow (stop cards, walk sheet list, proximity
// alerts, summary export). Batch 5: it only READS the server's decision (the
// `safety` object from /api/culinary/{name}, app/models/species.py
// safety_decision) through static/js/safety-gate.js — it never re-derives the
// rule from toxicity_severity. Missing decision → fails closed (⚠ toxicity
// unknown). Returns { ok, isToxic, label, safety } — label is the safety
// label ('' for none; '⚠ caution' for caution, where ok is true).
function _culinaryGate(safety) {
  const d = SafetyGate.decision(safety);
  return { ok: SafetyGate.allowed(d), isToxic: d.level === 'deadly' || d.level === 'toxic',
           label: d.label || '', safety: d };
}

// Warning badge for a blocked species (shared by all walk sites).
function _culinaryGateBadge(gate) {
  if (gate.ok) return '';
  return SafetyGate.badge(gate.safety);
}

// Culinary profile + safety decision for each species on a walk, from one
// request: /api/culinary/{name} serves `safety`, stored on the entry as
// _safety (null when it could not be read — _culinaryGate fails closed).
async function _fetchWalkEnrich(names) {
  const enrichMap = {};
  await Promise.allSettled(names.map(async name => {
    let entry = {};
    try {
      const r = await fetch(`/api/culinary/${encodeURIComponent(name)}`);
      if (r.ok) entry = await r.json();
    } catch (_) {}
    entry._safety = (entry && entry.safety) || null;
    enrichMap[name] = entry;
  }));
  return enrichMap;
}

// ── Stops: centroid clustering ────────────────────────────────────────────
// A pin joins an existing stop only if it is within R metres of that stop's
// CENTRE; the centre is recomputed (mean lat/lng) as pins join. Distance is
// always measured to the centre, never pin-to-pin, so stops cannot chain.
// One stop = one waypoint holding every species found there. Field notes are
// never clustered — each stays its own stop.
function _clusterStops(pins, radiusM) {
  const obsPins  = pins.filter(x => !x.p.is_note)
                       .slice().sort((a, b) => (a.lat - b.lat) || (a.lng - b.lng));
  const notePins = pins.filter(x => x.p.is_note);
  const stops = [];
  for (const pin of obsPins) {
    let best = null, bestD = Infinity;
    for (const s of stops) {
      const d = _haversineM(s.lat, s.lng, pin.lat, pin.lng);
      if (d < bestD) { bestD = d; best = s; }
    }
    if (best && bestD <= radiusM) {
      best.pins.push(pin);
      best.lat = best.pins.reduce((t, x) => t + x.lat, 0) / best.pins.length;
      best.lng = best.pins.reduce((t, x) => t + x.lng, 0) / best.pins.length;
      if (!best.species.includes(pin.p.species_primary)) best.species.push(pin.p.species_primary);
      if (pin.p.id != null) best.obs_ids.push(pin.p.id);
    } else {
      stops.push({
        lat: pin.lat, lng: pin.lng,
        p: pin.p,                      // representative pin (first to join) — kept for
                                       // code that still reads s.p (proximity, export)
        pins: [pin],
        species: [pin.p.species_primary],
        obs_ids: pin.p.id != null ? [pin.p.id] : [],
      });
    }
  }
  // Second pass — centre drift. A centre moves as later pins join, so an early
  // pin can end up further than R from its stop's FINAL centre. Any such pin
  // moves to the nearest other stop within R, or starts a new stop; centres are
  // then recomputed and the check repeats until nothing moves (capped — the
  // Gresgen test boxes settle in ≤ 4 passes).
  for (let pass = 0; pass < 10; pass++) {
    let moved = 0;
    for (const s of stops.slice()) {
      for (const pin of s.pins.slice()) {
        if (_haversineM(s.lat, s.lng, pin.lat, pin.lng) <= radiusM) continue;
        let best = null, bestD = Infinity;
        for (const t of stops) {
          if (t === s || !t.pins.length) continue;
          const d = _haversineM(t.lat, t.lng, pin.lat, pin.lng);
          if (d < bestD) { bestD = d; best = t; }
        }
        s.pins.splice(s.pins.indexOf(pin), 1);
        if (best && bestD <= radiusM) best.pins.push(pin);
        else stops.push({ lat: pin.lat, lng: pin.lng, p: pin.p, pins: [pin], species: [], obs_ids: [] });
        moved++;
      }
    }
    for (let i = stops.length - 1; i >= 0; i--) if (!stops[i].pins.length) stops.splice(i, 1);
    for (const s of stops) {
      s.lat = s.pins.reduce((t, x) => t + x.lat, 0) / s.pins.length;
      s.lng = s.pins.reduce((t, x) => t + x.lng, 0) / s.pins.length;
    }
    if (!moved) break;
  }
  // Rebuild each stop's species / obs ids / representative pin from its final pins.
  for (const s of stops) {
    s.p       = s.pins[0].p;
    s.species = [...new Set(s.pins.map(x => x.p.species_primary))];
    s.obs_ids = s.pins.filter(x => x.p.id != null).map(x => x.p.id);
  }
  for (const n of notePins) {
    stops.push({ lat: n.lat, lng: n.lng, p: n.p, pins: null, species: [], obs_ids: [] });
  }
  return stops;
}

// Species at a stop (works for clustered stops, loaded walks and old shapes).
// Stop number shown on the map, card and export. Loaded saved walks carry the
// server's label ("7", "7a" for a stop that joined by route proximity —
// walk_membership.py); every other route is numbered by position.
function _stopLabel(s, i) {
  return (s && s.label) ? String(s.label) : String(i + 1);
}

function _stopSpecies(s) {
  if (s.p && s.p.is_note) return [];
  if (Array.isArray(s.species) && s.species.length) return s.species.filter(Boolean);
  return s.p && s.p.species_primary ? [s.p.species_primary] : [];
}

// Repeat rule — the ONE implementation, shared by the walk panel stop cards and
// the summary export: a species gets its full section at the first stop it
// appears at in walk order; every later stop lists it as a compact "Also here"
// line pointing back to that stop (label as displayed, "7a" included).
// Returns one {label, full: [names], repeats: [{name, first_label}]} per stop.
// (The static experience export can't load this file — its Python mirror is
// the st["repeat"] loop in scripts/experience_export/export.py.)
// A saved stop whose photos have all left the walk (excluded, or no longer
// confirmed) has no species: it is hidden from the panel and the map (batch
// 15b, Melvin 28 Oct 2026; numbering kept), and Save changes / Renumber /
// Re-route drop it. Note stops are never empty.
function _walkStopEmpty(stop) {
  return !!stop && !(stop.p && stop.p.is_note) && _stopSpecies(stop).length === 0;
}

function _walkRepeatSplit(route) {
  const firstStopOf = {};
  return (route || []).map((stop, i) => {
    const label = _stopLabel(stop, i);
    const full = [], repeats = [];
    for (const name of _stopSpecies(stop)) {
      if (firstStopOf[name] === undefined) { firstStopOf[name] = label; full.push(name); }
      else if (firstStopOf[name] !== label) repeats.push({ name, first_label: firstStopOf[name] });
    }
    return { label, full, repeats };
  });
}

// Dashed (straight) legs of a saved line: vertex ranges [[a, b], …], validated
// and merged. meta.straight_ranges, or legacy meta.straight_from sf = [[sf, n-1]].
// Same reading rule as straight_ranges() in app/services/walk_route.py.
function _walkStraightRangesOf(meta, n) {
  meta = meta || {};
  let raw = [];
  if (Array.isArray(meta.straight_ranges)) raw = meta.straight_ranges;
  else if (Number.isInteger(meta.straight_from)) raw = [[meta.straight_from, n - 1]];
  const flags = new Array(Math.max(n - 1, 0)).fill(false);
  for (const r of raw) {
    if (!Array.isArray(r) || r.length !== 2 || !Number.isInteger(r[0]) || !Number.isInteger(r[1])) continue;
    if (!(r[0] >= 0 && r[0] < r[1] && r[1] <= n - 1)) continue;
    for (let k = r[0]; k < r[1]; k++) flags[k] = true;
  }
  const out = [];
  let start = null;
  flags.concat([false]).forEach((f, k) => {
    if (f && start === null) start = k;
    else if (!f && start !== null) { out.push([start, k]); start = null; }
  });
  return out;
}

// Walk panel species badge (full card AND compact repeat line). Blocked by the
// toxic guard → the ☠ / ⚠ toxicity-unknown warning, never an edibility label;
// otherwise the edibility verdict.
function _walkEdibBadge(gate, edib) {
  // Blocked with a ☠ / ⚠ label → the label; blocked without one (inedible) → the verdict badge.
  if (!gate.ok && gate.label) return _culinaryGateBadge(gate);
  if (!edib) return '';
  return `<span style="font-size:0.68rem;padding:1px 6px;border-radius:4px;font-weight:600;
             background:${edib==='edible'?'#d1f5da':edib==='toxic'?'#dc2626':edib==='inedible'?'#fef3c7':edib==='medicinal'?'#e0e7ff':'#f3f3f3'};
             color:${edib==='edible'?'#166534':edib==='toxic'?'#fff':edib==='inedible'?'#854d0e':edib==='medicinal'?'#3730a3':'#555'}">
             ${_esc(edib)}</span>`;
}

// ORS public directions API: max 50 coordinates per request. A circular walk
// sends the start again at the end, so it can hold one stop fewer.
function _walkMaxStops() { return _walkCircular ? 49 : 50; }

// ── Build route from selected area ────────────────────────────────────────

async function _buildWalkRoute(bounds, circle, suppressFitBounds = false) {
  // Remember selection for re-routing (toggle circular)
  _lastWalkBounds = bounds;
  _lastWalkCircle = circle;
  // Collect visible pins in the selected area (rect or circle)
  const _inArea = (lat, lng) => circle
    ? _haversineM(circle.center.lat, circle.center.lng, lat, lng) <= circle.radiusM
    : bounds.contains([lat, lng]);

  const pins = [];
  for (const f of allFeatures) {
    const [lng, lat] = f.geometry.coordinates;
    if (!_inArea(lat, lng)) continue;
    const p = f.properties;
    if (!p.species_primary) continue;
    if (!_passesFilters(p)) continue;
    pins.push({ p, lat, lng });          // every pin — grouping happens in _clusterStops
  }

  // Note pins within the area
  for (const f of noteFeatures) {
    const [lng, lat] = f.geometry.coordinates;
    if (!_inArea(lat, lng)) continue;
    pins.push({ p: { ...f.properties, species_primary: null, is_note: true }, lat, lng });
  }

  if (!pins.length) {
    alert('No confirmed sightings or notes found in the selected area. Try a larger area.');
    return;
  }

  _walkLastPins     = pins;
  _walkStraightLine = false;
  _syncWalkRadiusUi(true);
  const _seq = ++_walkTidySeq;
  const route = await _tidyRoute(_clusterStops(pins, _walkStopRadiusM));
  if (_seq !== _walkTidySeq) return;          // a newer build/regroup started meanwhile
  _walkSelected     = route;
  _activeWalkRoute  = route;

  // false = a newer route/regroup started meanwhile; that one renders the panel.
  if (!(await _routeWalk({ suppressFitBounds }))) return;

  // ── Culinary enrichment (+ toxicity, for the walk panel's toxic guard) ─────
  const uniqueSpecies = [...new Set(route.flatMap(_stopSpecies))];
  const enrichMap = await _fetchWalkEnrich(uniqueSpecies);

  // ── Show panel ─────────────────────────────────────────────────────────────
  _closeTabPanels();
  document.getElementById('walk-clear-btn').classList.add('visible');
  document.getElementById('walk-mode-toggle').classList.remove('visible');
  // Open the bottom sheet on both phone and laptop (renderWalkPanel also ensures this)
  const _wbsRbw = document.getElementById('walk-bottom-sheet');
  if (_wbsRbw && !_wbsRbw.classList.contains('wbs-open')) {
    _wbsRbw.classList.add('wbs-open');
    const _chevRbw = document.getElementById('wbs-chevron');
    if (_chevRbw) _chevRbw.textContent = '▾';
  }

  _startProxWatch();            // 10a.5 — begin proximity watch if field mode on
  _activeWalkEnrich = enrichMap;
  renderWalkPanel(route, enrichMap);
  // The area is drawn and the walk built: give the map back (pan / zoom / tap).
  // The rectangle/circle draw kept map dragging disabled after a walk was built
  // and saved — "the map froze" (Melvin 20 Oct 2026). "← Draw new area"
  // (clearWalkMode) attaches the draw again.
  _detachWalkDraw();
}

// ── Routing for the current _activeWalkRoute (new, regrouped or loaded) ────
// opts.savedGeom  — draw this saved LineString instead of calling ORS
// opts.keepSaved  — keep the saved distance/duration (loaded walks)
// Never falls back to a straight line on its own: on a stop-cap or ORS failure
// only the numbered stops are drawn and _walkRouteStatus says why; the
// straight line appears only after the user picks it (walkUseStraightLine).
async function _routeWalk(opts = {}) {
  const seq   = ++_walkBuildSeq;
  const route = _activeWalkRoute || [];
  if (!opts.keepSaved) { _walkOrsDistM = 0; _walkOrsDurMin = 0; }
  _walkRouteGeom   = null;
  _walkStraightRanges = [];
  _walkOrsFallback = false;

  let status;
  if (route.length < 2) {
    status = { kind: 'single' };
  } else if (opts.savedGeom && Array.isArray(opts.savedGeom.coordinates)) {
    _walkRouteGeom = opts.savedGeom;   // exactly the shape that was saved — no ORS call
    _walkStraightRanges = _walkStraightRangesOf(opts.routeMeta, opts.savedGeom.coordinates.length);
    status = { kind: 'ok' };
  } else if (route.length > _walkMaxStops()) {
    status = { kind: 'capped', n: route.length, max: _walkMaxStops() };
  } else {
    const res = await _fetchOrsRoute(route);
    if (seq !== _walkBuildSeq) return false;   // a newer regroup/route superseded this one
    if (res.geom) {
      _walkRouteGeom = res.geom;
      if (!opts.keepSaved) { _walkOrsDistM = res.distM; _walkOrsDurMin = res.durMin; }
      status = { kind: 'ok' };
    } else {
      status = { kind: 'failed', reason: res.reason };
    }
  }
  if (seq !== _walkBuildSeq) return false;
  _walkRouteStatus = status;
  _walkOrsFallback = status.kind !== 'ok' && status.kind !== 'single';
  _drawWalkLayer(opts.suppressFitBounds);
  _renderWalkRouteStatus();
  return true;
}

// ORS call with the real failure reason. Returns {geom, distM, durMin} or {reason}.
async function _fetchOrsRoute(route) {
  const coords = route.map(s => [s.lng, s.lat]);      // ORS expects [lng, lat]
  if (_walkCircular) coords.push(coords[0]);          // close the loop
  let resp;
  try {
    resp = await fetch('/api/walk/ors-route', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ coordinates: coords }),
    });
  } catch (e) {
    return { reason: `network error — the app server could not be reached (${e.message})` };
  }
  if (!resp.ok) {
    let detail = '';
    try { detail = (await resp.json()).detail || ''; } catch (_) {}
    return { reason: `app server error HTTP ${resp.status}${detail ? ' — ' + detail : ''}` };
  }
  let data;
  try { data = await resp.json(); } catch (_) { return { reason: 'unreadable response from the routing proxy' }; }
  if (data.fallback) {
    const raw = String(data.reason || 'unknown ORS error');
    let reason = raw;
    if (/429/.test(raw))                reason = `rate limit reached (${raw}) — wait a minute, then Retry`;
    else if (/timed out/i.test(raw))    reason = `ORS timed out (${raw})`;
    else if (/not configured/i.test(raw)) reason = `${raw} — add the key in Settings → APIs`;
    else if (/40[04]/.test(raw))        reason = `ORS could not route between these stops (${raw})`;
    return { reason };
  }
  const feat = data.features && data.features[0];
  if (!feat || !feat.geometry || !Array.isArray(feat.geometry.coordinates)) {
    return { reason: 'ORS returned no route geometry' };
  }
  const sum = (feat.properties && feat.properties.summary) || {};
  return {
    geom:   feat.geometry,
    distM:  sum.distance || 0,
    durMin: Math.round((sum.duration || 0) / 60),
  };
}

// Draw numbered stops + whatever line the current status allows.
function _drawWalkLayer(suppressFitBounds) {
  const route = _activeWalkRoute || [];
  if (_walkRouteLayer) map.removeLayer(_walkRouteLayer);
  _walkRouteLayer = L.layerGroup().addTo(map);
  _walkRouteLayer._walkBuildSeq = _walkBuildSeq;   // which route build drew it (loadSavedWalk's stale check)
  // Point-to-point: flag the start (first stop) and the finish (last saved stop —
  // where the line ends) so the one-way shape is unmistakable on the map.
  let finishIdx = -1;
  if (!_walkCircular && route.length > 1) {
    for (let k = route.length - 1; k >= 0; k--) { if (route[k].origin !== 'joined') { finishIdx = k; break; } }
  }
  const latLngs = route.map((s, i) => {
    if (_walkStopEmpty(s)) return [s.lat, s.lng];   // no marker for an empty stop (batch 15b)
    // Stops that joined a saved walk by route proximity ("7a") are a lighter green.
    const bg = s.p.is_note ? '#f59e0b' : (s.origin === 'joined' ? '#5f8f35' : '#2d5016');
    const n  = _stopSpecies(s).length;
    // Edit walk: a stop marked for removal gets a red ring (batch 15b).
    const ring = (_walkPinSel && !s.p.is_note && _walkStopMarked(s)) ? '#dc2626' : 'white';
    const stopIcon = L.divIcon({
      className: '',
      html: `<div style="width:28px;height:28px;border-radius:50%;background:${bg};
                 color:white;font-size:0.72rem;font-weight:700;
                 display:flex;align-items:center;justify-content:center;
                 border:2px solid ${ring};box-shadow:0 2px 6px rgba(0,0,0,.3)${ring !== 'white' ? ',0 0 0 3px #dc2626' : ''};position:relative">${_esc(_stopLabel(s, i))}${
                 (finishIdx >= 0 && (i === 0 || i === finishIdx))
                   ? `<span title="${i === 0 ? 'Start' : 'Finish'}" style="position:absolute;top:-13px;right:-12px;font-size:15px;line-height:1">${i === 0 ? '🚩' : '🏁'}</span>`
                   : ''}</div>`,
      iconSize: [28, 28], iconAnchor: [14, 14],
    });
    const stopMk = L.marker([s.lat, s.lng], { icon: stopIcon }).addTo(_walkRouteLayer);
    // Tap (touch) / hover (desktop): the stop's species, names rule.
    stopMk.bindTooltip(s.p.is_note ? 'Field note'
      : `<strong>Stop ${_esc(_stopLabel(s, i))}</strong>` + (n ? '<br>' + _stopSpecies(s).map(nm => spNameHtml(nm, _spCommonFor(nm))).join('<br>') : ''),
      { direction: 'top', offset: [0, -14], className: 'walk-pin-label' });
    // Edit walk: tapping a stop marks the whole stop for removal (batch 15b).
    if (!s.p.is_note) stopMk.on('click', () => _walkStopToggle(s));
    return [s.lat, s.lng];
  });

  if (latLngs.length > 1) {
    if (_walkRouteGeom) {
      const ll = _walkRouteGeom.coordinates.map(([lng, lat]) => [lat, lng]);
      // Routed parts solid; the straight legs (no mapped footpath) dashed and labelled.
      let at = 0;
      const solid = (a, b) => { if (b > a) L.polyline(ll.slice(a, b + 1), { color: '#2d5016', weight: 3.5, opacity: 0.85 })
                                             .addTo(_walkRouteLayer); };
      for (const [a, b] of _walkStraightRanges) {
        solid(at, a);
        L.polyline(ll.slice(a, b + 1), { color: '#2d5016', weight: 3, dashArray: '7 6', opacity: 0.85 })
          .bindTooltip('Straight line between stops — no mapped footpath here', { sticky: true })
          .addTo(_walkRouteLayer);
        at = b;
      }
      solid(at, ll.length - 1);
    } else if (_walkStraightLine) {
      // Chosen by the user after an ORS failure — dashed, and labelled as such.
      const sl = _walkCircular ? [...latLngs, latLngs[0]] : latLngs;
      L.polyline(sl, { color: '#2d5016', weight: 2.5, dashArray: '6 6', opacity: 0.7 })
        .bindTooltip('Straight line between stops — not a walking route', { sticky: true })
        .addTo(_walkRouteLayer);
    }
  }
  if (!suppressFitBounds && latLngs.length) {
    map.fitBounds(L.latLngBounds(latLngs), { padding: [50, 50], maxZoom: 15 });
  }
}

// Status line under the route controls: stop cap, ORS failure, straight line.
function _renderWalkRouteStatus() {
  const el = document.getElementById('walk-ors-note');
  if (!el) return;
  const st = _walkRouteStatus;
  el.classList.remove('visible', 'walk-route-warn');
  el.innerHTML = '';
  if (!st || st.kind === 'ok' || st.kind === 'single') return;
  el.classList.add('visible', 'walk-route-warn');
  if (st.kind === 'capped') {
    const loopNote = _walkCircular ? ' (a circular walk uses one extra point to return to the start)' : '';
    const canRegroup = !!_walkLastPins;
    el.innerHTML =
      `<strong>${st.n} stops — max ${st.max}${_esc(loopNote)}.</strong> ` +
      `Increase the stop radius or select a smaller area. No route was drawn.` +
      (canRegroup
        ? `<br><button class="walk-route-act" onclick="walkIncreaseRadius()">↔ Increase radius</button>`
        : '');
  } else if (st.kind === 'failed') {
    el.innerHTML =
      `<strong>Walking route not drawn:</strong> ${_esc(st.reason || 'unknown error')}` +
      (_walkStraightLine
        ? `<br><em>Showing a straight line between stops — not a walking route.</em>`
        : '') +
      `<br><button class="walk-route-act" onclick="walkRetryRoute()">↻ Retry</button>` +
      (_walkStraightLine ? '' :
        `<button class="walk-route-act" onclick="walkUseStraightLine()">Draw straight line instead</button>`);
  }
}

function walkUseStraightLine() {
  _walkStraightLine = true;
  _drawWalkLayer(true);
  _renderWalkRouteStatus();
  if (_activeWalkRoute) renderWalkPanel(_activeWalkRoute, _activeWalkEnrich || {});
}

async function walkRetryRoute() {
  _walkStraightLine = false;
  if (await _routeWalk({ suppressFitBounds: true }) && _activeWalkRoute) {
    renderWalkPanel(_activeWalkRoute, _activeWalkEnrich || {});
  }
}

// ── Stop radius slider ─────────────────────────────────────────────────────
function _syncWalkRadiusUi(enabled) {
  const inp = document.getElementById('walk-radius');
  const val = document.getElementById('walk-radius-val');
  if (inp) { inp.value = String(_walkStopRadiusM); inp.disabled = !enabled; }
  if (val) val.textContent = `${_walkStopRadiusM} m`;
  const wrap = document.getElementById('walk-radius-wrap');
  if (wrap) wrap.style.opacity = enabled ? '1' : '0.5';
}

function onWalkRadiusInput(v) {
  _walkStopRadiusM = Math.max(10, Math.min(100, parseInt(v, 10) || 30));
  const val = document.getElementById('walk-radius-val');
  if (val) val.textContent = `${_walkStopRadiusM} m`;
  if (!_walkLastPins) return;              // loaded walk: stops are fixed
  // Regroup immediately on screen; debounce the ORS call while dragging.
  clearTimeout(_walkRadiusTimer);
  _walkRadiusTimer = setTimeout(_regroupWalk, 600);
}

async function _regroupWalk() {
  if (!_walkLastPins) return;
  _walkStraightLine = false;
  const _seq = ++_walkTidySeq;
  const route = await _tidyRoute(_clusterStops(_walkLastPins, _walkStopRadiusM));
  if (_seq !== _walkTidySeq) return;          // a newer build/regroup started meanwhile
  _walkSelected    = route;
  _activeWalkRoute = route;
  if (await _routeWalk({ suppressFitBounds: true })) {
    renderWalkPanel(route, _activeWalkEnrich || {});
  }
}

// One tap: smallest radius (5 m steps, ≤ 100 m) that brings stops under the cap.
function walkIncreaseRadius() {
  if (!_walkLastPins) return;
  const max = _walkMaxStops();
  for (let r = _walkStopRadiusM + 5; r <= 100; r += 5) {
    if (_clusterStops(_walkLastPins, r).length <= max) {
      _walkStopRadiusM = r;
      _syncWalkRadiusUi(true);
      clearTimeout(_walkRadiusTimer);
      _regroupWalk();
      return;
    }
  }
  const n100 = _clusterStops(_walkLastPins, 100).length;
  _walkStopRadiusM = 100;
  _syncWalkRadiusUi(true);
  _regroupWalk();
  alert(`Even at 100 m there are ${n100} stops (max ${max}). Select a smaller area.`);
}

