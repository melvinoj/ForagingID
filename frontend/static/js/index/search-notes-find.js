// ── Patch setLayer to handle the walk modal view ──────────────────────────
// Near me / Find are no longer setLayer modes — they live in the discover
// view opened by the search chip (showDiscoverView/_exitDiscoverView).
const _origSetLayer = setLayer;
const _LAYER_BTNS = ['pins','clusters','heatmap','walk'];
setLayer = function(mode, _fromZoom) {
  if (mode === 'walk') {
    if (_walkActive) {
      // Re-tap while in walk mode → exit
      _exitWalkMode();
      const walkBtn = document.getElementById('btn-layer-walk');
      if (walkBtn) walkBtn.classList.remove('active');
      return;
    }
    // Entering walk mode
    _LAYER_BTNS.forEach(m => {
      const btn = document.getElementById(`btn-layer-${m}`);
      if (btn) btn.classList.toggle('active', m === mode);
    });
    _exitDiscoverView();
    // Switch to pins first (walk draws on pins); _enterWalkMode calls _applyLayer after setting _walkActive
    currentLayer = 'pins';
    _enterWalkMode();
    // Close the config sheet on all devices — on mobile it's a bottom sheet
    // that would otherwise compete with #walk-bottom-sheet for the same space.
    closeConfigSheet();
    // _enterWalkMode adds wbs-active (handle peeks) then wbs-open (sheet slides up) on both
    if (!isMobile()) {
      _closeTabPanels();
      document.getElementById('filter-view').style.display = 'none';
      document.getElementById('detail-view').style.display = 'none';
    }
    return;
  }
  // Exiting walk / discover mode via another layer button
  if (_walkActive) { _exitWalkMode(); }
  _exitDiscoverView();
  _origSetLayer(mode, _fromZoom);
};

// ── Feature 2: Search bar ─────────────────────────────────────────────────
let _searchTimer = null;
let _searchItems = [];

function onMapSearchInput(val) {
  const clearBtn  = document.getElementById('map-search-clear');
  const dropdown  = document.getElementById('map-search-dropdown');
  if (clearBtn) clearBtn.style.display = val ? 'inline' : 'none';
  clearTimeout(_searchTimer);
  if (!val.trim()) { dropdown.style.display = 'none'; _clearSearchFilter(); return; }

  // Species first (instant, no debounce)
  const q = val.toLowerCase();
  const hits = _allSpeciesList.filter(sp => {
    if (sp.scientific_name.toLowerCase().includes(q)) return true;
    if ((sp.preferred_common_name || '').toLowerCase().includes(q)) return true;
    return (sp.common_names || []).some(cn => cn.toLowerCase().includes(q));
  }).slice(0, 5);
  if (hits.length) {
    _showSearchDrop(hits.map(sp => ({
      type: 'species', label: sp.scientific_name,
      sub: spPickCommon(sp.preferred_common_name, sp.common_names), data: sp,
    })));
    return;
  }
  // Geocode after debounce
  _searchTimer = setTimeout(() => _geocodeSearch(val), 300);
}

function _showSearchDrop(items) {
  _searchItems = items;
  const dd = document.getElementById('map-search-dropdown');
  if (!items.length) { dd.style.display = 'none'; return; }
  dd.innerHTML = items.map((it, i) => {
    const typeTag = `<span class="msearch-type">${it.type === 'species' ? 'species' : 'place'}</span>`;
    const sub = it.sub ? `<span class="msearch-sub">${_esc(it.sub)}</span>` : '';
    return `<div class="map-search-item" onclick="_selectSearchItem(${i})">
      <span>${_esc(it.label)}</span>${sub}${typeTag}
    </div>`;
  }).join('');
  dd.style.display = 'block';
}

async function _geocodeSearch(q) {
  try {
    const url = `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(q)}&format=json&limit=3`;
    const r = await fetch(url, { headers: { 'Accept-Language': 'en' } });
    if (!r.ok) return;
    const results = await r.json();
    _showSearchDrop(results.slice(0, 3).map(res => {
      const parts = res.display_name.split(',');
      return {
        type: 'place',
        label: parts.slice(0, 2).join(',').trim(),
        sub: parts.slice(2, 4).join(',').trim(),
        lat: parseFloat(res.lat), lng: parseFloat(res.lon),
      };
    }));
  } catch (_) {}
}

function _selectSearchItem(i) {
  const item = _searchItems[i];
  if (!item) return;
  const input   = document.getElementById('map-search-input');
  const dropdown = document.getElementById('map-search-dropdown');
  dropdown.style.display = 'none';
  input.value = item.label;
  if (item.type === 'species') {
    filterState.species.clear();
    filterState.species.add(item.data.scientific_name);
    _updateFilterFab();
    renderMarkers();
    // Zoom to where this species' pins are using the global heat data (bbox-independent).
    // moveend after fitBounds will reload allFeatures for the new viewport.
    const spName = item.data.scientific_name;
    const pts = _heatAll.filter(pt => pt[2] === spName);
    if (pts.length) {
      const lats = pts.map(pt => pt[0]);
      const lngs = pts.map(pt => pt[1]);
      map.fitBounds(
        [[Math.min(...lats), Math.min(...lngs)], [Math.max(...lats), Math.max(...lngs)]],
        { maxZoom: 14, padding: [50, 50], animate: true }
      );
    }
  } else {
    map.flyTo([item.lat, item.lng], 13, { duration: 1.2, easeLinearity: 0.4 });
  }
}

function clearMapSearch() {
  const input = document.getElementById('map-search-input');
  const clearBtn = document.getElementById('map-search-clear');
  const dropdown = document.getElementById('map-search-dropdown');
  input.value = '';
  if (clearBtn) clearBtn.style.display = 'none';
  dropdown.style.display = 'none';
  _clearSearchFilter();
}

function _clearSearchFilter() {
  if (filterState.species.size > 0) {
    filterState.species.clear();
    _updateFilterFab();
    renderMarkers();
  }
}

// Close search dropdown when clicking elsewhere
document.addEventListener('click', function(e) {
  const wrap = document.getElementById('map-search-wrap');
  if (wrap && !wrap.contains(e.target)) {
    const dd = document.getElementById('map-search-dropdown');
    if (dd) dd.style.display = 'none';
  }
});

// ── Feature 3: Note pins ──────────────────────────────────────────────────
let noteFeatures     = [];
let _noteSpeciesTags = [];
let _notePlacing     = false;  // true while pan-to-place is active
const noteGroup      = L.layerGroup().addTo(map);

function makeNoteIcon(size) {
  const s = size || 16;
  return L.divIcon({
    className: '',
    html: `<div style="width:${s}px;height:${s}px;border-radius:50%;background:#f59e0b;
               border:2px solid white;box-shadow:0 1px 4px rgba(0,0,0,.35)"></div>`,
    iconSize: [s, s], iconAnchor: [s/2, s/2],
  });
}

// Zoom-proportional note pin size: 4 px at zoom ≤ 7, 16 px at zoom ≥ 19, linear.
// Keeps pins visible over the heatmap at all zoom levels without dominating
// when zoomed out to regional/national view.
function _noteIconSize() {
  return Math.max(4, Math.min(16, map.getZoom() - 3));
}

// Rescale existing note markers in-place on zoom — no clearLayers/re-add,
// so renderMarkers() is not triggered unnecessarily.
function _rescaleNotePins() {
  const icon = makeNoteIcon(_noteIconSize());
  noteGroup.eachLayer(function(mk) { mk.setIcon(icon); });
}
map.on('zoomend', _rescaleNotePins);   // keep note pin size proportional to zoom

async function loadNotes() {
  try {
    const r = await fetch('/api/notes/geojson');
    if (!r.ok) return;
    const geo = await r.json();
    noteFeatures = geo.features || [];
    renderNotes();
  } catch (_) {}
}

function renderNotes() {
  noteGroup.clearLayers();
  for (const f of noteFeatures) {
    const [lng, lat] = f.geometry.coordinates;
    const p = f.properties;
    const mk = L.marker([lat, lng], { icon: makeNoteIcon(_noteIconSize()) });
    mk.on('click', function(e) {
      L.DomEvent.stopPropagation(e);
      showNoteDetail(p, lat, lng);
    });
    noteGroup.addLayer(mk);
  }
  // Refresh heat layer to include notes
  if (typeof renderMarkers === 'function') renderMarkers();
}

function showNoteDetail(p, lat, lng) {
  showDetailView({ species_primary: '📝 Field Note', id: null });
  const scroll = document.getElementById('detail-scroll');
  const date = new Date(p.created_at).toLocaleDateString('en-GB',
    { day: 'numeric', month: 'short', year: 'numeric' });
  const tags = (p.species_tags || []).map(t =>
    `<span class="note-sp-badge">${_esc(t)}</span>`).join(' ');
  scroll.innerHTML = `
    <div style="padding:12px 14px 16px">
      <div style="margin-bottom:6px">
        <span class="note-badge">📝 Field Note</span>
        <span style="font-size:0.74rem;color:#888;margin-left:6px">${date}</span>
      </div>
      <div style="font-size:0.73rem;color:#888;margin-bottom:8px">
        ${lat.toFixed(5)}, ${lng.toFixed(5)}
      </div>
      ${tags ? `<div style="margin-bottom:10px;display:flex;flex-wrap:wrap;gap:3px">${tags}</div>` : ''}
      <div style="font-size:0.88rem;color:#222;line-height:1.55;white-space:pre-wrap">${_esc(p.text)}</div>
      <button onclick="deleteNote(${p.id})"
        style="margin-top:14px;font-size:0.74rem;padding:4px 12px;
               border:1px solid #dc2626;color:#dc2626;background:none;
               border-radius:4px;cursor:pointer">Delete note</button>
    </div>`;
  if (isMobile()) openSidebar();
}

async function deleteNote(id) {
  if (!confirm('Delete this note?')) return;
  try {
    const r = await fetch(`/api/notes/${id}`, { method: 'DELETE' });
    if (r.ok) {
      noteFeatures = noteFeatures.filter(f => f.properties.id !== id);
      renderNotes();
      closeSidebar();
    }
  } catch (_) {}
}

// ── Note panel ────────────────────────────────────────────────────────────
let _notePanelOpen  = false;
let _notePinLat     = null;   // latitude locked after pin placement
let _notePinLng     = null;   // longitude locked after pin placement
let _notePendingMk  = null;   // temporary amber marker shown while form is open

function toggleNotePanel() {
  // Second tap while flow is active → cancel everything
  if (_notePlacing || _notePinLat !== null) { _cancelNote(); return; }
  if (_walkActive) return;

  // Close the config sheet while placing a note — the crosshair sits at
  // map-center and would be hidden behind the sheet otherwise.
  closeConfigSheet();
  document.getElementById('rp-pane').classList.remove('rp-open');
  document.getElementById('drawer-scrim').classList.remove('show');

  // Enter pin-placement mode: crosshair + bar appear, user pans freely.
  // Pin is placed only when the user clicks "Select location" (centre of view).
  _notePlacing = true;
  const btn = document.getElementById('btn-layer-note');
  if (btn) btn.classList.add('active');
  document.getElementById('note-crosshair').classList.add('visible');
  document.getElementById('note-placing-bar').classList.add('visible');
}

function _placeNotePinAtCenter() {
  const c = map.getCenter();
  _placeNotePin(c.lat, c.lng);
}

function _placeNotePinAtClick(e) {
  if (!_notePlacing) return;
  _placeNotePin(e.latlng.lat, e.latlng.lng);
}

function _placeNotePin(lat, lng) {
  _notePlacing = false;
  _notePinLat  = lat;
  _notePinLng  = lng;
  map.off('click', _placeNotePinAtClick);

  document.getElementById('note-crosshair').classList.remove('visible');
  document.getElementById('note-placing-bar').classList.remove('visible');

  // Temporary amber marker so user can see the chosen location
  if (_notePendingMk) map.removeLayer(_notePendingMk);
  _notePendingMk = L.marker([lat, lng], { icon: makeNoteIcon(20) }).addTo(map);

  // Show locked location in the form
  const locEl = document.getElementById('note-placed-loc');
  if (locEl) { locEl.textContent = `📍 ${lat.toFixed(5)}, ${lng.toFixed(5)}`; locEl.style.display = 'block'; }

  // Open form panel
  _notePanelOpen = true;
  document.getElementById('panel-note').style.display = 'block';
  const btn = document.getElementById('btn-layer-note');
  if (btn) btn.classList.add('active');
  setTimeout(() => { const ta = document.getElementById('note-text-input'); if (ta) ta.focus(); }, 80);
}

function _cancelNote() {
  _notePlacing = false;
  _notePinLat  = null;
  _notePinLng  = null;

  document.getElementById('note-crosshair').classList.remove('visible');
  document.getElementById('note-placing-bar').classList.remove('visible');
  document.getElementById('panel-note').style.display = 'none';
  _notePanelOpen = false;

  if (_notePendingMk) { map.removeLayer(_notePendingMk); _notePendingMk = null; }

  // Reset form fields
  const ta = document.getElementById('note-text-input');
  if (ta) ta.value = '';
  _noteSpeciesTags = [];
  _renderNoteTags();
  const inp = document.getElementById('note-species-input');
  if (inp) inp.value = '';
  const dd = document.getElementById('note-species-dd');
  if (dd) dd.style.display = 'none';
  const locEl = document.getElementById('note-placed-loc');
  if (locEl) { locEl.textContent = ''; locEl.style.display = 'none'; }

  const btn = document.getElementById('btn-layer-note');
  if (btn) btn.classList.remove('active');
}

function _discardNote() { _cancelNote(); }

async function _saveNoteForm() {
  if (_notePinLat === null) return;
  const text = (document.getElementById('note-text-input').value || '').trim();
  if (!text) { alert('Please enter an observation note.'); return; }

  const lat = _notePinLat;
  const lng = _notePinLng;
  // Clear pending marker and state before async submit so double-tap is safe
  if (_notePendingMk) { map.removeLayer(_notePendingMk); _notePendingMk = null; }
  _notePinLat = null;
  _notePinLng = null;

  await _submitNote(lat, lng);
}


function _noteSpeciesSearch(q) {
  const dd = document.getElementById('note-species-dd');
  if (!q.trim()) { dd.style.display = 'none'; return; }
  const hits = _allSpeciesList.filter(sp =>
    sp.scientific_name.toLowerCase().includes(q.toLowerCase()) ||
    ((sp.common_names && sp.common_names[0]) || '').toLowerCase().includes(q.toLowerCase())
  ).slice(0, 6);
  if (!hits.length) { dd.style.display = 'none'; return; }
  dd.innerHTML = hits.map(sp => {
    const label = spNameText(sp.scientific_name, spPickCommon(sp.preferred_common_name, sp.common_names));
    return `<div class="nsp-item" onclick="_addNoteTag(${lmJsArg(sp.scientific_name)})">${_esc(label)}</div>`;
  }).join('');
  dd.style.display = 'block';
}

function _addNoteTag(name) {
  if (!_noteSpeciesTags.includes(name)) {
    _noteSpeciesTags.push(name);
    _renderNoteTags();
  }
  const inp = document.getElementById('note-species-input');
  const dd  = document.getElementById('note-species-dd');
  if (inp) inp.value = '';
  if (dd)  dd.style.display = 'none';
}

function _removeNoteTag(name) {
  _noteSpeciesTags = _noteSpeciesTags.filter(t => t !== name);
  _renderNoteTags();
}

function _renderNoteTags() {
  const row = document.getElementById('note-tags-row');
  if (!row) return;
  row.innerHTML = _noteSpeciesTags.map(t =>
    `<span class="np-tag" onclick="_removeNoteTag(${lmJsArg(t)})" title="Click to remove">${_esc(t)} ✕</span>`
  ).join('');
}

async function _submitNote(lat, lng) {
  const text = (document.getElementById('note-text-input').value || '').trim();
  if (!text) { alert('Please enter an observation note.'); return; }
  try {
    const r = await fetch('/api/notes/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ latitude: lat, longitude: lng, text, species_tags: _noteSpeciesTags }),
    });
    if (!r.ok) { alert('Failed to save note.'); return; }
    const data = await r.json();
    noteFeatures.push({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [lng, lat] },
      properties: {
        id: data.id, map_status: 'note', text,
        species_tags: [..._noteSpeciesTags],
        created_at: data.created_at,
      },
    });
    renderNotes();
    // Reset form and close panel
    document.getElementById('note-text-input').value = '';
    _noteSpeciesTags = [];
    _renderNoteTags();
    const inp = document.getElementById('note-species-input');
    if (inp) inp.value = '';
    const locElSave = document.getElementById('note-placed-loc');
    if (locElSave) { locElSave.textContent = ''; locElSave.style.display = 'none'; }
    document.getElementById('panel-note').style.display = 'none';
    _notePanelOpen = false;
    const btn = document.getElementById('btn-layer-note');
    if (btn) btn.classList.remove('active');
    map.flyTo([lat, lng], Math.max(map.getZoom(), 15), { duration: 0.8 });
  } catch (_) { alert('Failed to save note.'); }
}

// ── Init ──────────────────────────────────────────────────────────────────
_readFiltersFromUrl();                   // restore filterState from query string (Fix #1)
_initSelectMode();                       // enter /lists select mode if ?select=1
_initLatLngDeepLink();                   // ?lat&lng&z centre + standalone marker (any review_status)
loadHeat();                              // whole-archive heat + stats-bar totals
loadFeatures().then(_initHighlight).then(_initSpeciesFilter);  // bbox pins, then deep-link highlight / species filter
loadSpeciesFilter();
loadNotes();

// ── Find Tab (Phase 10.6 — Intent-Based Search) ───────────────────────────

let _findMode = 'season';   // 'season' | 'medicinal' | 'nearby' (Make? opens /recipes)

const _FIND_EDIB_STYLE = {
  edible:   'background:#d1f5da;color:#166534',
  toxic:    'background:#dc2626;color:#fff;font-weight:600',
  caution:  'background:#fef3c7;color:#92400e',
  inedible: 'background:#fef3c7;color:#854d0e',
  unknown:  'background:#f3f3f3;color:#777',
};

function setFindMode(mode) {
  _findMode = mode;
  // Update mode buttons
  ['season','medicinal'].forEach(m => {
    const btn = document.getElementById(`find-mode-${m}`);
    if (btn) btn.classList.toggle('active', m === mode);
  });
  // Show/hide text input (recipes/medicinal need it, season doesn't)
  const inputRow = document.getElementById('find-input-row');
  const optsRow  = document.getElementById('find-opts-row');
  const input    = document.getElementById('find-input');
  if (mode === 'medicinal') {
    inputRow.classList.add('visible');
    optsRow.classList.remove('visible');
    if (input) input.placeholder = 'Type a symptom or use…';
  } else {
    inputRow.classList.remove('visible');
    optsRow.classList.add('visible');
  }
  // Auto-run the mode that doesn't need a text query
  if (mode === 'season') {
    _runFindMode(mode);
  } else {
    document.getElementById('discover-results').innerHTML =
      '<div class="find-state">Enter a symptom or use and press Go.</div>';
  }
}

function runFind() {
  _runFindMode(_findMode);
}

async function _runFindMode(mode) {
  const resultsEl = document.getElementById('discover-results');
  resultsEl.innerHTML = '<div class="find-state">🔎 Searching…</div>';

  if (mode === 'season')    { await _findInSeason(); return; }
  if (mode === 'medicinal') { await _findMedicinal(); return; }
}

// ── Mode 1: In season now ─────────────────────────────────────────────────

async function _findInSeason() {
  const month = new Date().getMonth() + 1;
  const edibleOnly = document.getElementById('find-edible-only')?.checked || false;
  const resultsEl = document.getElementById('discover-results');

  let data;
  try {
    const r = await fetch(`/api/find/in-season?month=${month}&edible_only=${edibleOnly}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    data = await r.json();
  } catch (e) {
    resultsEl.innerHTML = `<div class="find-state">❌ ${_esc(e.message)}</div>`;
    return;
  }

  const { results, in_season_count, total } = data;
  if (!results.length) {
    resultsEl.innerHTML = '<div class="find-state">No species found.</div>';
    return;
  }

  const monthName = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][month];
  let html = `<div class="find-section-hdr">🗓 ${monthName} — ${in_season_count} in season of ${total} species</div>`;
  html += results.map(sp => _findCardHtml(sp, {
    badge: sp.in_season ? '<span class="find-badge find-inseason">✓ in season</span>' : '',
    sub: sp.peak_season
      ? `<span class="find-recipe-count" style="font-style:italic">${_escHtml(sp.peak_season)}</span>`
      : (sp.recipe_count > 0 ? `<span class="find-recipe-count">${sp.recipe_count} recipe${sp.recipe_count !== 1 ? 's' : ''}</span>` : ''),
  })).join('');
  resultsEl.innerHTML = html;
}

// ── Mode 2: What can I make? → the Recipes page (25 Oct 2026) ────────────
// Replaces the old in-panel ingredient search (_findRecipes, /api/find/recipes):
// the Recipes page has the same search plus season / walk / type views, and its
// tiles carry the same look-alike + preparation warnings. With a saved walk
// open, it opens on that walk's recipes — the walk open before Find
// (_discoverWalkId), since opening Find leaves walk mode.

function _openRecipesPage() {
  const walkId = (typeof _walkSaved !== 'undefined' && _walkSaved && _walkSaved.id) ? _walkSaved.id
               : (_discoverWalkId || null);
  location.href = walkId ? `/recipes?walk=${encodeURIComponent(walkId)}` : '/recipes';
}

// ── Mode 3: Medicinal use ─────────────────────────────────────────────────

async function _findMedicinal() {
  const q = (document.getElementById('find-input')?.value || '').trim();
  if (q.length < 2) {
    document.getElementById('discover-results').innerHTML =
      '<div class="find-state">Enter at least 2 characters.</div>'; return;
  }
  const resultsEl = document.getElementById('discover-results');
  let data;
  try {
    const r = await fetch(`/api/find/medicinal?q=${encodeURIComponent(q)}`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    data = await r.json();
  } catch (e) {
    resultsEl.innerHTML = `<div class="find-state">❌ ${_esc(e.message)}</div>`;
    return;
  }

  if (!data.results.length) {
    resultsEl.innerHTML = `<div class="find-state">No medicinal preparations found for "${_escHtml(q)}".<br><small style="color:#aaa">Try: inflammation, wound, digestion, anxiety…</small></div>`;
    return;
  }

  let html = `<div class="find-section-hdr">🌿 ${data.prep_count} preparation${data.prep_count !== 1 ? 's' : ''} across ${data.species_count} species</div>`;
  for (const sp of data.results) {
    for (const prep of sp.preparations) {
      html += `<div class="find-card" onclick="_discoverShowSpecies('${encodeURIComponent(sp.scientific_name).replace(/'/g, "\\'")}')">
        <div class="find-info">
          <div class="find-name" style="font-style:italic">${_escHtml(sp.scientific_name)}</div>
          <div class="find-common">${_escHtml(spCommon(sp.common_name || ''))}</div>
          <div class="find-snippet">${_escHtml(prep.snippet)}</div>
        </div>
      </div>`;
    }
  }
  resultsEl.innerHTML = html;
}

// ── Shared Find helpers ───────────────────────────────────────────────────

function _findCardHtml(sp, { badge = '', sub = '' } = {}) {
  const edibStyle = _FIND_EDIB_STYLE[sp.edibility_status] || _FIND_EDIB_STYLE.unknown;
  const edibLabel = sp.edibility_status || 'unknown';
  return `<div class="find-card" onclick="_discoverShowSpecies('${encodeURIComponent(sp.scientific_name).replace(/'/g, "\\'")}')">
    ${sp.thumbnail
      ? `<img class="find-thumb" src="${_esc(sp.thumbnail)}" loading="lazy" alt="">`
      : '<div class="find-thumb-empty"></div>'}
    <div class="find-info">
      <div class="find-name">${_escHtml(sp.scientific_name)}</div>
      <div class="find-common">${_escHtml(spCommon(sp.common_name || ''))}</div>
      <div class="find-meta">
        <span class="find-badge" style="${edibStyle}">${edibLabel}</span>
        ${badge}
        ${sub}
      </div>
    </div>
  </div>`;
}

function _escHtml(s) { return window.lmEsc(s); }

// ── Right-panel initialisation ─────────────────────────────────────────────
// Map starts full-width with panel closed on all devices.
// Tab strip is always visible via CSS (position:absolute in #main).
// Pane starts hidden via CSS (transform:translateX(300px)).
(function _initRightPanel() {
  // Nothing to do — CSS defaults are correct.
  // Remove any stale class that previous implementations may have set.
  document.getElementById('sidebar').classList.remove('rp-collapsed');
})();
