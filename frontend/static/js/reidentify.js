/**
 * Re-identification power panel — shared between map and review pages.
 *
 * Usage:
 *   ReID.render(obsId, currentSpecies)  → returns HTML string to inject
 *   ReID.wire(obsId, onConfirmed)       → attach event handlers after inject
 *     onConfirmed(obsId, speciesInfo)   → called when user confirms a species
 *
 * The panel supports:
 *   · Re-identify via PlantNet + iNaturalist in parallel
 *   · Google Lens fallback link
 *   · Mushroom Observer deep link (when species known)
 *   · GBIF UK occurrence check (auto-runs after confirmation)
 *   · Manual entry with GBIF + iNaturalist name lookup
 */

window.ReID = (() => {

  // ── CSS (injected once) ────────────────────────────────────────────────

  const CSS = `
  .reid-panel {
    margin-top: 14px;
    border-top: 1px solid #e8f0dc;
    padding-top: 12px;
  }
  .reid-section-title {
    font-size: 0.78rem; font-weight: 700; color: #2d5016;
    text-transform: uppercase; letter-spacing: 0.04em;
    margin-bottom: 10px;
  }
  /* action links row */
  .reid-action-row {
    display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px;
  }
  .reid-btn {
    padding: 7px 13px; border-radius: 6px; font-size: 0.8rem;
    border: 1px solid #a8c678; background: #f0f9e8; color: #2d5016;
    cursor: pointer; white-space: nowrap;
    touch-action: manipulation; -webkit-tap-highlight-color: transparent;
    min-height: 36px; display: inline-flex; align-items: center; gap: 4px;
  }
  .reid-btn:hover, .reid-btn:active { background: #e2f0d0; border-color: #2d5016; }
  .reid-btn:disabled { opacity: 0.55; cursor: default; }
  .reid-link {
    padding: 7px 10px; font-size: 0.78rem; color: #555;
    text-decoration: none; border-radius: 6px;
    border: 1px solid #ddd; background: white;
    touch-action: manipulation; -webkit-tap-highlight-color: transparent;
    min-height: 36px; display: inline-flex; align-items: center;
    white-space: nowrap;
  }
  .reid-link:hover { background: #f5f5f5; border-color: #aaa; color: #222; }
  /* candidate cards */
  .reid-results { margin: 8px 0 10px; }
  .reid-loading  { font-size: 0.82rem; color: #888; padding: 8px 0; }
  .reid-error    { font-size: 0.82rem; color: #856404; background: #fff3cd; padding: 8px 10px; border-radius: 6px; }
  .reid-no-results { font-size: 0.82rem; color: #888; padding: 6px 0; }
  .reid-candidate {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 10px; border: 1px solid #e0e8d0; border-radius: 7px;
    margin-bottom: 5px; background: white; cursor: pointer;
    transition: background 0.12s, border-color 0.12s;
    touch-action: manipulation; -webkit-tap-highlight-color: transparent;
  }
  .reid-candidate:hover, .reid-candidate:active { background: #f0f9e8; border-color: #7a9e50; }
  .reid-candidate.selected { background: #d1e7dd; border-color: #0f5132; }
  .reid-conf-bar {
    width: 42px; flex-shrink: 0;
    background: #e8f0dc; border-radius: 4px; overflow: hidden;
    height: 6px; margin-top: 4px;
  }
  .reid-conf-fill { height: 100%; background: #2d5016; }
  .reid-cand-sci  { font-style: italic; font-size: 0.82rem; color: #333; font-weight: 600; }
  .reid-cand-common { font-size: 0.76rem; color: #666; margin-top: 1px; }
  .reid-cand-meta   { font-size: 0.72rem; color: #999; margin-top: 2px; display: flex; gap: 6px; }
  .reid-cand-score  { font-weight: 700; }
  .reid-source-badge {
    font-size: 0.65rem; padding: 1px 5px; border-radius: 3px;
    background: #e8f0dc; color: #4a7a25; font-weight: 600;
  }
  .reid-source-badge.both { background: #cce5ff; color: #004085; }
  .reid-source-badge.inaturalist { background: #fff3cd; color: #856404; }
  /* GBIF result chip */
  .reid-gbif {
    margin: 6px 0 10px;
    font-size: 0.78rem; color: #555;
    display: flex; align-items: center; gap: 6px;
    background: #f8f9fa; border: 1px solid #e0e0e0;
    border-radius: 6px; padding: 6px 10px;
  }
  .reid-gbif.found  { background: #f0fbf4; border-color: #b2dfdb; color: #0f5132; }
  .reid-gbif.absent { background: #fff8f0; border-color: #f0d090; color: #856404; }
  /* manual entry */
  .reid-manual-header {
    font-size: 0.76rem; color: #777; margin: 10px 0 6px;
    display: flex; align-items: center; gap: 6px;
    cursor: pointer; user-select: none;
  }
  .reid-manual-header:hover { color: #4a7a25; }
  .reid-manual-header::before, .reid-manual-header::after {
    content: ''; flex: 1; height: 1px; background: #ddd;
  }
  .reid-manual-row {
    display: flex; gap: 6px; margin-bottom: 6px;
  }
  .reid-manual-input {
    flex: 1; padding: 7px 10px; font-size: 0.82rem;
    border: 1px solid #ccc; border-radius: 6px;
    min-height: 36px;
  }
  .reid-manual-input:focus { outline: none; border-color: #7a9e50; box-shadow: 0 0 0 2px #7a9e5030; }
  .reid-manual-btn {
    padding: 7px 12px; font-size: 0.8rem; border-radius: 6px;
    border: 1px solid #a8c678; background: #2d5016; color: white;
    cursor: pointer; white-space: nowrap; min-height: 36px;
    touch-action: manipulation; -webkit-tap-highlight-color: transparent;
  }
  .reid-manual-btn:hover, .reid-manual-btn:active { background: #3a6b1e; }
  .reid-manual-btn:disabled { opacity: 0.5; cursor: default; }
  `;

  let _cssInjected = false;
  function _injectCss() {
    if (_cssInjected) return;
    const el = document.createElement('style');
    el.textContent = CSS + `
  /* ── API selector ─────────────────────────────────────────────────── */
  .reid-api-selector {
    display: none; flex-wrap: wrap; gap: 6px; margin-bottom: 8px;
    padding: 7px 9px; background: #f8faf2;
    border: 1px solid #d0dbb8; border-radius: 6px;
  }
  .reid-api-selector.open { display: flex; }
  .reid-api-label {
    font-size: 0.72rem; font-weight: 700; color: #2d5016;
    width: 100%; margin-bottom: 2px; text-transform: uppercase;
    letter-spacing: 0.04em;
  }
  .reid-api-check {
    display: flex; align-items: center; gap: 5px;
    font-size: 0.77rem; color: #333; cursor: pointer; user-select: none;
    padding: 2px 7px; border: 1px solid #d0dbb8; border-radius: 4px;
    background: white;
  }
  .reid-api-check input { accent-color: #2d5016; cursor: pointer; }
  .reid-api-check.disabled { opacity: 0.45; pointer-events: none; }
  .reid-api-toggle {
    padding: 7px 10px; border-radius: 6px; font-size: 0.78rem;
    border: 1px dashed #a8c678; background: transparent; color: #4a7a25;
    cursor: pointer; white-space: nowrap; min-height: 36px;
    display: inline-flex; align-items: center; gap: 4px;
  }
  .reid-api-toggle:hover { background: #eaf2de; }
  `;
    document.head.appendChild(el);
    _cssInjected = true;
  }

  // ── Session-persisted API selection ────────────────────────────────────
  // Per-observation overrides stored in a plain object (lives for page lifetime).
  const _apiSel = {};          // obsId → Set of selected source strings
  const _SOURCES = ['plantnet', 'inaturalist'];
  const _SOURCE_LABELS = { plantnet: '🌿 PlantNet', inaturalist: '🦋 iNaturalist' };

  function _getApiSel(obsId, category) {
    if (_apiSel[obsId]) return _apiSel[obsId];
    // Category default: fungi skips PlantNet
    const isFungi = (category || '').toLowerCase() === 'fungi';
    return new Set(isFungi ? ['inaturalist'] : ['plantnet', 'inaturalist']);
  }

  function _saveApiSel(obsId, sel) { _apiSel[obsId] = sel; }

  function toggleApiSelector(obsId) {
    const box = document.getElementById(`reid-api-sel-${obsId}`);
    if (box) box.classList.toggle('open');
  }

  function onApiCheck(obsId, source, checked) {
    const category = document.getElementById(`reid-panel-${obsId}`)?.dataset.category || 'plant';
    const sel = new Set(_getApiSel(obsId, category));
    if (checked) sel.add(source);
    else         sel.delete(source);
    _saveApiSel(obsId, sel);
  }

  // ── Helpers ────────────────────────────────────────────────────────────

  function _esc(s) {
    if (!s) return '';
    return String(s)
      .replace(/&/g,'&amp;')
      .replace(/</g,'&lt;')
      .replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;');
  }

  function _sourceBadge(source) {
    const cls = source === 'both' ? 'both' : source === 'inaturalist' ? 'inaturalist' : '';
    const label = source === 'both' ? 'PlantNet + iNat' : source === 'inaturalist' ? 'iNaturalist' : 'PlantNet';
    return `<span class="reid-source-badge ${cls}">${label}</span>`;
  }

  function _candidateCard(c, obsId) {
    const pct = Math.round(c.confidence * 100);
    const fill = Math.round(c.confidence * 100);
    return `
    <div class="reid-candidate" data-obs="${obsId}" data-sci="${_esc(c.scientific_name)}"
         data-common="${_esc(c.common_name || '')}"
         data-conf="${c.confidence}" data-source="${_esc(c.source)}"
         onclick="ReID._selectCandidate(this)">
      <div style="flex:1;min-width:0">
        <div class="reid-cand-sci">${_esc(c.scientific_name)}</div>
        ${c.common_name ? `<div class="reid-cand-common">${_esc(c.common_name)}</div>` : ''}
        <div class="reid-cand-meta">
          <span class="reid-cand-score">${pct}%</span>
          ${_sourceBadge(c.source)}
        </div>
        <div class="reid-conf-bar"><div class="reid-conf-fill" style="width:${fill}%"></div></div>
      </div>
    </div>`;
  }

  // ── Public: render ─────────────────────────────────────────────────────

  function render(obsId, currentSpecies, obsCategory) {
    _injectCss();
    const category = (obsCategory || 'plant').toLowerCase();
    const lensUrl  = 'https://lens.google.com';
    const moUrl    = currentSpecies
      ? `https://mushroomobserver.org/name/search?q=${encodeURIComponent(currentSpecies)}`
      : null;

    // Build API selector checkboxes
    const isFungi    = category === 'fungi';
    const initSel    = _getApiSel(obsId, category);
    const apiChecks  = _SOURCES.map(src => {
      const disabledClass = (isFungi && src === 'plantnet') ? ' disabled' : '';
      const disabledAttr  = (isFungi && src === 'plantnet') ? ' disabled' : '';
      const checked       = initSel.has(src) ? ' checked' : '';
      return `<label class="reid-api-check${disabledClass}">
        <input type="checkbox" ${checked}${disabledAttr}
               onchange="ReID.onApiCheck(${obsId},'${src}',this.checked)">
        ${_SOURCE_LABELS[src]}
      </label>`;
    }).join('');

    return `
    <div class="reid-panel" id="reid-panel-${obsId}" data-category="${_esc(category)}">
      <div class="reid-section-title">🔬 Identification tools</div>

      <div class="reid-action-row">
        <button class="reid-btn" id="reid-btn-${obsId}"
                onclick="ReID.reidentify(${obsId})">
          🔬 Re-identify
        </button>
        <button class="reid-api-toggle" onclick="ReID.toggleApiSelector(${obsId})"
                title="Choose which APIs to query">⚙ APIs</button>
        <a class="reid-link" href="${lensUrl}" target="_blank" rel="noopener">
          🔍 Google Lens ↗
        </a>
        ${moUrl ? `<a class="reid-link" href="${_esc(moUrl)}" target="_blank" rel="noopener">🍄 Mushroom Observer ↗</a>` : ''}
      </div>

      <div class="reid-api-selector" id="reid-api-sel-${obsId}">
        <div class="reid-api-label">Query sources</div>
        ${apiChecks}
      </div>

      <div id="reid-results-${obsId}"></div>
      <div id="reid-gbif-${obsId}" style="display:none"></div>

      <div class="reid-manual-header" onclick="ReID.toggleManual(${obsId})"
           title="Enter a name manually">▸ or enter manually</div>
      <div id="reid-manual-body-${obsId}" style="display:none">
        <div class="reid-manual-row">
          <input class="reid-manual-input" id="reid-input-${obsId}"
                 type="text" placeholder="Common or Latin name…"
                 onkeydown="if(event.key==='Enter')ReID.lookup(${obsId})">
          <button class="reid-manual-btn" id="reid-lookup-btn-${obsId}"
                  onclick="ReID.lookup(${obsId})">Look up</button>
        </div>
        <div id="reid-lookup-results-${obsId}"></div>
      </div>
    </div>`;
  }

  // ── Public: reidentify ─────────────────────────────────────────────────

  async function reidentify(obsId) {
    const btn     = document.getElementById(`reid-btn-${obsId}`);
    const area    = document.getElementById(`reid-results-${obsId}`);
    const panel   = document.getElementById(`reid-panel-${obsId}`);
    if (!btn || !area) return;

    const category = panel?.dataset.category || 'plant';
    const sel      = _getApiSel(obsId, category);
    const sources  = [...sel];

    btn.disabled = true;
    btn.textContent = '⟳ Identifying…';
    const srcLabel = sources.map(s => _SOURCE_LABELS[s] || s).join(' + ');
    area.innerHTML = `<div class="reid-loading">Querying ${srcLabel || 'APIs'}…</div>`;

    try {
      const r   = await fetch(`/api/observations/${obsId}/reidentify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sources }),
      });
      const txt = await r.text();
      let d;
      try { d = JSON.parse(txt); } catch(_) { d = { results: [] }; }

      if (!r.ok) {
        area.innerHTML = `<div class="reid-error">Re-identify failed: ${_esc(d.detail || 'Unknown error')}</div>`;
        return;
      }

      const results  = d.results  || [];
      const warnings = d.warnings || [];

      if (!results.length) {
        let msg = 'No suggestions found from either source.';
        if (warnings.length) {
          msg += '<ul style="margin:6px 0 0;padding-left:18px;font-size:0.72rem;color:#856404">'
               + warnings.map(w => `<li>${_esc(w)}</li>`).join('')
               + '</ul>';
        }
        area.innerHTML = `<div class="reid-error">${msg}</div>`;
        return;
      }

      area.innerHTML = results.map(c => _candidateCard(c, obsId)).join('');

      // Note which sources responded
      const unavail = [];
      if (!d.plantnet_ok)    unavail.push('PlantNet unavailable');
      if (!d.inaturalist_ok) unavail.push('iNaturalist unavailable');
      if (unavail.length) {
        area.innerHTML += `<div style="font-size:0.72rem;color:#aaa;margin-top:4px">${unavail.join(' · ')}</div>`;
      }

    } catch (e) {
      area.innerHTML = `<div class="reid-error">Network error: ${_esc(e.message)}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = '🔬 Re-identify';
    }
  }

  // ── Public: lookup (manual entry) ─────────────────────────────────────

  async function lookup(obsId) {
    const input   = document.getElementById(`reid-input-${obsId}`);
    const btn     = document.getElementById(`reid-lookup-btn-${obsId}`);
    const area    = document.getElementById(`reid-lookup-results-${obsId}`);
    if (!input || !area) return;

    const q = (input.value || '').trim();
    if (!q) return;

    btn.disabled = true;
    btn.textContent = '⟳';
    area.innerHTML = '<div class="reid-loading">Looking up…</div>';

    try {
      const r   = await fetch(`/api/species/lookup?q=${encodeURIComponent(q)}`);
      const txt = await r.text();
      let d;
      try { d = JSON.parse(txt); } catch(_) { d = { results: [] }; }

      const results = d.results || [];
      if (!results.length) {
        area.innerHTML = '<div class="reid-no-results">No species found — check spelling or try the Latin name.</div>';
        return;
      }

      area.innerHTML = results.map(item => {
        const conf = 1.0; // manual lookup has no score
        return `
        <div class="reid-candidate" data-obs="${obsId}"
             data-sci="${_esc(item.scientific_name)}"
             data-common="${_esc(item.common_name || '')}"
             data-conf="" data-source="manual_entry"
             onclick="ReID._selectCandidate(this)">
          <div style="flex:1;min-width:0">
            <div class="reid-cand-sci">${_esc(item.scientific_name)}</div>
            ${item.common_name ? `<div class="reid-cand-common">${_esc(item.common_name)}</div>` : ''}
            <div class="reid-cand-meta">
              ${item.family ? `<span>${_esc(item.family)}</span>` : ''}
              <span class="reid-source-badge ${item.source === 'inaturalist' ? 'inaturalist' : ''}">${_esc(item.source || 'gbif')}</span>
            </div>
          </div>
        </div>`;
      }).join('');

    } catch (e) {
      area.innerHTML = `<div class="reid-error">Lookup failed: ${_esc(e.message)}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = 'Look up';
    }
  }

  // ── Internal: select a candidate card ─────────────────────────────────

  async function _selectCandidate(el) {
    const obsId    = parseInt(el.dataset.obs, 10);
    const sci      = el.dataset.sci;
    const common   = el.dataset.common || null;
    const conf     = el.dataset.conf ? parseFloat(el.dataset.conf) : null;
    const source   = el.dataset.source;

    // Determine action string for audit
    const action = source === 'manual_entry' ? 'manual_entry' : 'manual_reidentification';

    // Highlight selected card
    el.closest('[id^="reid-"]')?.querySelectorAll('.reid-candidate')
      .forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');

    try {
      const r = await fetch(`/api/observations/${obsId}/confirm-species`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scientific_name: sci,
          common_name: common || null,
          confidence: conf,
          source: action,
        }),
      });
      const txt = await r.text();
      let d;
      try { d = JSON.parse(txt); } catch(_) { d = {}; }

      if (!r.ok) {
        alert(d.detail || 'Failed to save identification.');
        el.classList.remove('selected');
        return;
      }

      // Trigger GBIF check inline
      _gbifCheck(obsId, sci);

      // Notify parent page via callback
      if (window._reidOnConfirmed) {
        window._reidOnConfirmed(obsId, { scientific_name: sci, common_name: common, confidence: conf, source: action });
      }

      // Collapse candidate lists — decision is made
      const panel = document.getElementById(`reid-panel-${obsId}`);
      if (panel) {
        const resultsEl = panel.querySelector('[id^="reid-results-"]');
        const lookupEl  = panel.querySelector('[id^="reid-lookup-results-"]');
        if (resultsEl) resultsEl.innerHTML = `<div style="font-size:0.78rem;color:#2d8016;padding:4px 0">✓ Saved: <em>${_esc(sci)}</em></div>`;
        if (lookupEl)  lookupEl.innerHTML  = '';
      }

    } catch (e) {
      alert(`Network error: ${e.message}`);
      el.classList.remove('selected');
    }
  }

  // ── Internal: GBIF UK check ────────────────────────────────────────────

  async function _gbifCheck(obsId, speciesName) {
    const el = document.getElementById(`reid-gbif-${obsId}`);
    if (!el) return;
    el.style.display = '';
    el.className = 'reid-gbif';
    el.textContent = '🌍 Checking UK records…';

    try {
      const r   = await fetch(`/api/observations/${obsId}/gbif-check?species=${encodeURIComponent(speciesName)}`, { method: 'POST' });
      const txt = await r.text();
      let d;
      try { d = JSON.parse(txt); } catch(_) { d = { summary: 'GBIF unavailable' }; }

      el.className = `reid-gbif ${d.found ? 'found' : 'absent'}`;
      el.innerHTML = `🌍 ${_esc(d.summary)}`;
    } catch (_) {
      el.style.display = 'none';
    }
  }

  // ── Public: toggleManual ──────────────────────────────────────────────

  function toggleManual(obsId) {
    const body   = document.getElementById(`reid-manual-body-${obsId}`);
    const header = body?.previousElementSibling;
    if (!body) return;
    const open = body.style.display === 'none';
    body.style.display = open ? 'block' : 'none';
    if (header) header.textContent = (open ? '▾' : '▸') + ' or enter manually';
    if (open) {
      const input = document.getElementById(`reid-input-${obsId}`);
      if (input) setTimeout(() => input.focus(), 60);
    }
  }

  // ── Public: updateCategory ────────────────────────────────────────────
  // Called when the user manually changes the category on a review card.
  // Syncs the reid panel's data-category and resets API source selection.

  function updateCategory(obsId, category) {
    const panel = document.getElementById(`reid-panel-${obsId}`);
    if (!panel) return;

    const norm = (category || 'plant').toLowerCase();
    panel.dataset.category = norm;

    // Clear any manual override so defaults re-apply for new category
    delete _apiSel[obsId];

    // Update checkbox states: fungi disables PlantNet
    const isFungi = norm === 'fungi';
    const sel = document.getElementById(`reid-api-sel-${obsId}`);
    if (!sel) return;

    sel.querySelectorAll('.reid-api-check').forEach(label => {
      const input = label.querySelector('input');
      if (!input) return;
      const src = input.getAttribute('onchange')?.match(/'(\w+)'/)?.[1];
      if (src === 'plantnet') {
        label.classList.toggle('disabled', isFungi);
        input.disabled = isFungi;
        input.checked  = !isFungi;
      } else if (src === 'inaturalist') {
        input.checked = true;
      }
    });
  }

  // ── Public API ─────────────────────────────────────────────────────────

  return { render, reidentify, lookup, _selectCandidate, _gbifCheck,
           toggleApiSelector, onApiCheck, updateCategory, toggleManual };

})();
