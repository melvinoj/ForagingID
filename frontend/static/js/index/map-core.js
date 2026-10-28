// ── Map init ──────────────────────────────────────────────────────────────

const isMobile = () => window.innerWidth <= 700;

const map = L.map('map', { tap: true, tapTolerance: 15, zoomControl: false }).setView([54.5, -3.0], 6);
L.control.zoom({ position: 'topright' }).addTo(map);
L.control.scale({ position: 'bottomright', imperial: true, metric: true, maxWidth: 120 }).addTo(map);

// ── Locate me (GPS) — prompt 10a.2 ───────────────────────────────────────
let _userLocMarker = null;
let _locateToastTimer = null;

function _showLocateToast(msg) {
  const el = document.getElementById('locate-toast');
  if (!el) return;
  el.textContent = msg;
  el.classList.add('visible');
  clearTimeout(_locateToastTimer);
  _locateToastTimer = setTimeout(function () { el.classList.remove('visible'); }, 3000);
}

function locateMe() {
  const link = _locateControl && _locateControl._link;
  if (!('geolocation' in navigator)) { _showLocateToast('Location unavailable'); return; }
  if (link) link.classList.add('locating');
  // Shared GPS manager — window.foragingUser is kept in sync inside GPS.getOnce().
  GPS.getOnce().then(function (p) {
    if (link) link.classList.remove('locating');
    const lat = p.lat, lng = p.lng;
    map.setView([lat, lng], 16);
    if (_userLocMarker) {
      _userLocMarker.setLatLng([lat, lng]);
    } else {
      const icon = L.divIcon({
        className: 'fid-locate-icon',
        html: '<div class="fid-locate-pulse"></div><div class="fid-locate-core"></div>',
        iconSize: [16, 16], iconAnchor: [8, 8],
      });
      _userLocMarker = L.marker([lat, lng], {
        icon: icon, interactive: false, keyboard: false, zIndexOffset: 1000,
      }).addTo(map);
    }
    if (link) link.classList.add('active');
  }).catch(function (_err) {
    if (link) link.classList.remove('locating');
    _showLocateToast('Location unavailable');
  });
}

const LocateControl = L.Control.extend({
  options: { position: 'bottomright' },
  onAdd: function () {
    const c = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-locate');
    const a = L.DomUtil.create('a', '', c);
    a.href = '#';
    a.title = 'Show my location';
    a.setAttribute('role', 'button');
    a.setAttribute('aria-label', 'Show my location');
    a.innerHTML =
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<circle cx="12" cy="12" r="7"></circle>' +
      '<line x1="12" y1="1" x2="12" y2="4"></line>' +
      '<line x1="12" y1="20" x2="12" y2="23"></line>' +
      '<line x1="1" y1="12" x2="4" y2="12"></line>' +
      '<line x1="20" y1="12" x2="23" y2="12"></line>' +
      '<circle cx="12" cy="12" r="2.5" fill="currentColor" stroke="none"></circle>' +
      '</svg>';
    this._link = a;
    L.DomEvent.on(a, 'click', L.DomEvent.stop);
    L.DomEvent.on(a, 'click', locateMe);
    L.DomEvent.disableClickPropagation(c);
    return c;
  },
});
const _locateControl = new LocateControl();
map.addControl(_locateControl);

// Nav drawer open/close now live in /static/js/site-header.js (Map Redesign P3-nav).
// Config sheet closes itself when the shared drawer opens, without that file
// needing to know the config sheet exists.
window.addEventListener('sitenav:open', closeConfigSheet);

// ── Map Redesign P1: config sheet (VIEW/BASE LAYER/OVERLAYS/FILTERS/DISCOVER/TOOLS/LEGEND) ──

function openConfigSheet() {
  closeNavDrawer();
  document.getElementById('config-sheet').classList.add('open');
  document.getElementById('config-sheet-scrim').classList.add('show');
  document.getElementById('config-sheet-chip').setAttribute('aria-expanded', 'true');
  // Heatmap controls disclosure: collapsed by default each time the sheet opens
  const _hd = document.getElementById('heatmap-disclosure');
  if (_hd) _hd.open = false;
}
function closeConfigSheet() {
  document.getElementById('config-sheet').classList.remove('open');
  document.getElementById('config-sheet').classList.remove('expanded');
  document.getElementById('config-sheet-scrim').classList.remove('show');
  document.getElementById('config-sheet-chip').setAttribute('aria-expanded', 'false');
}
function toggleConfigSheet() {
  const sheet = document.getElementById('config-sheet');
  if (sheet.classList.contains('open')) closeConfigSheet();
  else openConfigSheet();
}
function _toggleSheetExpanded() {
  document.getElementById('config-sheet').classList.toggle('expanded');
}

// ── Map Redesign P1: search chip (top-right, expands in place) ───────────

function _collapseSearchChip() {
  // Deferred so a click on the clear button / dropdown still registers before collapse.
  setTimeout(() => {
    const wrap = document.getElementById('search-chip-wrap');
    if (wrap.contains(document.activeElement)) return;
    if (document.getElementById('map-search-input').value) return;
    wrap.classList.remove('expanded');
  }, 150);
}

// ── Map Redesign P1: "In season now" — Filters + Overlays both drive filterState.inSeason ──

function _setInSeason(checked) {
  filterState.inSeason = checked;
  const a = document.getElementById('filter-in-season');
  const b = document.getElementById('overlay-in-season');
  if (a) a.checked = checked;
  if (b) b.checked = checked;
  _updateFilterFab();
  renderMarkers();
}

document.addEventListener('keydown', (ev) => {
  if (ev.key !== 'Escape') return;
  // Nav drawer closes itself on Escape (site-header.js).
  closeConfigSheet();
  _collapseSearchChip();
  document.getElementById('search-chip-wrap').classList.remove('expanded');
});

// ── Feature 1: Map position memory ───────────────────────────────────────
(function() {
  // Skip the remembered-viewport restore when arriving via a ?lat&lng deep-link —
  // _initLatLngDeepLink() owns the initial view in that case, so the two don't fight.
  try {
    const _q = new URLSearchParams(location.search);
    if (isFinite(parseFloat(_q.get('lat'))) && isFinite(parseFloat(_q.get('lng')))) return;
  } catch (_) {}
  try {
    const _pos = JSON.parse(localStorage.getItem('fid_map_pos') || 'null');
    if (_pos && isFinite(_pos.lat) && isFinite(_pos.lng) && isFinite(_pos.z)) {
      map.setView([_pos.lat, _pos.lng], _pos.z);
    }
  } catch (_) {}
})();
map.on('moveend', function() {
  try {
    const c = map.getCenter();
    localStorage.setItem('fid_map_pos', JSON.stringify({ lat: c.lat, lng: c.lng, z: map.getZoom() }));
  } catch (_) {}
  // Refetch bbox-bounded pins for the new viewport (debounced).
  clearTimeout(_moveDebounce);
  _moveDebounce = setTimeout(loadFeatures, 200);
});

// ── Base layers ───────────────────────────────────────────────────────────────
const _baseLayers = {
  standard: L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© <a href="https://openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }),
  satellite: L.tileLayer(
    'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Source: Esri, USGS, AeroGRID, IGN, and the GIS User Community',
    maxZoom: 19,
  }),
  terrain: L.tileLayer('https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png', {
    attribution: 'Map data: &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a> contributors, SRTM | Display: &copy; <a href="http://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',
    maxZoom: 17, subdomains: ['a','b','c'],
  }),
};
const _STATIC_LAYERS = ['standard', 'satellite', 'terrain'];
// One-time reset: clear any stale saved layer so Outdoors becomes default again
if (localStorage.getItem('foragingid_layer_version') !== '3') {
  localStorage.removeItem('foragingid_default_layer');
  localStorage.setItem('foragingid_layer_version', '3');
}
const _savedDefaultLayer = localStorage.getItem('foragingid_default_layer');
let _currentBaseLayerKey = (_savedDefaultLayer && _STATIC_LAYERS.includes(_savedDefaultLayer))
  ? _savedDefaultLayer : 'terrain';
_baseLayers[_currentBaseLayerKey].addTo(map);
// Reflect saved default in the star buttons once DOM is ready
document.addEventListener('DOMContentLoaded', () =>
  _refreshDefaultStars(_savedDefaultLayer || 'terrain'), { once: true });
// Fallback: apply immediately if DOMContentLoaded already fired
if (document.readyState !== 'loading')
  _refreshDefaultStars(_savedDefaultLayer || 'terrain');

// Load map config (Thunderforest key) and set up Outdoors layer if available
(async function _initMapConfig() {
  try {
    const r = await fetch('/api/map/config');
    if (!r.ok) return;
    const cfg = await r.json();
    const tfKey = cfg.thunderforest_api_key || '';
    if (!tfKey) return;

    _baseLayers.outdoors = L.tileLayer(
      `https://tile.thunderforest.com/outdoors/{z}/{x}/{y}.png?apikey=${tfKey}`,
      {
        attribution: 'Maps &copy; <a href="https://www.thunderforest.com/">Thunderforest</a>, Data &copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap contributors</a>',
        maxZoom: 22,
      }
    );

    // Show the Outdoors row (button + star)
    const outdoorsRow = document.getElementById('bls-row-outdoors');
    if (outdoorsRow) outdoorsRow.style.display = '';

    // Switch to Outdoors only when: user saved it as default, or no saved default at all
    const _storedDefault = localStorage.getItem('foragingid_default_layer');
    if (!_storedDefault || _storedDefault === 'outdoors') {
      map.removeLayer(_baseLayers[_currentBaseLayerKey]);
      _baseLayers.outdoors.addTo(map);
      _currentBaseLayerKey = 'outdoors';
      document.querySelectorAll('.bls-base-btn').forEach(b =>
        b.classList.toggle('active', b.dataset.layer === 'outdoors'));
    }
    // If Outdoors is the saved default, update the star buttons
    if (_storedDefault === 'outdoors') _refreshDefaultStars('outdoors');
  } catch (_) {}
})();

function _refreshDefaultStars(key) {
  document.querySelectorAll('.bls-default-btn').forEach(b => {
    const isDefault = b.dataset.layer === key;
    b.classList.toggle('is-default', isDefault);
    b.textContent = isDefault ? '★' : '☆';
  });
}

function setDefaultLayer(key) {
  localStorage.setItem('foragingid_default_layer', key);
  _refreshDefaultStars(key);
}

function setBaseLayer(name) {
  if (name === _currentBaseLayerKey || !_baseLayers[name]) return;
  map.removeLayer(_baseLayers[_currentBaseLayerKey]);
  _baseLayers[name].addTo(map);
  _currentBaseLayerKey = name;
  document.querySelectorAll('.bls-base-btn').forEach(b =>
    b.classList.toggle('active', b.dataset.layer === name));
  // Clear any stale "unavailable" state on the layer we're activating so it
  // always renders active/bold rather than greyed/italic.
  const _selBtn = document.querySelector(`.bls-base-btn[data-layer="${name}"]`);
  if (_selBtn) { _selBtn.classList.remove('bls-unavailable'); _selBtn.title = ''; }
  // Soil legend — visible only when soil layer is active
  document.getElementById('soil-legend').classList.toggle('visible', name === 'soil');
  // Land use legend — visible only when land use layer is active
  document.getElementById('landuse-legend').classList.toggle('visible', name === 'landuse');
  // Geology toast — dismiss when switching away
  if (name !== 'geology') _hideGeoToast();
  // Place names toggle: show only for overlay layers, remove overlay when leaving
  const _isOverlay = ['geology', 'soil', 'landuse'].includes(name);
  const _pnRow = document.getElementById('bls-placenames-row');
  if (_pnRow) _pnRow.style.display = _isOverlay ? '' : 'none';
  const _pnTbar = document.getElementById('btn-placenames-toolbar');
  if (_pnTbar) _pnTbar.style.display = _isOverlay ? '' : 'none';
  if (!_isOverlay && _placeNamesOn) {
    _placeNamesOn = false;
    if (map.hasLayer(_placeNamesOverlay)) map.removeLayer(_placeNamesOverlay);
    const _pnBtn = document.getElementById('bls-placenames-btn');
    if (_pnBtn) _pnBtn.classList.remove('active');
    if (_pnTbar) _pnTbar.classList.remove('active');
  }
}

// ── Extended base layers (geology / soil / land use) ─────────────────────
// These are added to _baseLayers after the map is created. Verified HTTP 200:
// - Macrostrat geology tiles
// - ISRIC phh2o WMS (soil pH)
// - ESRI Sentinel-2 10m Land Cover (ImageServer exportImage, see below)

// The ESRI land cover dataset is an ImageServer (not cached XYZ tiles), so we
// subclass L.TileLayer and build an exportImage request per tile, computing the
// tile's Web-Mercator (EPSG:3857) bbox from its {x,y,z} coords.
const _LC_EXPORT =
  'https://ic.imagery1.arcgis.com/arcgis/rest/services/Sentinel2_10m_LandCover/ImageServer/exportImage';
const _LandCoverTileLayer = L.TileLayer.extend({
  getTileUrl: function (coords) {
    const size = this.getTileSize();
    const nwPx  = coords.scaleBy(size);
    const sePx  = nwPx.add(size);
    const nwM = L.CRS.EPSG3857.project(this._map.unproject(nwPx, coords.z));
    const seM = L.CRS.EPSG3857.project(this._map.unproject(sePx, coords.z));
    const bbox = [nwM.x, seM.y, seM.x, nwM.y].join(',');
    return `${_LC_EXPORT}?bbox=${bbox}&bboxSR=3857&imageSR=3857`
         + `&size=256,256&format=png&transparent=true&time=1577836800000&f=image`;
  },
});

Object.assign(_baseLayers, {
  geology: L.tileLayer('https://tiles.macrostrat.org/carto/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://macrostrat.org">Macrostrat</a>',
    maxZoom: 19, opacity: 0.85,
  }),
  soil: L.tileLayer.wms('https://maps.isric.org/mapserv?map=/map/phh2o.map', {
    layers: 'phh2o_0-5cm_mean', format: 'image/png', transparent: true,
    version: '1.3.0', opacity: 0.85,
    attribution: '&copy; <a href="https://www.isric.org">ISRIC &mdash; World Soil</a>',
  }),
  // ESRI Sentinel-2 10m Land Cover — genuine colour-coded land use classes
  // (Water, Trees, Flooded veg, Crops, Built, Bare ground, Snow, Rangeland).
  // The dataset is a (non-tiled) time-aware ImageServer, so we render per-tile
  // PNGs via exportImage rather than fetching cached XYZ tiles. Pinned to the
  // 2020 composite (time=2020-01-01) to match the legend.
  landuse: new _LandCoverTileLayer('', {
    attribution: '&copy; <a href="https://www.esri.com">Esri</a>, Sentinel-2 Land Cover 10m',
    maxZoom: 19,
    opacity: 0.85,
  }),
});


function _markLayerUnavailable(key) {
  if (_currentBaseLayerKey === key) {
    map.removeLayer(_baseLayers[key]);
    _baseLayers.standard.addTo(map);
    _currentBaseLayerKey = 'standard';
    // Sync legends and place names off when falling back to standard
    document.getElementById('soil-legend').classList.remove('visible');
    document.getElementById('landuse-legend').classList.remove('visible');
    const _pnRow = document.getElementById('bls-placenames-row');
    if (_pnRow) _pnRow.style.display = 'none';
  }
  const btn = document.querySelector(`.bls-base-btn[data-layer="${key}"]`);
  if (btn) { btn.classList.remove('active'); btn.classList.add('bls-unavailable'); btn.title = 'Unavailable in this area'; }
  document.querySelector('.bls-base-btn[data-layer="terrain"]').classList.add('active');
}

// ── Schutzgebiete WMS overlays (NSG / FFH / Biotop) ─────────────────────────
const _schutzLayers = {
  nsg: L.tileLayer.wms(
    'https://rips-gdi.lubw.baden-wuerttemberg.de/arcgis/services/wms/UIS_0100000001200001/MapServer/WMSServer',
    { layers: '0', format: 'image/png', transparent: true, version: '1.1.1', opacity: 0.5, attribution: 'LUBW' }
  ),
  ffh: L.tileLayer.wms(
    'https://rips-gdi.lubw.baden-wuerttemberg.de/arcgis/services/wms/UIS_0100000013100001/MapServer/WMSServer',
    { layers: '0', format: 'image/png', transparent: true, version: '1.1.1', opacity: 0.5, attribution: 'LUBW' }
  ),
  biotop: L.tileLayer.wms(
    'https://rips-gdi.lubw.baden-wuerttemberg.de/arcgis/services/wms/UIS_0100000030200001/MapServer/WMSServer',
    { layers: '0', format: 'image/png', transparent: true, version: '1.1.1', opacity: 0.5, minZoom: 13, attribution: 'LUBW' }
  ),
  wald: L.tileLayer.wms(
    'https://owsproxy.lgl-bw.de/owsproxy/ows/WMS_ForstBW_Waldschutzgebiete',
    { layers: 'Prozessschutz,Schonwaelder_bisM500000,Schonwaelder_abM500000', format: 'image/png', transparent: true, version: '1.1.1', opacity: 0.7, attribution: 'LFV BW' }
  ),
};
const _schutzActive = { nsg: false, ffh: false, biotop: false, wald: false };

function toggleSchutzOverlay(key) {
  const layer = _schutzLayers[key];
  if (!layer) return;
  _schutzActive[key] = !_schutzActive[key];
  if (_schutzActive[key]) {
    layer.addTo(map);
    if (key === 'biotop' && map.getZoom() < 13) {
      _showSchutzNotice('Zoom in to see Biotop layer (zoom 13+)');
    }
  } else {
    map.removeLayer(layer);
  }
  const btn = document.getElementById('bls-btn-' + key);
  if (btn) btn.classList.toggle('active', _schutzActive[key]);
  const row = document.getElementById('sz-row-' + key);
  if (row) row.style.display = _schutzActive[key] ? '' : 'none';
  const anyActive = _schutzActive.nsg || _schutzActive.ffh || _schutzActive.biotop || _schutzActive.wald;
  document.getElementById('schutz-legend').classList.toggle('visible', anyActive);
}

// ── Combined legend panel — opened directly via the legend chip, independent
// of the auto-show-on-overlay-toggle behaviour above (unchanged).
function toggleLegendPanel() {
  document.getElementById('schutz-legend').classList.toggle('visible');
}
function closeLegendPanel() {
  document.getElementById('schutz-legend').classList.remove('visible');
}

function _showSchutzNotice(msg) {
  var existing = document.getElementById('schutz-notice');
  if (existing) existing.remove();
  var el = document.createElement('div');
  el.id = 'schutz-notice';
  el.style.cssText = 'position:fixed;bottom:80px;left:50%;transform:translateX(-50%);background:rgba(0,0,0,.8);color:#fff;padding:8px 16px;border-radius:6px;font-size:0.78rem;z-index:3000;pointer-events:none;';
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(function() { el.remove(); }, 4000);
}

// ── Place names overlay (CartoDB labels-only; shown over geology/soil/landuse) ─
const _placeNamesOverlay = L.tileLayer(
  'https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; <a href="https://carto.com/attributions">CARTO</a>',
  subdomains: 'abcd', maxZoom: 19, zIndex: 350,
});
let _placeNamesOn = false;

function togglePlaceNames() {
  _placeNamesOn = !_placeNamesOn;
  if (_placeNamesOn) {
    _placeNamesOverlay.addTo(map);
  } else {
    if (map.hasLayer(_placeNamesOverlay)) map.removeLayer(_placeNamesOverlay);
  }
  const btn = document.getElementById('bls-placenames-btn');
  if (btn) btn.classList.toggle('active', _placeNamesOn);
  const tbar = document.getElementById('btn-placenames-toolbar');
  if (tbar) tbar.classList.toggle('active', _placeNamesOn);
}

const clusterGroup = L.markerClusterGroup({
  chunkedLoading: true,
  maxClusterRadius: 60,
  iconCreateFunction: function(cluster) {
    const n = cluster.getChildCount();
    const size = n < 10 ? 34 : n < 100 ? 40 : 48;
    const bg   = n < 10 ? '#2d7a4f' : n < 100 ? '#1a5c38' : '#0f3d24';
    return L.divIcon({
      className: 'mcluster',
      html: `<div style="width:${size}px;height:${size}px;border-radius:50%;
                  background:${bg};color:white;font-size:${n<100?'0.84':'0.72'}rem;
                  font-weight:700;display:flex;align-items:center;justify-content:center;
                  border:3px solid white;box-shadow:0 2px 8px rgba(0,0,0,.35)">${n}</div>`,
      iconSize: [size, size], iconAnchor: [size/2, size/2],
    });
  },
});

const pinsGroup = L.layerGroup();

// ── Heatmap ───────────────────────────────────────────────────────────────
// Fixed vivid gradient — exact stop colours, no saturation slider.
// max is self-calibrated via _recalcHeatMax() so the hottest cluster in the
// current view always hits the red end of the scale.
const _HEAT_GRADIENT = {
  0.00: 'transparent',
  0.20: '#0000ff',
  0.40: '#00ffff',
  0.60: '#00ff00',
  0.75: '#ffff00',
  0.90: '#ff6600',
  1.00: '#ff0000',
};

let _heatPoints = [];  // current rendered points, kept for _recalcHeatMax

let heatLayer = L.heatLayer([], {
  radius:     30,
  blur:       20,
  maxZoom:    18,
  max:        1,
  minOpacity: 0.6,
  gradient:   _HEAT_GRADIENT,
});
// leaflet.heat 0.2.0's redraw() reads this._map._animating, and _map is null
// once the layer is off the map (a loaded saved walk hides it) — setOptions /
// setLatLngs then throw "Cannot read properties of null (reading '_animating')".
// Every heat update goes through these: off the map they only store the new
// data/options, which onAdd's _reset → _redraw draws when the layer returns.
function _heatOnMap() { return !!heatLayer._map; }
function _heatSetOptions(opts) {
  if (_heatOnMap()) { heatLayer.setOptions(opts); return; }
  L.setOptions(heatLayer, opts);
  if (heatLayer._heat) heatLayer._updateOptions();
}
function _heatSetLatLngs(pts) {
  if (_heatOnMap()) heatLayer.setLatLngs(pts);
  else heatLayer._latlngs = pts;
}
// Remove the heat layer and drop a redraw frame it already queued — that frame's
// _redraw reads this._map.getSize() and would throw after removal.
function _heatRemove() {
  if (heatLayer._frame) { L.Util.cancelAnimFrame(heatLayer._frame); heatLayer._frame = null; }
  map.removeLayer(heatLayer);
}
let currentLayer = 'heatmap';
let _pinsExplicit = false; // true only when user explicitly selects the Pins layer button

function setLayer(mode, _fromZoom) {
  currentLayer = mode;
  _pinsExplicit = (mode === 'pins');
  if (!_fromZoom) {
    ['pins', 'clusters', 'heatmap'].forEach(m => {
      document.getElementById(`btn-layer-${m}`).classList.toggle('active', m === mode);
    });
  }
  _applyLayer();
}

// Loaded saved walk: {hidePins, prevLayer, prevCenter, prevZoom} — null otherwise.
// hidePins (default true) takes every observation layer off the map so only the
// walk shows; "Show all pins" flips it. prev* restore the view on clear.
// var (not let): _applyLayer runs from many places, some before this file's
// walk-state block is reached.
var _savedWalkView = null;
// Loaded saved walk as the server computed it: {id, name, stops, membership}
// (GET /api/walk/saves/{id}). _savedWalkRoute() turns it into the route array.
var _savedWalkData = null;

function _applyLayer() {
  const _hideAll     = !!(_savedWalkView && _savedWalkView.hidePins);
  const showPins     = currentLayer === 'pins'     && !_hideAll;
  const showClusters = currentLayer === 'clusters' && !_hideAll;
  const showHeat     = currentLayer === 'heatmap'  && !_hideAll;

  if (showPins     && !map.hasLayer(pinsGroup))    map.addLayer(pinsGroup);
  if (!showPins    &&  map.hasLayer(pinsGroup))    map.removeLayer(pinsGroup);
  if (showClusters && !map.hasLayer(clusterGroup)) map.addLayer(clusterGroup);
  if (!showClusters &&  map.hasLayer(clusterGroup)) map.removeLayer(clusterGroup);
  if (showHeat     && !map.hasLayer(heatLayer))    { map.addLayer(heatLayer); _recalcHeatMax(); }
  if (!showHeat    &&  map.hasLayer(heatLayer))    _heatRemove();

  // Heatmap controls disclosure only makes sense when the heatmap is the active
  // view — toggle the whole #cs-heatmap section (retargeted from the sliders).
  const heatSection = document.getElementById('cs-heatmap');
  if (heatSection) heatSection.style.display = showHeat ? '' : 'none';

  // Counts pill: shown in ALL three views (Pins/Clusters/Heatmap). The in-view
  // sightings/species count is computed in renderMarkers() on every pan/zoom via
  // loadFeatures(), independent of currentLayer, so it populates identically in
  // heatmap — only the visibility was ever gated, not the count.
  const pill = document.getElementById('counts-pill');
  if (pill) pill.classList.add('visible');
}

function updateHeatmapOptions() {
  const radius     = parseInt(document.getElementById('hc-radius').value);
  const blur       = parseInt(document.getElementById('hc-blur').value);
  const brightness = parseInt(document.getElementById('hc-brightness').value);

  document.getElementById('hc-radius-val').textContent     = radius + 'px';
  document.getElementById('hc-blur-val').textContent       = blur;
  document.getElementById('hc-brightness-val').textContent = brightness + '%';

  _heatSetOptions({ radius, blur });
  // Brightness controls canvas opacity so the whole heatmap fades uniformly
  if (heatLayer._canvas) heatLayer._canvas.style.opacity = brightness / 100;
  _recalcHeatMax();
}

// Self-calibrate heatmap max: find the highest point-density within the current
// radius in the visible viewport, so the hottest cluster hits the red end of scale.
function _recalcHeatMax() {
  // No-op when the heat layer isn't on the map (Pins/Clusters view, a loaded
  // saved walk): a zoomend fired by an unrelated fitBounds/flyTo (_fitSavedWalk,
  // _discoverShowSpecies) must not redraw it. Checks _map, not _canvas — the
  // canvas survives removal. _applyLayer recalibrates when the layer returns.
  if (!_heatOnMap()) return;
  if (!_heatPoints.length) return;
  const radius = parseInt(document.getElementById('hc-radius').value) || 30;
  const zoom   = map.getZoom();
  const lat0   = map.getCenter().lat;
  // Metres per pixel at this zoom
  const mpp    = 156543.03392 * Math.cos(lat0 * Math.PI / 180) / Math.pow(2, zoom);
  const threshM = radius * mpp;  // radius in metres

  const bounds = map.getBounds();
  // Use only viewport-visible points for both candidate selection AND neighbour
  // counting. This gives density-relative-to-view: max calibrates to what's on
  // screen, so sparse regions get the same gradient richness as dense ones,
  // without losing the whole-archive data source or the /api/map/heat wiring.
  const visible = _heatPoints.filter(([plat, plng]) => bounds.contains([plat, plng]));

  let maxCount = 1;
  for (const [lat1, lng1] of visible) {
    let count = 0;
    for (const [lat2, lng2] of visible) {
      const dlat = (lat1 - lat2) * 111320;
      const dlng = (lng1 - lng2) * 111320 * Math.cos(lat1 * Math.PI / 180);
      if (Math.sqrt(dlat * dlat + dlng * dlng) <= threshM) count++;
    }
    if (count > maxCount) maxCount = count;
  }

  _heatSetOptions({ max: maxCount });
}

map.addLayer(heatLayer);

// ── Heatmap live zoom response ─────────────────────────────────────────────
// Two-tier strategy so mobile pinch-zoom feels responsive:
//
//   zoom    → immediate opacity pulse (visual feedback that something is
//             happening) + a debounced _recalcHeatMax scheduled ≤1× per
//             300ms. The O(n²) neighbour loop is cheap enough to run a few
//             times mid-gesture without jank, but not on every RAF tick.
//
//   zoomend → cancel any pending debounce (zoomend owns the definitive
//             pass), restore opacity to user-set brightness, then run
//             _recalcHeatMax once the gesture is fully settled.

let _heatZoomDebounceTimer = null;

function _heatZoomFeedback() {
  // Pulse the canvas opacity to ~65% of the user's brightness preference.
  // This gives immediate sub-frame-latency visual confirmation that the
  // heatmap is responding, even before the calibration fires.
  if (heatLayer._canvas) {
    const brightness = (parseInt(document.getElementById('hc-brightness').value) || 80) / 100;
    heatLayer._canvas.style.opacity = brightness * 0.65;
  }
  // Debounced recalibration — fires at most once per 300ms during the gesture.
  clearTimeout(_heatZoomDebounceTimer);
  _heatZoomDebounceTimer = setTimeout(_recalcHeatMax, 300);
}

function _heatZoomEnd() {
  // Cancel any in-flight debounce; this function runs the authoritative pass.
  clearTimeout(_heatZoomDebounceTimer);
  _heatZoomDebounceTimer = null;
  // Restore to full user-set brightness before the definitive recalibration.
  if (heatLayer._canvas) {
    const brightness = (parseInt(document.getElementById('hc-brightness').value) || 80) / 100;
    heatLayer._canvas.style.opacity = brightness;
  }
  _recalcHeatMax();
}

map.on('zoom',    _heatZoomFeedback);
map.on('zoomend', _heatZoomEnd);

let allFeatures = [];   // bbox-bounded pins for the current viewport
let _heatAll    = [];   // whole-archive heat points [lat,lng,sp,hc,ws,month]
let _pinLoadSeq = 0;    // discards out-of-order bbox pin responses
let _moveDebounce = null;

// ── Sidebar: filter mode vs detail mode ──────────────────────────────────

let _currentDetailObs = null;  // properties of currently shown observation

function openSidebar() {
  // Open the pane (used by walk/nearme/find/detail flows that call this directly)
  document.getElementById('rp-pane').classList.add('rp-open');
  if (isMobile()) document.getElementById('drawer-scrim').classList.add('show');
}
function closeSidebar() {
  document.getElementById('rp-pane').classList.remove('rp-open');
  document.getElementById('drawer-scrim').classList.remove('show');
  // Also clear any active tab
  if (_openToolbarPanel) {
    document.getElementById('panel-' + _openToolbarPanel).style.display = 'none';
    document.getElementById('btn-panel-' + _openToolbarPanel).classList.remove('active');
    _openToolbarPanel = null;
  }
}

function showFilterView() {
  document.getElementById('filter-view').style.display = 'none';
  document.getElementById('detail-view').style.display = 'none';

  document.getElementById('discover-view').classList.remove('active');
  document.getElementById('sidebar').classList.remove('rp-detail');
  const _fvFab = document.getElementById('fab-filters');
  if (_fvFab) _fvFab.style.display = 'none';
  _currentDetailObs = null;
  _deselectPin();
  // Back from detail / walk / nearme — show the empty-state pane again.
  document.getElementById('filter-view').style.display = '';
}

// ── 10a.4 Near me / in season ─────────────────────────────────────────────────
let _nearMeRadius  = 200;     // active radius in metres (200 → 500 → 1000)
let _nearMePos     = null;    // { lat, lng } the results were fetched for
let _nearMeResults = [];      // last species list from /api/nearby

const _NEARME_EDIB_STYLE = {
  edible:    'background:#d1f5da;color:#166534',
  toxic:     'background:#dc2626;color:#fff;font-weight:600',
  caution:   'background:#fef3c7;color:#92400e',
  inedible:  'background:#fef3c7;color:#854d0e',
  medicinal: 'background:#e0e7ff;color:#3730a3',
  unknown:   'background:#f3f3f3;color:#777',
};

// GPS-acquire + first fetch for the Near me location filter (Map Redesign P2).
// Triggered by _toggleDiscoverNearMe() when the toggle is switched on.
function _beginNearMe() {
  document.getElementById('discover-sub').textContent = 'Locating you…';
  document.getElementById('nearme-radius-row').style.display = 'none';
  document.getElementById('discover-results').innerHTML =
    '<div class="nearme-state">📡 Acquiring your location…</div>';

  // getOnce() reuses a fix obtained by the locate button if it is fresh.
  GPS.getOnce().then(function (p) {
    _nearMePos = { lat: p.lat, lng: p.lng };
    _nearMeRadius = 200;
    _syncNearMeRadiusButtons();
    // Pan map to current location so the user sees where results are centred
    map.flyTo([p.lat, p.lng], Math.max(map.getZoom(), 14), { animate: true, duration: 1 });
    _fetchNearMe();
  }).catch(function (err) {
    const denied = err && (err.code === 1 || err.message === 'geolocation-unavailable');
    document.getElementById('discover-sub').textContent = 'Location unavailable';
    document.getElementById('discover-results').innerHTML = denied
      ? '<div class="nearme-state">📍 Location access denied.<br>Allow location in browser settings and try again.</div>'
      : '<div class="nearme-state">📍 Could not get your location.<br>Check your connection and try Near me again.</div>';
  });
}

function setNearMeRadius(r) {
  _nearMeRadius = r;
  _syncNearMeRadiusButtons();
  _fetchNearMe();
  // P4 — Zoom map to fit the selected radius circle around current location
  if (_nearMePos) {
    map.fitBounds(
      L.circle([_nearMePos.lat, _nearMePos.lng], r).getBounds(),
      { padding: [24, 24], maxZoom: 17 }
    );
  }
}

function _syncNearMeRadiusButtons() {
  [200, 500, 1000].forEach(function (r) {
    const btn = document.getElementById('nearme-r-' + r);
    if (btn) btn.classList.toggle('active', r === _nearMeRadius);
  });
}

async function _fetchNearMe() {
  if (!_nearMePos) return;
  const list = document.getElementById('discover-results');
  document.getElementById('discover-sub').textContent = 'Searching…';
  list.innerHTML = '<div class="nearme-state">🔎 Looking for species nearby…</div>';

  // Core params + mirror of the active map filters.
  const params = new URLSearchParams({
    lat: _nearMePos.lat,
    lng: _nearMePos.lng,
    radius_m: _nearMeRadius,
    month: new Date().getMonth() + 1,
  });
  if (filterState.species.size > 0) params.set('species', [...filterState.species].join(','));
  if (filterState.months.size  > 0) params.set('months',  [...filterState.months].join(','));
  if (filterState.workshop)  params.set('workshop', 'true');
  if (filterState.humanOnly) params.set('human_only', 'true');

  try {
    const r = await fetch('/api/nearby?' + params.toString());
    if (!r.ok) throw new Error('nearby ' + r.status);
    const d = await r.json();
    _nearMeResults = d.results || [];
    _renderNearMe();
  } catch (e) {
    document.getElementById('discover-sub').textContent = 'Error';
    list.innerHTML = '<div class="nearme-state">⚠️ Could not load nearby species. Try again.</div>';
  }
}

function _renderNearMe() {
  const list = document.getElementById('discover-results');
  const results = _nearMeResults;
  const radiusLabel = _nearMeRadius >= 1000 ? (_nearMeRadius / 1000) + 'km' : _nearMeRadius + 'm';

  document.getElementById('nearme-radius-row').style.display = 'flex';
  document.getElementById('discover-sub').textContent =
    `${results.length} species within ${radiusLabel}`;

  let html = '';

  // Filter notice — surfaces that active map filters are narrowing the results.
  if (_countActiveFilters() > 0) {
    html += `<div class="nearme-filter-notice">
      🔍 Filters active — results are filtered
      <button onclick="openSidebar(); showFilterView()">Edit filters</button>
    </div>`;
  }

  if (!results.length) {
    html += `<div class="nearme-state">No confirmed species within ${radiusLabel}.</div>`;
    // Offer wider radius when nothing turns up at the current one.
    html += _nearMeFallbackHint();
    list.innerHTML = html;
    return;
  }

  for (const sp of results) {
    const thumbName = sp.thumbnail ? sp.thumbnail.split('/').pop() : null;
    const thumb = thumbName
      ? `<img class="nearme-thumb" src="/thumbnails/${_esc(thumbName)}" loading="lazy" onerror="this.style.display='none'">`
      : `<div class="nearme-thumb" style="display:flex;align-items:center;justify-content:center;font-size:1.4rem">🌿</div>`;
    const dist = Math.round((sp.distance_m || 0) / 10) * 10;
    const edib = sp.edibility_status;
    const edibBadge = edib
      ? `<span class="nearme-edib" style="${_NEARME_EDIB_STYLE[edib] || _NEARME_EDIB_STYLE.unknown}">${_esc(edib)}</span>`
      : '';
    const seasonBadge = sp.in_season ? `<span class="nearme-inseason">✓ In season</span>` : '';
    const count = sp.observation_count || 0;
    const common = sp.common_name ? `<div class="nearme-common">${_esc(spCommon(sp.common_name))}</div>` : '';

    html += `<a class="nearme-card" href="#" onclick="event.preventDefault();_discoverShowSpecies('${encodeURIComponent(sp.scientific_name).replace(/'/g, "\\'")}')">

      ${thumb}
      <div class="nearme-info">
        <div class="nearme-name">${_esc(sp.scientific_name)}</div>
        ${common}
        <div class="nearme-meta">
          ${edibBadge}
          ${seasonBadge}
          <span class="nearme-dim">📏 ${dist}m</span>
          <span class="nearme-dim">· ${count} sighting${count !== 1 ? 's' : ''}</span>
        </div>
      </div>
    </a>`;
  }

  // Fallback radius hint when the result set is sparse (< 5) and we can widen.
  if (results.length < 5) html += _nearMeFallbackHint();

  list.innerHTML = html;
}

function _nearMeFallbackHint() {
  if (_nearMeRadius >= 1000) return '';
  const next = _nearMeRadius < 500 ? 500 : 1000;
  const nextLabel = next >= 1000 ? '1km' : next + 'm';
  return `<div class="nearme-fallback-hint">
    Few results — try widening to
    <a href="#" onclick="event.preventDefault();setNearMeRadius(${next})"><strong>${nextLabel}</strong></a>.
  </div>`;
}

// ── Discover view (Map Redesign P2 — merges Near me + Find) ───────────────
// Opened by the top-right search chip. Search field, Near me radius filter,
// and Find modes (season/recipes/medicinal) all share one results list.

let _discoverNearMeOn = false;
// Saved walk that was open when Find opened — _exitWalkMode clears _walkSaved,
// so 🍳 Make? (_openRecipesPage) reads the walk from here. null = none.
let _discoverWalkId = null;

function showDiscoverView() {
  _closeTabPanels();
  document.getElementById('filter-view').style.display = 'none';
  document.getElementById('detail-view').style.display = 'none';
  if (_walkActive) {
    _discoverWalkId = (_walkSaved && _walkSaved.id) || null;
    _exitWalkMode();
  } else if (!document.getElementById('discover-view').classList.contains('active')) {
    _discoverWalkId = null;
  }
  document.getElementById('discover-view').classList.add('active');
  openSidebar();
  // Discover draws on pins so surrounding sightings stay visible behind the sheet.
  currentLayer = 'pins';
  _pinsExplicit = false;
  _applyLayer();
  document.getElementById('map-search-input').focus();
  if (_discoverNearMeOn) { _beginNearMe(); } else { _runFindMode(_findMode); }
}

// Reset the Discover view + state when leaving it for another layer.
function _exitDiscoverView() {
  const view = document.getElementById('discover-view');
  const wasActive = view.classList.contains('active');
  view.classList.remove('active');
  _discoverWalkId = null;
  _nearMePos = null;
  _nearMeResults = [];
  // Restore the Filters tab if Discover was on screen.
  if (wasActive) showFilterView();
}

function _toggleDiscoverNearMe() {
  _discoverNearMeOn = !_discoverNearMeOn;
  document.getElementById('discover-nearme-toggle').classList.toggle('active', _discoverNearMeOn);
  const modeRow   = document.getElementById('find-mode-row');
  const inputRow  = document.getElementById('find-input-row');
  const optsRow   = document.getElementById('find-opts-row');
  const radiusRow = document.getElementById('nearme-radius-row');
  if (_discoverNearMeOn) {
    modeRow.style.display = 'none';
    inputRow.classList.remove('visible');
    optsRow.classList.remove('visible');
    _beginNearMe();
  } else {
    radiusRow.style.display = 'none';
    modeRow.style.display = '';
    document.getElementById('discover-sub').textContent = '';
    setFindMode(_findMode);
  }
}

// Shared result-tap action for the discover results list (in-season / recipes
// / medicinal / near-me cards): filter to that species and fit the map to its
// pins, mirroring the top search chip's existing species-select behaviour
// (_selectSearchItem). Display-only — does not touch edibility/identification data.
function _discoverShowSpecies(encodedName) {
  const name = decodeURIComponent(encodedName);
  filterState.species.clear();
  filterState.species.add(name);
  _updateFilterFab();
  renderMarkers();
  const pts = _heatAll.filter(pt => pt[2] === name);
  if (pts.length) {
    const lats = pts.map(pt => pt[0]);
    const lngs = pts.map(pt => pt[1]);
    map.fitBounds(
      [[Math.min(...lats), Math.min(...lngs)], [Math.max(...lats), Math.max(...lngs)]],
      { maxZoom: 14, padding: [50, 50], animate: true }
    );
  }
}

function showDetailView(p) {
  document.getElementById('filter-view').style.display = 'none';
  // Hide whichever tab panel is open
  if (_openToolbarPanel) {
    const _pe = document.getElementById('panel-' + _openToolbarPanel);
    const _be = document.getElementById('btn-panel-' + _openToolbarPanel);
    if (_pe) _pe.style.display = 'none';
    if (_be) _be.classList.remove('active');
    _openToolbarPanel = null;
  }
  document.getElementById('detail-view').style.display = 'flex';

  document.getElementById('discover-view').classList.remove('active');
  // Switch sidebar to detail mode: hide tab strip, slide pane in
  const _sid = document.getElementById('sidebar');
  _sid.classList.add('rp-detail');
  document.getElementById('rp-pane').classList.add('rp-open');
  if (isMobile()) document.getElementById('drawer-scrim').classList.add('show');
  // On mobile: show the FAB so user can reopen the sidebar after swiping it closed
  const _dvFab = document.getElementById('fab-filters');
  if (_dvFab && isMobile()) { _dvFab.style.display = 'flex'; _dvFab.textContent = '📍 Detail'; }
  _currentDetailObs = p;
  // Mini breadcrumb in back bar
  document.getElementById('detail-back-species').textContent =
    p.species_primary || 'Unknown species';
}

function backToFilters() {
  showFilterView();
}

let _touchStartY = 0;
document.getElementById('drawer-handle').addEventListener('touchstart', e => {
  _touchStartY = e.touches[0].clientY;
}, { passive: true });
document.getElementById('drawer-handle').addEventListener('touchend', e => {
  if (e.changedTouches[0].clientY - _touchStartY > 40) closeSidebar();
}, { passive: true });

