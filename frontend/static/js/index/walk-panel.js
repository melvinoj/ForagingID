// ── Season helpers for walk panel ─────────────────────────────────────────

function _currentSeason() {
  const m = new Date().getMonth() + 1; // 1-12
  if (m >= 3 && m <= 5) return 'spring';
  if (m >= 6 && m <= 8) return 'summer';
  if (m >= 9 && m <= 11) return 'autumn';
  return 'winter';
}

// Export summary recipe choice — the experience export's rule
// (scripts/experience_export/export.py, recipe_source_priority): human-authored
// first (curator), then Melvin's own menu (any other named source), then
// ai_generated; within a source preferred first, then oldest. Never a
// medicinal preparation; a dish already shown elsewhere in the summary is
// skipped. `shown` is the summary-wide set of dish titles (lower case).
// Recipes arrive already filtered by the toxic guard (empty when blocked).
// Recipe display title — JS twin of app/models/species.recipe_display_title
// (the one rule, also the experience export's): the recipe's title; else its
// first heading; else the first line that is not a blockquote, a rule or a
// safety note (a safety note takes its whole paragraph) — first sentence,
// capped at 120. A safety note is never a title. Keep the two in step.
function _recipeMdPlain(line) {
  return line.trim().replace(/^[#>\s]+/, '').replace(/[*_`]+/g, '').trim()
    .replace(/^(recipe\s*title|recipe|title)\s*:\s*/i, '').replace(/:+$/, '').trim();
}
function _isSafetyNoteLine(plain) { return /^(safety|caution|warning)\b/i.test(plain.trim()); }
// A section heading ("## Ingredients", "Method:") is never a title (_RECIPE_SECTION_HEADINGS).
const _RECIPE_SECTION_HEADINGS = new Set(['ingredients', 'ingredient', 'method', 'methods', 'instructions',
  'directions', 'steps', 'notes', 'note', 'serves', 'to serve', 'serving', 'preparation', 'equipment', 'tips',
  'variations', 'you will need', 'for the dressing', 'for the sauce', 'storage', 'makes']);
function _isSectionHeading(t) { return _RECIPE_SECTION_HEADINGS.has(t.trim().replace(/:+$/, '').toLowerCase()); }
function _recipeTitle(r) {
  if ((r.title || '').trim()) return r.title.trim();
  const lines = String(r.body || '').replace(/\r/g, '').split('\n');
  for (const line of lines) {
    if (/^\s*#{1,6}\s/.test(line)) {
      const t = _recipeMdPlain(line);
      if (t && !_isSafetyNoteLine(t) && !_isSectionHeading(t)) return t;
    }
  }
  let inNote = false;
  for (const line of lines) {
    const raw = line.trim();
    if (!raw || /^([-*_]\s*){3,}$/.test(raw)) { inNote = false; continue; }
    if (raw.startsWith('>')) continue;
    let t = _recipeMdPlain(raw);
    if (t && _isSafetyNoteLine(t)) inNote = true;
    if (!t || inNote || _isSectionHeading(t) || /^\s*#{1,6}\s/.test(raw)) continue;
    const m = t.match(/^(.+?[.!?])(\s|$)/);
    if (m) t = m[1];
    if (t.length > 120) t = t.slice(0, 119).replace(/\s+\S*$/, '').replace(/[,;:—-]+$/, '') + '…';
    return t;
  }
  return '';
}

function _summaryRecipe(recipes, shown) {
  const rank = r => r.source === 'curator' ? 0 : (r.source === 'ai_generated' ? 2 : 1);
  const sorted = (recipes || [])
    .filter(r => !r.is_medicinal_prep)
    .slice()
    .sort((a, b) => (rank(a) - rank(b)) || ((b.is_preferred ? 1 : 0) - (a.is_preferred ? 1 : 0)) || (a.id - b.id));
  for (const r of sorted) {
    const dish = _recipeTitle(r).toLowerCase();
    if (dish && shown.has(dish)) continue;
    if (dish) shown.add(dish);
    return r;
  }
  return null;
}


// ── Render walk panel ──────────────────────────────────────────────────────

function renderWalkPanel(route, enrichMap) {
  _syncWalkLoopUi();                 // Loop / One-way label follows the rendered route
  // Hide empty state and restore route controls whenever a route is rendered
  _wbsHideEmptyState();
  _wbsRestoreRouteContent();
  // On laptop: mark route active (hides quickbar) and open the sheet
  if (!isMobile()) {
    const _wbsEl = document.getElementById('walk-bottom-sheet');
    if (_wbsEl) {
      _wbsEl.classList.add('wbs-route-active');
      if (!_wbsEl.classList.contains('wbs-open')) {
        _wbsEl.classList.add('wbs-open');
        const _chevEl = document.getElementById('wbs-chevron');
        if (_chevEl) _chevEl.textContent = '▾';
      }
    }
  }

  const titleEl = document.getElementById('walk-title');
  const subEl   = document.getElementById('walk-sub');
  if (titleEl) titleEl.textContent = _walkTitleText(route);

  // Show the header block on desktop (phone uses wbs-summary instead)
  const hdrBlock = document.getElementById('wbs-header-block');
  if (hdrBlock) hdrBlock.style.display = isMobile() ? 'none' : 'block';

  // Route status (stop cap / ORS failure / straight line) — replaces the old
  // always-the-same "ORS key not configured" note.
  _renderWalkRouteStatus();

  // Distance + duration: prefer ORS values when available
  let totalM = _walkOrsDistM > 0 ? _walkOrsDistM : 0;
  const _straightEst = !totalM;
  if (!totalM) {
    for (let i = 1; i < route.length; i++) {
      totalM += _haversineM(route[i-1].lat, route[i-1].lng, route[i].lat, route[i].lng);
    }
  }
  const distStr = (totalM < 1000
    ? `~${Math.round(totalM)}m`
    : `~${(totalM / 1000).toFixed(1)}km`) + (_straightEst ? ' straight-line' : '');
  const timeStr = _walkOrsDurMin > 0
    ? ` · ~${_walkOrsDurMin} min`
    : ` · ~${Math.round(totalM / 80)} min`;

  // Build maps export URLs
  _buildMapsUrls(route);

  // Sub-header: species count (exclude note stops) + distance + time
  const _uniqSp = new Set(route.flatMap(_stopSpecies)).size;
  subEl.textContent = `${_uniqSp} species · ${route.length} stop${route.length !== 1 ? 's' : ''} · ${distStr} total${timeStr}`;

  // Load saved walks list
  loadSavedWalksList();

  // Stop cards
  const _season = _currentSeason();
  const _seasonIcon = { spring: '🌱', summer: '☀️', autumn: '🍂', winter: '❄️', 'year-round': '🔄' };
  let html = '';
  const _repeatSplit = _walkRepeatSplit(route);
  // The panel shows the loaded saved walk itself (not a route rebuilt from a
  // drawn area meanwhile) — reorder actions act on that saved row.
  const _isSavedRoute = _onSavedRoute(route);
  for (let i = 0; i < route.length; i++) {
    const { p, lat, lng } = route[i];

    // Note stop — compact amber card
    if (p.is_note) {
      const distFromPrevN = i === 0 ? null : _haversineM(route[i-1].lat, route[i-1].lng, lat, lng);
      const dstrN = distFromPrevN === null ? '' : distFromPrevN < 1000
        ? `${Math.round(distFromPrevN)}m` : `${(distFromPrevN/1000).toFixed(1)}km`;
      html += `<div class="walk-stop-card" style="border-left:3px solid #f59e0b">
        <div class="walk-stop-header">
          <span class="walk-stop-num" style="background:#f59e0b">${_esc(_stopLabel(route[i], i))}</span>
          <span style="font-size:0.8rem;font-weight:600;color:#92400e">📝 Field Note</span>
          ${dstrN ? `<span class="walk-stop-dist">${dstrN}</span>` : ''}
        </div>
        <div style="font-size:0.78rem;color:#555;margin-top:4px;line-height:1.4;white-space:pre-wrap">${_esc((p.text||'').slice(0,200))}</div>
        ${(p.species_tags||[]).length ? `<div style="margin-top:4px">${p.species_tags.map(t=>`<em style="font-size:0.71rem;color:#2d5016">${_esc(t)}</em>`).join(', ')}</div>` : ''}
      </div>`;
      continue;
    }

    const distFromPrev = i === 0 ? null
      : _haversineM(route[i-1].lat, route[i-1].lng, lat, lng);
    const distStr2 = distFromPrev === null ? '' : (
      distFromPrev < 1000 ? `${Math.round(distFromPrev)}m` : `${(distFromPrev/1000).toFixed(1)}km`
    );

    // One stop can hold several species (centroid clustering) — one section
    // per species, each with its own toxic guard.
    const _stop    = route[i];
    if (_walkStopEmpty(_stop)) continue;      // hidden (batch 15b) — label numbering kept
    const _spList  = _stopSpecies(_stop);
    let speciesHtml = '';
    for (const spName of _repeatSplit[i].full) {
      const _enrichData = enrichMap[spName];
      const spData   = _enrichData?.species  || null;
      // Pin properties for this species (common name / edibility on the map
      // pin); loaded walks have no pins, so fall back to the culinary profile.
      const pinP = (_stop.pins || []).map(x => x.p).find(pp => pp.species_primary === spName)
                   || (spName === p.species_primary ? p : {});
      const commonName = pinP.common_name
                         || spPickCommon(spData?.preferred_common_name, spData?.common_names) || '';
      const edib = spData?.edibility_status || pinP.edibility_status;

      // Toxic guard (_culinaryGate): the edibility badge only when toxicity is
      // 'none'; fails closed when it could not be read.
      const _gate      = _culinaryGate(_enrichData ? _enrichData._safety : null);

      // Stop card = name, common name, badge, profile link, and the curator's
      // own foraging notes (species card) — first ~160 chars, plain text, or
      // nothing. No recipe and no edible-parts/taste hint: those live in the
      // Export summary, the experience page and the species page. The notes are
      // Melvin-authored, so not behind the culinary gate.
      let forNotesHtml = '';
      const fnotes = (spData?.foraging_notes || '').trim();
      if (fnotes) {
        const fsnip = fnotes.length > 160 ? fnotes.slice(0, 157) + '…' : fnotes;
        forNotesHtml = `<div style="font-size:0.75rem;color:#555;margin:3px 0 4px;line-height:1.4">${_esc(fsnip)}</div>`;
      }

      // Blocked species (toxic/deadly/unknown): the badge is the toxicity
      // warning, never an edibility label (whatever edibility_status says).
      const edibBadge = _walkEdibBadge(_gate, edib);

      speciesHtml += `<div class="walk-stop-sp"${speciesHtml ? ' style="border-top:1px dashed #e3ead7;margin-top:6px;padding-top:6px"' : ''}>
        <span class="walk-stop-species">${_esc(spName)}</span>
        ${commonName ? `<div class="walk-stop-common">${_esc(spCommon(commonName))}</div>` : ''}
        <div class="walk-stop-meta">
          ${edibBadge}
          ${_walkMemberChips(_stop, spName)}
          <a href="/species?s=${encodeURIComponent(spName)}"
             style="font-size:0.68rem;color:#2d5016;margin-left:8px">Species profile →</a>
        </div>
        ${SafetyGate.warnings(_gate.safety, { collapse: 'auto' })}
        ${forNotesHtml}
        ${spData && spData.id ? `<div class="walk-guest-note" data-guest-note-sid="${spData.id}" data-guest-note-name="${_esc(spName)}"></div>` : ''}
      </div>`;
    }

    // Repeats: one compact line each — safety badge only (☠ toxic/deadly,
    // ⚠ toxicity unknown, or caution), no recipe, no edible-parts text.
    let alsoHtml = '';
    for (const rp of _repeatSplit[i].repeats) {
      const _ed   = enrichMap[rp.name];
      const _g    = _culinaryGate(_ed ? _ed._safety : null);
      const _pin  = (_stop.pins || []).map(x => x.p).find(pp => pp.species_primary === rp.name) || {};
      const _edib = _ed?.species?.edibility_status || _pin.edibility_status;   // same source as the full card
      const _b    = _g.label ? _walkEdibBadge(_g, _edib) : '';   // safety signals only (☠ / ⚠ / caution)
      alsoHtml += `<div class="walk-stop-also" style="font-size:0.75rem;color:#556040;margin-top:4px">
        Also here: ${_b} ${spNameHtml(rp.name, _spCommonFor(rp.name))}${_walkMemberChips(_stop, rp.name)} — see stop ${_esc(rp.first_label)}
      </div>`;
    }

    const _joinedStop = _stop.origin === 'joined';
    // "Start here" on every saved stop of a saved walk (batch 15b), not the
    // current stop 1 and not a 7a stop (not a waypoint until Renumber stops).
    // walkStartHere: a closed stored line rotates (no ORS); an open one goes
    // through the Re-route preview (k…N, then back k−1…1).
    const _canStartHere = !!(_savedWalkData && !_joinedStop && _isSavedRoute
                             && /^\d+$/.test(_stopLabel(_stop, i)) && _stopLabel(_stop, i) !== '1');
    html += `<div class="walk-stop-card"${_joinedStop ? ' style="border-style:dashed"' : ''}>
      <div>
        <span class="walk-stop-num"${_joinedStop ? ' style="background:#5f8f35"' : ''}>${_esc(_stopLabel(_stop, i))}</span>
        ${_joinedStop ? `<span style="font-size:0.72rem;color:#556040;font-weight:600">new stop · </span>` : ''}
        ${_stop.off_route_m ? `<span style="font-size:0.72rem;color:#92400e;font-weight:600">${_stop.off_route_m} m off route · </span>` : ''}
        ${_spList.length > 1 ? `<span style="font-size:0.72rem;color:#556040;font-weight:600">${_spList.length} species here</span>` : ''}
        ${distStr2 ? `<span class="walk-stop-dist">${_esc(distStr2)}</span>` : ''}
        ${_canStartHere ? `<button data-guest-hide onclick="walkStartHere(${lmJsArg(_stopLabel(_stop, i))})"
            title="${_walkLineClosed ? 'Make this stop 1 — same line, direction and distance' : 'Make this stop 1 — walk on to the end, then back the other way (Re-route preview first)'}"
            style="float:right;font-size:0.66rem;padding:1px 6px;border-radius:4px;border:1px solid #b8d48a;background:#f0f4e8;color:#2d5016;cursor:pointer">Start here</button>` : ''}
      </div>
      ${speciesHtml}${alsoHtml}
      ${(speciesHtml || alsoHtml) ? '' : `<div style="font-size:0.75rem;color:#999;margin-top:4px">No confirmed species here now</div>`}
    </div>`;
  }
  document.getElementById('walk-stops-scroll').innerHTML = html;
  // Guest notes (batch 8): a participant gets "📝 Add a note" on each species.
  GuestNotes.isParticipant().then(ok => {
    if (!ok) return;
    document.querySelectorAll('#walk-stops-scroll .walk-guest-note').forEach(el => {
      el.innerHTML = '<button type="button" style="font-size:0.75rem;margin-top:4px">📝 Add a note</button>';
      el.querySelector('button').onclick = () =>
        GuestNotes.mount(el, Number(el.dataset.guestNoteSid), el.dataset.guestNoteName);
    });
  });
  _syncWalkSaveBtn();          // loaded walk: "Save changes (N)"; new walk: "Save walk"

  // Bottom sheet summary (phone only — mirrors walk-title / walk-sub for the sheet)
  _wbsUpdateSummary(route);
}

// Loaded saved walk: per-species membership chips (walk_membership.py).
//   AI-agreed — confirmed only by P1's dual-API auto-approve, no human review
//   new       — joined after the walk was saved (route proximity / accepted older)
// The ✕ removes proximity-joined photos of that species at this stop (curator).
function _walkMemberChips(stop, spName) {
  const info = (stop.spInfo || []).find(x => x.name === spName);
  if (!info) return '';
  let h = '';
  if (!info.human) {
    h += `<span title="Confirmed by two identification services agreeing — not reviewed by a person"
             style="font-size:0.64rem;padding:1px 5px;border-radius:4px;margin-left:5px;
                    background:#eef2ff;color:#3730a3;font-weight:600">AI-agreed</span>`;
  }
  if (info.joined) {
    const ids = (info.obs_ids || []).filter(id => (stop.joined_obs_ids || []).includes(id));
    h += `<span title="Joined after the walk was saved"
             style="font-size:0.64rem;padding:1px 5px;border-radius:4px;margin-left:5px;
                    background:#ecfccb;color:#3f6212;font-weight:600">new</span>`;
    if (ids.length) {
      h += `<button data-guest-hide onclick="walkExcludeJoined([${ids.join(',')}])"
               title="Remove from this walk"
               style="margin-left:4px;font-size:0.64rem;padding:0 5px;border:1px solid #d6d3d1;
                      border-radius:4px;background:#fff;color:#78716c;cursor:pointer">✕</button>`;
    }
  }
  return h;
}

// ── Walk bottom sheet: summary section ─────────────────────────────────────
function _wbsUpdateSummary(route) {
  const el = document.getElementById('wbs-summary');
  if (!el) return;
  if (!route || !route.length) { el.style.display = 'none'; return; }

  const uniqSp = new Set(route.flatMap(_stopSpecies)).size;
  const stopWord = route.length === 1 ? 'stop' : 'stops';

  // Re-use ORS distance if available, else haversine sum
  let totalM = _walkOrsDistM > 0 ? _walkOrsDistM : 0;
  if (!totalM) {
    for (let i = 1; i < route.length; i++) {
      totalM += _haversineM(route[i-1].lat, route[i-1].lng, route[i].lat, route[i].lng);
    }
  }
  const distStr = totalM < 1000
    ? `~${Math.round(totalM)}m`
    : `~${(totalM / 1000).toFixed(1)}km`;
  const durMin = _walkOrsDurMin > 0 ? _walkOrsDurMin : Math.round(totalM / 80);

  document.getElementById('wbs-summary-title').textContent =
    _walkSavedNameFor(route) ? _walkTitleText(route) : `🥾 Walk route · ${route.length} ${stopWord}`;
  document.getElementById('wbs-summary-sub').textContent =
    `${uniqSp} species · ${distStr} · ~${durMin} min`;
  // Phone only — on laptop the walk-title header block shows the same thing.
  el.style.display = isMobile() ? 'block' : 'none';
}

// ── Walk title: saved name while the route is the one saved/loaded ─────────
// Signature = stop positions + circular flag. Regrouping (radius slider) or a
// new selection changes it, and the title falls back to the stop count.
function _walkRouteSig(route) {
  return (_walkCircular ? 'c|' : 'o|') +
    (route || []).map(s => `${s.lat.toFixed(6)},${s.lng.toFixed(6)}`).join(';');
}

function _walkSavedNameFor(route) {
  return _walkSaved && route && route.length && _walkSaved.sig === _walkRouteSig(route)
    ? _walkSaved.name : null;
}

function _walkTitleText(route) {
  const name = _walkSavedNameFor(route);
  if (name) return `🥾 ${name}`;
  const n = route ? route.length : 0;
  return `🥾 Walk Route (${n} stop${n !== 1 ? 's' : ''})`;
}

// Re-title header, phone summary and minimise bar without re-rendering stops.
function _walkRefreshTitles() {
  const route = _activeWalkRoute;
  if (!route || !route.length) return;
  const titleEl = document.getElementById('walk-title');
  if (titleEl) titleEl.textContent = _walkTitleText(route);
  _wbsUpdateSummary(route);
  const bar = document.getElementById('walk-min-bar');
  if (bar && bar.classList.contains('visible')) {
    document.getElementById('wmb-name').textContent = _walkTitleText(route).replace('🥾 ', '');
  }
}

// ── Walk bottom sheet: lasso-selected species ──────────────────────────────
function _wbsRenderLasso() {
  console.log('[wbs] _wbsRenderLasso() called — _walkActive:', _walkActive, '| ForagingList:', ForagingList.species());
  const el = document.getElementById('wbs-lasso');
  if (!el) return;
  const selected = ForagingList.species();
  if (!selected.length) { el.style.display = 'none'; return; }

  // Build a lookup from allFeatures: scientific_name → first matching feature props
  const lookup = {};
  for (const f of allFeatures) {
    const p = f.properties;
    if (p.species_primary && !lookup[p.species_primary]) lookup[p.species_primary] = p;
  }

  const edibColour = {
    edible:   { bg: '#d1f5da', fg: '#166534', label: '✓ edible' },
    caution:  { bg: '#fef3c7', fg: '#92400e', label: '⚠ caution' },
    toxic:    { bg: '#dc2626', fg: '#fff',    label: '✗ toxic' },
    inedible: { bg: '#fef3c7', fg: '#854d0e', label: '✗ not edible' },
    unknown:  { bg: '#f3f3f3', fg: '#666',    label: 'unknown' },
  };

  const rows = selected.map(name => {
    const p = lookup[name] || {};
    const common = p.common_name || spPickCommon(p.preferred_common_name, p.common_names) || '';
    const edib = p.edibility_status || '';
    const ec = edibColour[edib] || { bg: '#f3f3f3', fg: '#666', label: edib };
    // Toxic guard: toxicity comes from the walk enrichment (map pins carry
    // none); a species not enriched yet fails closed to "toxicity unknown".
    const gate = _culinaryGate(_activeWalkEnrich?.[name]?._safety ?? null);
    const edibTag = (!gate.ok && gate.label)
      ? _culinaryGateBadge(gate)
      : edib
      ? `<span class="wbs-lasso-edib" style="background:${ec.bg};color:${ec.fg}">${ec.label}</span>`
      : '';
    return `<div class="wbs-lasso-item">
      <span class="wbs-lasso-name">${_esc(name)}</span>
      ${common ? `<span class="wbs-lasso-common">${_esc(spCommon(common))}</span>` : ''}
      ${edibTag}
      <a class="wbs-lasso-link" href="/species?s=${encodeURIComponent(name)}" target="_blank">Profile →</a>
    </div>`;
  }).join('');

  document.getElementById('wbs-lasso-count').textContent = selected.length;
  document.getElementById('wbs-lasso-list').innerHTML = rows;
  el.style.display = 'block';
  console.log('[wbs] #wbs-lasso shown — count:', selected.length, '| el.style.display:', el.style.display);
}

// ── Maps export URLs ───────────────────────────────────────────────────────

function _buildMapsUrls(route) {
  const noteEl = document.getElementById('walk-gmaps-note');
  if (!route.length) { if (noteEl) noteEl.style.display = 'none'; return; }

  // Google Maps walking route takes 10 points: origin + 8 waypoints +
  // destination. They are spread EVENLY BY DISTANCE along the whole walk line
  // (the drawn route; else the stops joined in order, back to the start for a
  // circular walk), so the link covers the full loop rather than the first 10
  // stops. A circular line ends where it starts, so the destination is the start.
  const line = _walkLinePoints(route);
  const use  = _samplePolyline(line, 10).map(([la, ln]) => `${la.toFixed(6)},${ln.toFixed(6)}`);
  const origin = use[0];
  const dest   = use[use.length - 1];
  const wpts   = use.length > 2 ? use.slice(1, -1).join('|') : '';
  const gUrl = 'https://www.google.com/maps/dir/?api=1'
    + `&origin=${encodeURIComponent(origin)}`
    + `&destination=${encodeURIComponent(dest)}`
    + (wpts ? `&waypoints=${encodeURIComponent(wpts)}` : '')
    + '&travelmode=walking';
  document.getElementById('walk-google-btn').href = gUrl;
  if (noteEl) {
    const many = line.length > 10;
    noteEl.textContent = many
      ? 'Google Maps takes 10 points — they are spread evenly along the whole route; use Download GPX for the exact track.'
      : '';
    noteEl.style.display = many ? 'block' : 'none';
  }
}

// The walk as a line of [lat, lng]: the drawn route geometry when there is one
// (ORS / saved shape), else the stops in order (+ back to start if circular).
function _walkLinePoints(route) {
  if (_walkRouteGeom && Array.isArray(_walkRouteGeom.coordinates) && _walkRouteGeom.coordinates.length > 1) {
    return _walkRouteGeom.coordinates.map(([lng, lat]) => [lat, lng]);
  }
  const pts = (route || []).map(s => [s.lat, s.lng]);
  return (_walkCircular && pts.length > 1) ? [...pts, pts[0]] : pts;
}

// n points evenly spaced by distance along a polyline (first and last included).
function _samplePolyline(pts, n) {
  if (pts.length <= n) return pts.slice();
  const cum = [0];
  for (let i = 1; i < pts.length; i++) {
    cum.push(cum[i - 1] + _haversineM(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1]));
  }
  const total = cum[cum.length - 1];
  if (!total) return [pts[0]];
  const out = [];
  let j = 1;
  for (let k = 0; k < n; k++) {
    const target = total * k / (n - 1);
    while (j < pts.length - 1 && cum[j] < target) j++;
    const seg = cum[j] - cum[j - 1];
    const t = seg ? Math.min(1, Math.max(0, (target - cum[j - 1]) / seg)) : 0;
    out.push([pts[j - 1][0] + t * (pts[j][0] - pts[j - 1][0]),
              pts[j - 1][1] + t * (pts[j][1] - pts[j - 1][1])]);
  }
  return out;
}

// GPX 1.1 of the whole walk: the full line as a track + every stop as a
// waypoint named by its label ("7", "7a") with its species.
function walkDownloadGpx() {
  const route = _activeWalkRoute || [];
  const line  = _walkLinePoints(route);
  if (!line.length) { alert('No walk route to export.'); return; }
  const x = window.lmEsc;   // XML-safe too (static/js/esc.js)
  const name = (_walkSavedNameFor(route) || _walkTitleText(route).replace('🥾 ', '')).trim() || 'Walk';
  const wpts = route.map((s, i) => {
    const sp = s.p && s.p.is_note ? 'Field note' : _stopSpecies(s).join(', ');
    return `  <wpt lat="${s.lat.toFixed(7)}" lon="${s.lng.toFixed(7)}"><name>${x('Stop ' + _stopLabel(s, i))}</name>` +
           (sp ? `<desc>${x(sp)}</desc>` : '') + `</wpt>`;
  }).join('\n');
  const trkpts = line.map(([la, ln]) => `      <trkpt lat="${la.toFixed(7)}" lon="${ln.toFixed(7)}"/>`).join('\n');
  const gpx = `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<gpx version="1.1" creator="LandMemory" xmlns="http://www.topografix.com/GPX/1/1">\n` +
    `  <metadata><name>${x(name)}</name></metadata>\n` +
    `${wpts}\n` +
    `  <trk><name>${x(name)}</name><trkseg>\n${trkpts}\n    </trkseg></trk>\n</gpx>\n`;
  const blob = new Blob([gpx], { type: 'application/gpx+xml' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name.replace(/[^\wÀ-ɏ -]+/g, '').replace(/\s+/g, '_') + '.gpx';
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

