// hazard-ack.js — hazard candidates on approve (Melvin, 22 Oct 2026, foxglove #24507).
//
// The rule lives server-side (app/services/hazard_candidates.py): any candidate
// from any source naming a toxic/deadly species makes the photo a hazard case.
// This file only SHOWS it and carries the second tap:
//   HazardAck.lineHtml(hazards)        red ☠ line per hazard species, by name
//   HazardAck.others(hazards, name)    the hazards that are not the approving species
//   HazardAck.ackParam(hazards)        query-string value naming them
//   HazardAck.fetch(url, opts)         fetch; on 409 hazard_ack_required asks a
//                                      second explicit OK naming the hazard and
//                                      retries with hazard_ack — every approve
//                                      caller goes through it.
(function () {
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c =>
      ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function key(s) { return String(s || '').trim().toLowerCase().replace(/\s+/g, ' '); }

  function lineHtml(hazards) {
    if (!hazards || !hazards.length) return '';
    return hazards.map(h =>
      `<div class="hazard-line hazard-${h.level === 'deadly' ? 'deadly' : 'toxic'}"` +
      ` title="${esc(h.level)} — named by ${esc((h.sources || []).map(s => s.source).join(' + '))}">` +
      `☠ ${esc(h.label || h.scientific_name)} — candidate</div>`).join('');
  }

  function others(hazards, approvingName) {
    const k = key(approvingName);
    return (hazards || []).filter(h => key(h.scientific_name) !== k);
  }

  function ackParam(hazards) {
    return encodeURIComponent((hazards || []).map(h => h.scientific_name).join(','));
  }

  function withAck(url, hazards) {
    return url + (url.includes('?') ? '&' : '?') + 'hazard_ack=' + ackParam(hazards);
  }

  function promptText(detail) {
    const names = (detail.hazards || []).map(h => '☠ ' + (h.label || h.scientific_name)).join('\n');
    return `${names}\n\nwas a candidate for this photo.\n\n` +
      `Tap OK only if you are sure it is NOT that — approve as ${detail.approving || 'this species'}.`;
  }

  async function hazardFetch(url, opts) {
    const r = await fetch(url, opts);
    if (r.status !== 409) return r;
    const body = await r.clone().json().catch(() => null);
    const d = body && body.detail;
    if (!d || d.code !== 'hazard_ack_required') return r;
    if (!window.confirm(promptText(d))) {
      return new Response(JSON.stringify({ detail: 'Not approved — ☠ hazard candidate not acknowledged' }),
        { status: 409, headers: { 'Content-Type': 'application/json' } });
    }
    return fetch(withAck(url, d.hazards), opts);
  }

  window.HazardAck = { lineHtml, others, ackParam, withAck, fetch: hazardFetch };
})();
