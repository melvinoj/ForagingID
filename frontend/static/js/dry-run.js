// Dry run before every enrichment / backfill / draft button (Melvin, 22 Oct 2026).
// lmDryRunConfirm(url, init, title): POSTs the same request with ?dry_run=true,
// shows the server's summary (species, fields it may fill, drafts it may create)
// and runs the real request only when confirmed. Resolves to the real Response,
// or null when the curator cancels (or the dry run fails) — nothing is written.
// The summary comes from app/services/enrichment_plan.py (one shape for all).
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
})();
