// ── Walk proximity alerts (10a.5) ────────────────────────────────────────
// watchPosition activates when _activeWalkRoute is set (field mode on).
// Clears in _exitWalkMode(). In-app only — no browser push notifications.
// Goethean hook placeholder wired in Phase 11c.

const _PROX_COOLDOWN_MS = 5 * 60 * 1000;  // 5-minute cooldown per pin
const _PROX_MAX_NOTIFS  = 3;               // oldest auto-dismissed on 4th arrival

let _proxWatchActive = false;
let _proxCooldowns   = {};  // pinKey → last-triggered timestamp
let _proxNotifs      = [];  // active notifications [{id, species, …}]
let _proxIdSeq       = 0;   // monotonic notification id

function _fieldModeOn() {
  return localStorage.getItem('foragingid_field_mode') !== 'false';
}
function _proxThresholdM() {
  return parseInt(localStorage.getItem('foragingid_prox_threshold') || '20', 10);
}

// Haversine distance in metres between two lat/lng pairs.
function _haversineM(lat1, lng1, lat2, lng2) {
  const R  = 6371000;
  const f1 = lat1 * Math.PI / 180, f2 = lat2 * Math.PI / 180;
  const df = (lat2 - lat1) * Math.PI / 180;
  const dl = (lng2 - lng1) * Math.PI / 180;
  const a  = Math.sin(df / 2) ** 2 + Math.cos(f1) * Math.cos(f2) * Math.sin(dl / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Bounding box of walk stops, with ~150 m buffer, as a quick pre-filter.
function _walkStopBbox(route) {
  let minLat = Infinity, maxLat = -Infinity, minLng = Infinity, maxLng = -Infinity;
  for (const s of route) {
    if (s.lat < minLat) minLat = s.lat;
    if (s.lat > maxLat) maxLat = s.lat;
    if (s.lng < minLng) minLng = s.lng;
    if (s.lng > maxLng) maxLng = s.lng;
  }
  const buf = 0.0015;  // ~150 m in degrees
  return { minLat: minLat - buf, maxLat: maxLat + buf, minLng: minLng - buf, maxLng: maxLng + buf };
}

// Called after _activeWalkRoute is set. No-op if field mode is disabled.
function _startProxWatch() {
  if (!_fieldModeOn()) return;
  if (!_activeWalkRoute || !_activeWalkRoute.length) return;
  _proxWatchActive = true;
  GPS.startWatch(_onProxPosition);
}

// Called in _exitWalkMode() — stops the GPS watch and clears all state.
function _stopProxWatch() {
  _proxWatchActive = false;
  GPS.stopWatch();
  _proxCooldowns = {};
  _proxNotifs    = [];
  _renderProxPanel();
}

// GPS.startWatch callback — check each walk stop against the threshold.
function _onProxPosition(pos) {
  if (!_proxWatchActive || !_activeWalkRoute) return;
  const bbox = _walkStopBbox(_activeWalkRoute);
  // Skip all work when user is clearly outside the walk bounding box.
  if (pos.lat < bbox.minLat || pos.lat > bbox.maxLat ||
      pos.lng < bbox.minLng || pos.lng > bbox.maxLng) return;

  const threshold = _proxThresholdM();
  const now       = Date.now();

  _activeWalkRoute.forEach(function (stop, idx) {
    const key = (stop.p && stop.p.id != null) ? 'obs_' + stop.p.id : 'stop_' + idx;
    if (_proxCooldowns[key] && now - _proxCooldowns[key] < _PROX_COOLDOWN_MS) return;
    const d = _haversineM(pos.lat, pos.lng, stop.lat, stop.lng);
    if (d <= threshold) {
      _proxCooldowns[key] = now;
      _fireProxAlert(stop, Math.round(d));
      // Log to active walk recording if one is running
      if (stop.p && stop.p.id != null && window.WalkRecorder && WalkRecorder.isRecording()) {
        WalkRecorder.logProximityEncounter(stop.p.id, new Date().toISOString());
      }
    }
  });
}

// Builds a notification object and prepends it to the stack.
// Lists EVERY species at the stop (_stopSpecies); each gets its own toxic guard
// at render time.
function _fireProxAlert(stop, distM) {
  const p       = stop.p || {};
  const species = _stopSpecies(stop).map(name => {
    const ed   = _activeWalkEnrich?.[name] || null;
    const pinP = (stop.pins || []).map(x => x.p).find(pp => pp.species_primary === name)
                 || (name === p.species_primary ? p : {});
    return {
      name:             name,
      common_name:      pinP.common_name ||
                        spPickCommon(ed?.species?.preferred_common_name, ed?.species?.common_names) || null,
      edibility_status: ed?.species?.edibility_status || pinP.edibility_status || null,
      safety:           (ed && ed._safety) || null,
    };
  });

  _proxNotifs.unshift({
    id:               ++_proxIdSeq,
    species:          species,
    distance_m:       distM,
    thumbnail:        p.thumbnail        || null,
    is_note:          p.is_note          || false,
  });
  // Auto-dismiss oldest when overflow
  if (_proxNotifs.length > _PROX_MAX_NOTIFS) {
    _proxNotifs = _proxNotifs.slice(0, _PROX_MAX_NOTIFS);
  }
  _renderProxPanel();
}

function _dismissProxAlert(id) {
  _proxNotifs = _proxNotifs.filter(function (n) { return n.id !== id; });
  _renderProxPanel();
}

function _renderProxPanel() {
  const panel = document.getElementById('walk-prox-panel');
  if (!panel) return;
  if (!_proxNotifs.length) {
    panel.style.display = 'none';
    panel.innerHTML = '';
    return;
  }
  panel.style.display = 'flex';
  panel.innerHTML = _proxNotifs.map(function (n) {
    const thumb  = n.thumbnail
      ? '<img class="walk-prox-thumb" src="' + _esc(n.thumbnail) + '" alt="" loading="lazy">'
      : '<div class="walk-prox-thumb walk-prox-thumb-empty"></div>';
    // One row per species at the stop. Toxic guard per species: blocked
    // species show the warning, never an edibility label.
    const spRows = n.is_note
      ? '<div><span class="walk-prox-name" style="font-style:normal">📝 Walk note</span></div>'
      : (n.species.length ? n.species : [{ name: null }]).map(function (sp, k) {
          const href   = sp.name ? '/species?s=' + encodeURIComponent(sp.name) : '#';
          const common = sp.common_name
            ? '<div class="walk-prox-common">' + _esc(spCommon(sp.common_name)) + '</div>'
            : '';
          const gate   = _culinaryGate(sp.safety);
          const edib   = (!gate.ok && gate.label) ? _culinaryGateBadge(gate)
            : sp.edibility_status
            ? '<span class="nearme-edib" style="' +
                _esc(_NEARME_EDIB_STYLE[sp.edibility_status] || _NEARME_EDIB_STYLE.unknown) +
                '">' + _esc(sp.edibility_status) + '</span>'
            : '';
          return '<div' + (k ? ' style="margin-top:4px"' : '') + '>' +
            '<a class="walk-prox-name" href="' + _esc(href) + '">' + _esc(sp.name || '?') + '</a>' +
            common +
            (edib ? '<div class="walk-prox-meta">' + edib + '</div>' : '') +
            // Batch 6: look-alike + preparation warnings, full text, collapsed.
            SafetyGate.warnings(sp.safety, { collapse: 'all' }) +
          '</div>';
        }).join('');
    return '<div class="walk-prox-card" data-id="' + n.id + '">' +
      '<button class="walk-prox-dismiss" onclick="_dismissProxAlert(' + n.id + ')" title="Dismiss">✕</button>' +
      '<div class="walk-prox-body">' + thumb +
        '<div class="walk-prox-info">' +
          spRows +
          '<div class="walk-prox-meta">' +
            '<span class="walk-prox-dist">📍 ' + n.distance_m + 'm away</span>' +
          '</div>' +
          '<!-- goethean_prompt_placeholder -->' +
          '<div class="walk-prox-goethean"></div>' +
        '</div>' +
      '</div>' +
    '</div>';
  }).join('');
}

