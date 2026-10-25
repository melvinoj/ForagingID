// hazard-ack.js — hazard candidates on approve (Melvin, 22 Oct 2026, foxglove #24507).
//
// The rule lives server-side (app/services/hazard_candidates.py): a toxic/deadly
// candidate in the top 3 or at >= 5% of any source gates an undecided card
// (hazard_candidates); one named lower is DEEP (hazard_deep). This file only
// SHOWS them and carries the second tap:
//   HazardAck.lineHtml(hazards)        red ☠ line per GATE-tier hazard, by name
//   HazardAck.deepLineHtml(hazards)    one grey "Also listed deep in …" line
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

  const SOURCE_LABEL = { plantnet: 'PlantNet', inaturalist: 'iNaturalist' };

  function pct(score) {
    if (score == null || isNaN(score)) return '';
    const p = Number(score) * 100;
    return ' ' + (p < 1 ? p.toFixed(1) : Math.round(p)) + '%';
  }

  // DEEP tier: one grey line, each species with the source that ranked it
  // highest (best score), e.g. "Also listed deep in PlantNet: Conium maculatum 0.1%".
  function deepLineHtml(hazards) {
    if (!hazards || !hazards.length) return '';
    const parts = hazards.map(h => {
      const best = (h.sources || []).slice().sort((a, b) => (b.score || 0) - (a.score || 0))[0] || {};
      const src = SOURCE_LABEL[best.source] || best.source || 'a source';
      return `${esc(src)}: ${esc(h.scientific_name)}${esc(pct(best.score))}`;
    });
    return `<div class="hazard-deep-line">Also listed deep in ${parts.join('; ')}</div>`;
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

  window.HazardAck = { lineHtml, deepLineHtml, others, ackParam, withAck, fetch: hazardFetch };
})();
