// Dry run before every enrichment / backfill / draft button (Melvin, 22 Oct 2026).
// lmDryRunConfirm(url, init, title): POSTs the same request with ?dry_run=true,
// shows the server's summary (species, fields it may fill, drafts it may create)
// and runs the real request only when confirmed. Resolves to the real Response,
// or null when the curator cancels (or the dry run fails) — nothing is written.
// The summary comes from app/services/enrichment_plan.py (one shape for all).
//
// Scope (Melvin, 22 Oct 2026): every BULK enrichment / backfill button goes
// through lmScopedDryRunCheck / lmScopedDryRunConfirm, which first ask which
// species — a saved walk (its species, as on the map), Current list (the
// Foraging List, lists.js) or All eligible (never preselected) — and a per-run
// cap (default 25, walk species first). No scope chosen = nothing runs. The
// scope travels as query params (scope, walk_id, species, cap) to the dry run
// AND the real run, so both count the same species (app/services/enrichment_scope.py).
(function () {
  function _line(label, obj) {
    const entries = Object.entries(obj || {}).filter(([, n]) => n);
    if (!entries.length) return null;
    return label + '\n' + entries.map(([f, n]) => '   • ' + f.replace(/_/g, ' ') + ': ' + n).join('\n');
  }

  function summaryText(d, title) {
    const lines = [title || 'Run this?', ''];
    if (d.species_count != null) lines.push('Species: ' + d.species_count + (d.new_species ? ' (' + d.new_species + ' new)' : ''));
    const parts = [
      _line('May fill (empty now):', d.fields_may_fill),
      _line('Filled already — changed source text becomes a Review card:', d.fields_may_get_review_draft),
      _line('May update:', d.fields_may_update),
      _line('Drafts it may create:', d.drafts_may_create || d.fields),
    ].filter(Boolean);
    if (parts.length) lines.push('', parts.join('\n\n'));
    if (d.scope_label) {
      lines.push('', 'Scope: ' + d.scope_label + ' — ' + d.eligible_in_scope + ' eligible, ' + d.queued +
                 ' queued (cap ' + d.cap + ')' +
                 (d.remaining ? '; ' + d.remaining + ' not queued — run again for the rest' : ''));
    }
    if (d.drafts_note) lines.push('', d.drafts_note);
    if (d.note) lines.push('', d.note);
    if (d.species_sample && d.species_sample.length) {
      lines.push('', 'e.g. ' + d.species_sample.slice(0, 6).join(', ') + (d.species_count > 6 ? ', …' : ''));
    }
    lines.push('', 'Nothing has been written yet. OK to run?');
    return lines.join('\n');
  }

  window.lmDryRunConfirm = async function (url, init, title) {
    init = Object.assign({ method: 'POST' }, init || {});
    const sep = url.indexOf('?') === -1 ? '?' : '&';
    let d;
    try {
      const r = await fetch(url + sep + 'dry_run=true', init);
      d = await r.json().catch(() => ({}));
      if (!r.ok) {
        alert((title || 'Dry run') + ' failed: ' + (typeof d.detail === 'string' ? d.detail : ('HTTP ' + r.status)));
        return null;
      }
    } catch (e) {
      alert((title || 'Dry run') + ' failed: ' + e.message);
      return null;
    }
    if (!confirm(summaryText(d, title))) return null;
    return fetch(url, init);
  };
  // Confirm-only variant for handlers that must do something between the
  // dry run and the real request (e.g. cancel a stuck queue job first).
  window.lmDryRunCheck = async function (url, init, title) {
    init = Object.assign({ method: 'POST' }, init || {});
    const sep = url.indexOf('?') === -1 ? '?' : '&';
    try {
      const r = await fetch(url + sep + 'dry_run=true', init);
      const d = await r.json().catch(() => ({}));
      if (!r.ok) { alert((title || 'Dry run') + ' failed: ' + (typeof d.detail === 'string' ? d.detail : ('HTTP ' + r.status))); return false; }
      return confirm(summaryText(d, title));
    } catch (e) {
      alert((title || 'Dry run') + ' failed: ' + e.message);
      return false;
    }
  };
  window.lmDryRunSummaryText = summaryText;   // tests

  // ── Scope picker ───────────────────────────────────────────────────────────
  const DEFAULT_CAP = 25;   // = enrichment_scope.DEFAULT_CAP

  // Query string for a chosen scope (tests use it too).
  function scopeQuery(sc) {
    const q = ['scope=' + encodeURIComponent(sc.scope), 'cap=' + encodeURIComponent(sc.cap || DEFAULT_CAP)];
    if (sc.scope === 'walk') q.push('walk_id=' + encodeURIComponent(sc.walk_id));
    if (sc.scope === 'list') (sc.species || []).forEach(n => q.push('species=' + encodeURIComponent(n)));
    return q.join('&');
  }

  function withScope(url, sc) {
    return url + (url.indexOf('?') === -1 ? '?' : '&') + scopeQuery(sc);
  }

  function _el(tag, attrs, html) {
    const e = document.createElement(tag);
    Object.assign(e, attrs || {});
    if (html != null) e.innerHTML = html;
    return e;
  }

  // Resolves to {scope, walk_id, species, cap} or null (cancelled / nothing chosen).
  async function pickScope(title) {
    if (!window.ForagingList) throw new Error('dry-run.js: lists.js (ForagingList) is not loaded on this page');
    const listNames = ForagingList.species();
    let walks = [];
    try {
      const r = await fetch('/api/walk/saves');
      if (r.ok) walks = ((await r.json()).walks || []);
    } catch (_) { /* no walks offered */ }
    const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    return new Promise(resolve => {
      const ov = _el('div', { className: 'lm-scope-overlay' });
      ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:100000;display:flex;align-items:center;justify-content:center;padding:16px';
      const box = _el('div', { className: 'lm-scope-box' }, `
        <div style="font-weight:700;margin-bottom:8px">${esc(title || 'Run this?')}</div>
        <div style="font-size:0.85rem;color:#555;margin-bottom:10px">Which species? Nothing runs until you choose.</div>
        <label style="display:block;margin:6px 0"><input type="radio" name="lm-scope" value="walk"${walks.length ? '' : ' disabled'}>
          A saved walk <select class="lm-scope-walk" style="max-width:100%;margin-left:4px"${walks.length ? '' : ' disabled'}>
          ${walks.map(w => `<option value="${esc(w.id)}">${esc(w.name)}</option>`).join('')}</select></label>
        <label style="display:block;margin:6px 0"><input type="radio" name="lm-scope" value="list"${listNames.length ? '' : ' disabled'}>
          Current list (${listNames.length} species on the Foraging List)</label>
        <label style="display:block;margin:6px 0"><input type="radio" name="lm-scope" value="all"> All eligible species</label>
        <label style="display:block;margin:10px 0 4px;font-size:0.85rem">Species per run (walk species first):
          <input type="number" class="lm-scope-cap" min="1" max="1000" value="${DEFAULT_CAP}" style="width:5em"></label>
        <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:12px">
          <button type="button" class="lm-scope-cancel">Cancel</button>
          <button type="button" class="lm-scope-ok" disabled>Continue to dry run</button>
        </div>`);
      box.style.cssText = 'background:#fff;color:#222;border-radius:8px;padding:16px;max-width:420px;width:100%;box-shadow:0 8px 30px rgba(0,0,0,0.3)';
      ov.appendChild(box);
      document.body.appendChild(ov);
      const ok = box.querySelector('.lm-scope-ok');
      const chosen = () => (box.querySelector('input[name="lm-scope"]:checked') || {}).value || null;
      box.addEventListener('change', () => { ok.disabled = !chosen(); });
      const done = v => { ov.remove(); resolve(v); };
      box.querySelector('.lm-scope-cancel').onclick = () => done(null);
      ok.onclick = () => {
        const scope = chosen();
        if (!scope) return;
        const cap = Math.max(1, Math.min(1000, parseInt(box.querySelector('.lm-scope-cap').value, 10) || DEFAULT_CAP));
        done({ scope: scope, cap: cap,
               walk_id: scope === 'walk' ? box.querySelector('.lm-scope-walk').value : null,
               species: scope === 'list' ? listNames : [] });
      };
    });
  }

  // Scope → dry run → confirm. Resolves to the scoped URL to POST (same scope
  // as the dry run), or null when cancelled — nothing has been written.
  window.lmScopedDryRunCheck = async function (url, init, title) {
    const sc = await pickScope(title);
    if (!sc) return null;
    const scoped = withScope(url, sc);
    return (await window.lmDryRunCheck(scoped, init, title)) ? scoped : null;
  };
  // Scope → dry run → confirm → the real request (Response), or null.
  window.lmScopedDryRunConfirm = async function (url, init, title) {
    const sc = await pickScope(title);
    if (!sc) return null;
    return window.lmDryRunConfirm(withScope(url, sc), init, title);
  };
  window.lmScopeQuery = scopeQuery;   // tests
})();
