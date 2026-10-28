// ── Pin click ─────────────────────────────────────────────────────────────

function handlePinClick(p, lat, lng, marker) {
  // A saved walk is loaded: a pin tap NEVER opens the species card (Melvin,
  // 20 Oct 2026). Edit walk on → select / deselect; off → its name label only.
  // Species cards stay reachable from the stop cards ("Species profile →").
  // Outside a loaded saved walk everything below is unchanged.
  if (_savedWalkView) {
    if (_walkPinSel) _walkPinToggle(p);
    else if (marker && p.species_primary) {
      marker.bindTooltip(spNameHtml(p.species_primary, p.common_name),
        { direction: 'top', offset: [0, -10], className: 'walk-pin-label' }).openTooltip();
    }
    return;
  }
  // In select mode, a tap toggles the species in/out of the /lists selection
  // and does nothing else (no detail panel, no fly-to).
  if (_selectMode) { _selectModeToggle(p); return; }

  // Deselect previous pin, then select the clicked one
  _deselectPin();
  if (marker) {
    marker.setIcon(makeSelectedIcon());
    _selectedPinMarker = marker;
    _selectedPinObs    = p;
  }

  const targetZoom = Math.max(map.getZoom(), 15);
  map.flyTo([lat, lng], targetZoom, { duration: 0.6, easeLinearity: 0.5 });
  setTimeout(() => {
    showDetail(p);
    if (isMobile()) openSidebar();
  }, 80);
}

// ── Enrichment cache ──────────────────────────────────────────────────────
const _enrichCache = new Map();

async function _fetchEnrichment(speciesName) {
  if (_enrichCache.has(speciesName)) return _enrichCache.get(speciesName);
  try {
    const r = await fetch(`/api/culinary/${encodeURIComponent(speciesName)}`);
    if (!r.ok) { _enrichCache.set(speciesName, null); return null; }
    const data = await r.json();
    const result = { ci: data.culinary, aiFields: new Set(data.ai_generated_fields || []),
                     safety: data.safety || null };   // batch 5 safety gate (served decision)
    _enrichCache.set(speciesName, result);
    return result;
  } catch (_) {
    _enrichCache.set(speciesName, null);
    return null;
  }
}

// ── Detail panel — the main event ─────────────────────────────────────────

function showDetail(p) {
  // Switch sidebar to detail mode
  showDetailView(p);

  const scroll = document.getElementById('detail-scroll');

  const thumbName = p.thumbnail ? p.thumbnail.split('/').pop() : null;
  const thumb = thumbName
    ? `<img class="obs-thumb" src="/thumbnails/${_esc(thumbName)}"
           loading="lazy"
           onclick="openPhotoLightbox(${p.id})"
           onerror="this.style.display='none'"
           title="Click to enlarge">`
    : '';

  const date   = p.taken_at
    ? new Date(p.taken_at).toLocaleDateString('en-GB', {day:'numeric',month:'short',year:'numeric'})
    : 'Date unknown';
  const conf   = p.confidence != null ? `${(p.confidence * 100).toFixed(0)}%` : '—';
  const month  = monthOfDate(p.taken_at);
  const season = month ? ({ spring:'🌱 Spring', summer:'☀️ Summer', autumn:'🍂 Autumn', winter:'❄️ Winter' }[seasonOfMonth(month)] || '') : '';

  // ── Status badge ──────────────────────────────────────────────────────
  let badge;
  if (p.human_corrected) {
    badge = '<span class="badge badge-human">✏ Human verified</span>';
  } else if (p.has_enrichment) {
    badge = '<span class="badge badge-enriched">✓ Confirmed &amp; enriched</span>';
  } else {
    badge = '<span class="badge badge-confirmed">✓ Confirmed</span>';
  }

  // ── Species name block ────────────────────────────────────────────────
  const isLandscapeObs = (p.obs_category || 'plant').toLowerCase() === 'landscape';
  const _allCommon = (p.common_names && p.common_names.length)
    ? p.common_names
    : (p.common_name ? [p.common_name] : []);

  let speciesBlock;
  if (isLandscapeObs) {
    // Landscape: show scene description instead of species block
    const descText = p.description ? _esc(p.description) : '';
    speciesBlock = `<div style="font-size:0.78rem;color:#1e3a5f;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;margin-bottom:4px">🏞 Scene / Landscape</div>
      ${descText
        ? `<div style="font-size:0.85rem;color:#333;line-height:1.5;padding:6px 10px;background:#f0f7ff;border-left:3px solid #3b82f6;border-radius:0 5px 5px 0">${descText}</div>`
        : `<div data-guest-hide style="font-size:0.82rem;color:#888;font-style:italic">No description added yet — edit in review queue</div>`}`;  // curator prompt; guests see the heading only
  } else if (p.species_primary) {
    const commonLine = _allCommon.length
      ? `<div class="det-common-name">${_esc(spCommon(_allCommon[0]))}</div>` : '';
    const extraCommon = _allCommon.length > 1
      ? `<div class="meta-row" style="color:#888">${_esc(spCommonList(_allCommon.slice(1)))}</div>` : '';
    const renameBtn = `<button class="rename-btn" title="Correct species name"
        onclick="openRenameForm(${p.id}, ${lmJsArg(p.species_primary)})">✎ rename</button>`;
    speciesBlock = `${commonLine}
      <div class="det-sci-name">${_esc(p.species_primary)} ${renameBtn}</div>
      ${extraCommon}
      <div id="rename-form-${p.id}" class="rename-form" style="display:none">
        <label>Correct scientific name</label>
        <input type="text" id="rename-sci-${p.id}" value="${_esc(p.species_primary)}"
               placeholder="e.g. Urtica dioica" autocomplete="off">
        <label>Primary common name (optional)</label>
        <input type="text" id="rename-common-${p.id}" placeholder="e.g. Stinging nettle" autocomplete="off">
        <div class="rename-actions">
          <button class="btn-rename-save" id="rename-save-${p.id}"
            onclick="saveSpeciesRename(${p.id}, ${lmJsArg(p.species_primary)})">Save &amp; re-enrich</button>
          <button class="btn-rename-cancel"
            onclick="document.getElementById('rename-form-${p.id}').style.display='none'">Cancel</button>
        </div>
        <div id="rename-result-${p.id}"></div>
      </div>`;
  } else {
    // Edge case: confirmed observation without species (shouldn't happen after Fix 13)
    speciesBlock = `<div class="det-unknown">Species not identified</div>
      <div class="det-species-edit">
        <label>Enter species name to correct:</label>
        <input type="text" id="species-edit-${p.id}" placeholder="e.g. Urtica dioica" autocomplete="off">
        <button class="edit-save-btn" onclick="saveSpeciesCorrection(${p.id})">Save</button>
      </div>`;
  }

  // ── Action buttons ────────────────────────────────────────────────────
  const profileLink = (!isLandscapeObs && p.species_primary)
    ? `<a class="det-btn primary" href="/species?s=${encodeURIComponent(p.species_primary)}">View species profile →</a>`
    : '';

  // "Send to review queue" — only for non-landscape missing species
  const reviewBtn = (!isLandscapeObs && !p.species_primary)
    ? `<button class="det-btn" onclick="sendToReview(${p.id})">🔍 Send to review queue</button>`
    : '';

  // "Enrich this species" — shown when confirmed but not yet enriched (not landscape)
  const enrichBtn = (!isLandscapeObs && p.species_primary && !p.has_enrichment)
    ? `<button class="det-btn enrich" id="enrich-btn-${p.id}"
         onclick="enrichSpeciesFromMap(${lmJsArg(p.species_primary)}, ${p.id})">⚡ Enrich this species</button>`
    : '';

  const removeBtn = `<button class="det-btn danger"
    onclick="showRemoveConfirm(${p.id})" title="Mark as rejected — removes from map">
    🚫 Remove from map</button>`;
  const deleteBtn = `<button class="det-btn danger" style="border-color:#991b1b"
    onclick="showDeleteDialog(${p.id})" title="Permanently delete this observation record">
    🗑 Delete permanently</button>`;

  // ── Enrichment slot (async populated below; not shown for landscape) ──
  const enrichSlot = (!isLandscapeObs && p.species_primary)
    ? `<div id="det-enrich-${p.id}" class="map-enrich">
         <div class="map-enrich-loading">Loading enrichment data…</div>
       </div>`
    : '';

  // ── Enrich result slot (for feedback after enriching) ─────────────────
  const enrichResultSlot = `<div id="enrich-result-${p.id}"></div>`;

  scroll.innerHTML = `
    ${thumb}
    ${badge}
    ${speciesBlock}
    <div class="meta-row">📅 ${date}${season ? '  ·  ' + season : ''}</div>
    ${(!isLandscapeObs && p.species_primary) ? `<div class="meta-row">🎯 Confidence: ${conf}</div>` : ''}
    <div class="det-actions">
      ${profileLink}
      ${enrichBtn}
      ${reviewBtn}
    </div>
    ${enrichResultSlot}
    ${enrichSlot}
    <div class="det-actions" style="margin-top:8px">
      ${removeBtn}
      ${deleteBtn}
    </div>
    ${!isLandscapeObs ? ReID.render(p.id, p.species_primary, p.obs_category) : ''}`;

  // Async: inject enrichment snippet (not for landscape)
  if (!isLandscapeObs && p.species_primary) {
    _injectEnrichment(p.id, p.species_primary);
  }

  // Callback: re-identify confirmed
  window._reidOnConfirmed = (obsId, info) => {
    const feat = allFeatures.find(f => f.properties.id === obsId);
    if (feat) {
      feat.properties.species_primary = info.scientific_name;
      feat.properties.map_status      = 'confirmed';
      feat.properties.human_corrected = true;
      _enrichCache.delete(info.scientific_name);
    }
    renderMarkers();
    loadHeat();  // species changed via re-ID — refresh heat filter metadata
    const sciEl = scroll.querySelector('.det-sci-name');
    if (sciEl) sciEl.textContent = info.scientific_name;
    const badgeEl = scroll.querySelector('.badge');
    if (badgeEl) { badgeEl.className = 'badge badge-human'; badgeEl.textContent = '✏ Human verified'; }
  };
}

// ── Enrich this species ───────────────────────────────────────────────────

async function enrichSpeciesFromMap(speciesName, obsId) {
  // Dry run first, before any UI change (Melvin, 22 Oct 2026) — nothing runs until confirmed.
  if (!(await lmDryRunCheck(`/api/culinary/${encodeURIComponent(speciesName)}/enrich`, { method: 'POST' }, `Enrich ${speciesName}?`))) return;
  const btn = document.getElementById(`enrich-btn-${obsId}`);
  const resultSlot = document.getElementById(`enrich-result-${obsId}`);
  if (btn) { btn.disabled = true; btn.textContent = '⚡ Enriching…'; }

  try {
    const r = await fetch(`/api/culinary/${encodeURIComponent(speciesName)}/enrich`, {
      method: 'POST',
    });
    const d = await r.json().catch(() => ({}));

    if (!r.ok) {
      if (btn) { btn.disabled = false; btn.textContent = '⚡ Retry enrich'; }
      if (resultSlot) resultSlot.innerHTML =
        `<div class="enrich-result-err">Enrichment failed: ${_esc(d.detail || 'unknown error')}</div>`;
      return;
    }

    // Update local state
    const feat = allFeatures.find(f => f.properties.id === obsId);
    if (feat) feat.properties.has_enrichment = (d.enrichment_status === 'enriched' || d.enrichment_status === 'partial');

    // Show result
    const filled    = d.fields_filled || 0;
    const empty     = d.fields_empty || 0;
    const protected_ = d.fields_protected_human_edit || 0;
    const status    = d.enrichment_status || 'unknown';

    if (resultSlot) {
      resultSlot.innerHTML = `<div class="enrich-result-ok">
        ✓ ${status === 'enriched' ? 'Fully enriched' : status === 'partial' ? 'Partially enriched' : 'Enriched'}
        — ${filled} field${filled !== 1 ? 's' : ''} filled
        ${empty > 0 ? `· ${empty} empty` : ''}
        ${protected_ > 0 ? `· ${protected_} protected (human edits)` : ''}
        <br><a href="/species?s=${encodeURIComponent(speciesName)}" style="color:#166534">View full species profile →</a>
      </div>`;
    }

    if (btn) btn.style.display = 'none';

    // Invalidate enrichment cache so popup reloads fresh data
    _enrichCache.delete(speciesName);

    // Re-inject enrichment snippet with fresh data
    const enrichSlot = document.getElementById(`det-enrich-${obsId}`);
    if (enrichSlot) {
      enrichSlot.innerHTML = '<div class="map-enrich-loading">Reloading enrichment data…</div>';
      _injectEnrichment(obsId, speciesName);
    }

    renderMarkers();

  } catch (err) {
    if (btn) { btn.disabled = false; btn.textContent = '⚡ Retry enrich'; }
    if (resultSlot) resultSlot.innerHTML =
      `<div class="enrich-result-err">Network error — please try again.</div>`;
  }
}

// ── Send to review queue ──────────────────────────────────────────────────

async function sendToReview(obsId) {
  try {
    const r = await fetch(`/api/observations/${obsId}/review?status=needs_review`, { method: 'PATCH' });
    if (r.ok) {
      const feat = allFeatures.find(f => f.properties.id === obsId);
      if (feat) {
        feat.properties.review_status = 'needs_review';
        // Note: after Fix 13, this item will no longer appear on the map
        // since map only shows approved/manually_verified.
        // Remove it from allFeatures so it disappears.
        const idx = allFeatures.indexOf(feat);
        if (idx !== -1) allFeatures.splice(idx, 1);
      }
      renderMarkers();
      loadHeat();  // archive changed — refresh whole-archive heat + totals
      backToFilters();
      alert('Sent to review queue.');
    }
  } catch (_) {}
}

// ── Save species correction (unidentified edge case) ──────────────────────

async function saveSpeciesCorrection(obsId) {
  const input = document.getElementById(`species-edit-${obsId}`);
  const value = input ? input.value.trim() : '';
  if (!value) return;

  try {
    const r = await HazardAck.fetch(`/api/observations/${obsId}/review?status=approved`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ species_primary: value }),
    });
    if (r.ok) {
      const feat = allFeatures.find(f => f.properties.id === obsId);
      if (feat) {
        feat.properties.species_primary = value;
        feat.properties.review_status   = 'approved';
        feat.properties.human_corrected = true;
      }
      renderMarkers();
      loadHeat();  // species changed — refresh heat filter metadata
      showDetail(allFeatures.find(f => f.properties.id === obsId)?.properties || { id: obsId, species_primary: value });
    }
  } catch (_) {}
}

// ── Enrichment snippet (async inject) ─────────────────────────────────────

async function _injectEnrichment(obsId, speciesName) {
  const slot = document.getElementById(`det-enrich-${obsId}`);
  if (!slot) return;

  const result = await _fetchEnrichment(speciesName);

  if (!result || !result.ci) {
    // Safety gate still shows its label without culinary data (no decision → ⚠ toxicity unknown).
    slot.innerHTML = SafetyGate.badge(result ? result.safety : null) + `<div class="map-enrich-pending">
      No enrichment data yet —
      <a href="/species?s=${encodeURIComponent(speciesName)}" style="color:#2d5016">view species profile</a>
    </div>`;
    return;
  }

  const { ci, aiFields, safety } = result;
  let html = '';

  // Safety gate (batch 5, audit B2-01): the served decision — ☠ / ⚠ label
  // first; edible parts only when allowed.
  const _sgBadge = SafetyGate.badge(safety);
  if (_sgBadge) html += `<div class="map-safety-label" style="margin-bottom:4px">${_sgBadge}</div>`;

  // Safety warnings ALWAYS first (batch 6, B2-03): look-alike + preparation,
  // full text (never cut), from the served safety.warnings; text that is not
  // curator-authored is labelled "Source text — not yet reviewed".
  html += SafetyGate.warnings(safety);

  // Culinary summary — only when the safety gate allows culinary content
  if (!SafetyGate.allowed(safety)) {
    html += `<div class="map-culinary-row">
      <a href="/species?s=${encodeURIComponent(speciesName)}">View full species profile →</a>
    </div>`;
  } else if (ci.edible_parts) {
    const aiMark = aiFields.has('edible_parts')
      ? ' <span style="font-size:0.65rem;background:#f3e8ff;color:#7c3aed;border-radius:3px;padding:1px 4px">✦ AI</span>' : '';
    html += `<div class="map-culinary-row">
      <strong>🍴 Edible Parts${aiMark}</strong>${_esc(_trunc(ci.edible_parts, 140))}
      <br><a href="/species?s=${encodeURIComponent(speciesName)}">View full profile →</a>
    </div>`;
  } else {
    html += `<div class="map-culinary-row">
      <strong>🍴 Culinary data available</strong>
      <a href="/species?s=${encodeURIComponent(speciesName)}">View full species profile →</a>
    </div>`;
  }

  slot.innerHTML = html || `<div class="map-enrich-pending">
    <a href="/species?s=${encodeURIComponent(speciesName)}" style="color:#2d5016">View species profile →</a>
  </div>`;
}

function _trunc(str, maxLen) {
  if (!str) return '';
  const s = String(str).trim();
  return s.length > maxLen ? s.slice(0, maxLen).trimEnd() + '…' : s;
}

// ── Filter wire-up ────────────────────────────────────────────────────────
// Species / month / season toggles are wired via inline onchange/onclick.
// Workshop and human-only checkboxes (now in filter panel) update filterState inline.

window.addEventListener('resize', () => {
  map.invalidateSize();
  clusterGroup.refreshClusters();
});

// ── Lightbox — shared component (static/js/lightbox.js) ──────────────────

function openPhotoLightbox(obsId) {
  openLightbox([{ src: `/api/observations/${obsId}/photo`, caption: '' }], 0);
}

// ── Remove photo (reject — keeps record, removes from map) ────────────────

let _removeObsId = null;
let _undoTimer   = null;
let _cdTimer     = null;

function showRemoveConfirm(obsId) {
  _removeObsId = obsId;
  document.getElementById('confirm-dialog').classList.add('show');
}
function hideConfirmDialog() {
  document.getElementById('confirm-dialog').classList.remove('show');
}

async function confirmRemovePhoto() {
  if (!_removeObsId) return;
  const obsId = _removeObsId;
  hideConfirmDialog();

  try {
    const r = await fetch(`/api/observations/${obsId}/review?status=rejected`, { method: 'PATCH' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { alert(d.detail || 'Failed to remove from map.'); return; }

    const feat = allFeatures.find(f => f.properties.id === obsId);
    if (feat) feat.properties._prev_map_status = feat.properties.map_status;

    // Remove from the map (reject means it no longer qualifies as confirmed)
    const idx = allFeatures.findIndex(f => f.properties.id === obsId);
    if (idx !== -1) allFeatures.splice(idx, 1);

    renderMarkers();
    loadHeat();  // archive changed — refresh whole-archive heat + totals
    backToFilters();
    _showUndoToast(obsId, 30);

  } catch (err) {
    alert('Network error — please try again.');
  }
}

function _showUndoToast(obsId, totalSeconds) {
  clearTimeout(_undoTimer);
  clearInterval(_cdTimer);
  _removeObsId = obsId;
  const cd = document.getElementById('undo-countdown');
  let remaining = totalSeconds;
  cd.textContent = ` (${remaining}s)`;
  document.getElementById('undo-toast').classList.add('show');
  _cdTimer = setInterval(() => {
    remaining--;
    cd.textContent = remaining > 0 ? ` (${remaining}s)` : '';
    if (remaining <= 0) clearInterval(_cdTimer);
  }, 1000);
  _undoTimer = setTimeout(() => {
    document.getElementById('undo-toast').classList.remove('show');
    _removeObsId = null;
  }, totalSeconds * 1000);
}

async function undoRemovePhoto() {
  if (!_removeObsId) return;
  const obsId = _removeObsId;
  clearTimeout(_undoTimer);
  clearInterval(_cdTimer);
  document.getElementById('undo-toast').classList.remove('show');
  _removeObsId = null;

  try {
    const r = await fetch(`/api/observations/${obsId}/reject-undo`, { method: 'POST' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { alert(d.detail || 'Undo failed — the 30-second window may have expired.'); return; }

    // Reload the feature list to get the restored observation
    await loadFeatures();
    loadHeat();  // archive changed — refresh whole-archive heat + totals

  } catch (err) {
    alert('Network error during undo.');
  }
}

// ── Delete observation (permanent) ───────────────────────────────────────

let _deleteObsId = null;

function showDeleteDialog(obsId) {
  _deleteObsId = obsId;
  document.getElementById('delete-reason').value = '';
  document.getElementById('delete-dialog').classList.add('show');
}
function hideDeleteDialog() {
  _deleteObsId = null;
  document.getElementById('delete-dialog').classList.remove('show');
}

async function confirmDeleteObs() {
  if (!_deleteObsId) return;
  const obsId = _deleteObsId;
  const reason = document.getElementById('delete-reason').value.trim();
  hideDeleteDialog();

  try {
    const r = await fetch(`/api/observations/${obsId}`, {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: reason || null }),
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) { alert(d.detail || 'Delete failed.'); return; }

    const idx = allFeatures.findIndex(f => f.properties.id === obsId);
    if (idx !== -1) allFeatures.splice(idx, 1);

    renderMarkers();
    loadHeat();  // archive changed — refresh whole-archive heat + totals
    backToFilters();

  } catch (err) {
    alert('Network error — please try again.');
  }
}

// ── Utilities ─────────────────────────────────────────────────────────────

// The page's escaper → static/js/esc.js (batch 15). Inline-handler string
// arguments use lmJsArg(), never the old escape-then-backslash-the-apostrophe pattern.
function _esc(s) { return window.lmEsc(s); }

// ── Fix 17: Species rename (detail panel) ────────────────────────────────

function openRenameForm(obsId, currentName) {
  const form = document.getElementById(`rename-form-${obsId}`);
  const sciEl = document.getElementById(`rename-sci-${obsId}`);
  if (!form) return;
  form.style.display = '';
  if (sciEl) { sciEl.value = currentName; sciEl.focus(); sciEl.select(); }
  document.getElementById(`rename-result-${obsId}`)?.replaceChildren();
}

async function saveSpeciesRename(obsId, oldName) {
  const sciEl    = document.getElementById(`rename-sci-${obsId}`);
  const commonEl = document.getElementById(`rename-common-${obsId}`);
  const saveBtn  = document.getElementById(`rename-save-${obsId}`);
  const resultEl = document.getElementById(`rename-result-${obsId}`);

  const newName   = sciEl?.value.trim();
  const newCommon = commonEl?.value.trim() || undefined;

  if (!newName) {
    if (resultEl) resultEl.innerHTML = `<div class="rename-result-err">Species name cannot be empty.</div>`;
    return;
  }

  if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = '⟳ Re-enriching…'; }
  if (resultEl) resultEl.innerHTML = `<div style="font-size:0.76rem;color:#888">Querying PFAF and Wikidata…</div>`;

  try {
    const r = await fetch(`/api/species/${encodeURIComponent(oldName)}/rename`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ new_name: newName, new_common_name: newCommon || null }),
    });
    const d = await r.json().catch(() => ({}));

    if (!r.ok) {
      if (resultEl) resultEl.innerHTML = `<div class="rename-result-err">✗ ${_esc(d.detail || 'Error')}</div>`;
      if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save & re-enrich'; }
      return;
    }

    // Update local features
    allFeatures.forEach(f => {
      if (f.properties.species_primary === oldName) {
        f.properties.species_primary = newName;
        f.properties.human_corrected = true;
      }
    });
    _enrichCache.delete(oldName);
    _enrichCache.delete(newName);

    // Update the visible name in the detail panel
    const sciDisplay = document.querySelector('.det-sci-name');
    if (sciDisplay) sciDisplay.childNodes[0].textContent = newName + ' ';

    const form = document.getElementById(`rename-form-${obsId}`);
    if (form) form.style.display = 'none';

    if (resultEl) {
      if (d.not_found) {
        resultEl.innerHTML = `<div class="rename-result-warn">⚠ ${_esc(d.not_found_message)}<br>
          Name updated, but no enrichment data found. Check spelling or use the full Latin binomial.</div>`;
      } else {
        const status = d.enrichment_status;
        resultEl.innerHTML = `<div class="rename-result-ok">
          ✓ Renamed to <em>${_esc(newName)}</em>
          — re-enrichment: ${status === 'enriched' ? '✓ both sources' : status === 'partial' ? '~ one source' : status}
          ${d.protected_fields?.length ? `<br><small>${d.protected_fields.length} field(s) protected from human edits</small>` : ''}
        </div>`;
      }
    }

    renderMarkers();
    loadHeat();  // species renamed — refresh heat filter metadata
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save & re-enrich'; }

  } catch (e) {
    if (resultEl) resultEl.innerHTML = `<div class="rename-result-err">Network error: ${_esc(e.message)}</div>`;
    if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save & re-enrich'; }
  }
}

