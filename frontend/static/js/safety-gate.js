// Safety gate — the ONLY frontend reader of the server's safety decision
// (audit P1 / batch 5, 21 Oct 2026). The rule itself lives in one place:
// app/models/species.py safety_decision(), served as `safety` by
// /api/culinary/{name} and /api/species/{name}/profile:
//   { culinary_allowed: bool, level: 'deadly'|'toxic'|'unknown'|'caution'|'none',
//     label: '☠ deadly'|'☠ toxic'|'⚠ toxicity unknown'|'⚠ caution'|'', warning: str|null }
// This file never re-derives it from toxicity_severity or edibility_status.
// A missing / malformed decision (old cached payload, failed fetch) fails
// closed: no culinary content, "⚠ toxicity unknown".
(function () {
  'use strict';

  const UNKNOWN = Object.freeze({ culinary_allowed: false, level: 'unknown', label: '⚠ toxicity unknown', warning: null });
  const LEVELS = ['deadly', 'toxic', 'unknown', 'caution', 'none'];

  function _h(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }

  // The served decision, or the fail-closed one.
  function decision(safety) {
    if (!safety || typeof safety !== 'object' || LEVELS.indexOf(safety.level) === -1) return UNKNOWN;
    return safety;
  }

  // May edible parts / taste notes / recipes be shown?
  function allowed(safety) {
    const d = decision(safety);
    return d.culinary_allowed === true && (d.level === 'none' || d.level === 'caution');
  }

  // ☠ / ⚠ badge HTML ('' when no label). Red for deadly/toxic, amber otherwise.
  function badge(safety, extraStyle) {
    const d = decision(safety);
    if (!d.label) return '';
    const red = d.level === 'deadly' || d.level === 'toxic';
    return '<span class="safety-badge safety-' + d.level + '" style="display:inline-block;font-size:0.68rem;' +
      'padding:1px 6px;border-radius:4px;font-weight:700;background:' + (red ? '#dc2626' : '#fef3c7') +
      ';color:' + (red ? '#fff' : '#92400e') + ';' + (extraStyle || '') + '">' + _h(d.label) + '</span>';
  }

  // The approved caution warning as a block ('' when none).
  function warning(safety) {
    const d = decision(safety);
    if (d.level !== 'caution' || !d.warning) return '';
    return '<div class="safety-warning" style="font-size:0.78rem;color:#92400e;background:#fffbeb;' +
      'border-left:3px solid #f59e0b;padding:4px 8px;margin:4px 0">⚠ Caution: ' + _h(d.warning) + '</div>';
  }

  // Culinary content fields (species page "Culinary" section + taste notes).
  // Keep in step with CULINARY_FIELDS in app/api/lists_pdf.py's gate.
  const CULINARY_FIELDS = ['edible_parts', 'preparation_methods', 'cooking_techniques', 'preservation_methods',
    'harvest_stage', 'culinary_traditions', 'flavour_profile', 'pairing_ideas', 'recipe_ideas',
    'workshop_value_score', 'taste_notes'];

  // A copy of a culinary_info dict with the culinary fields removed when blocked.
  function culinary(cul, safety) {
    const out = Object.assign({}, cul || {});
    if (!allowed(safety)) CULINARY_FIELDS.forEach(function (f) { delete out[f]; });
    return out;
  }

  // Recipes when allowed, else [].
  function recipes(list, safety) {
    return allowed(safety) ? (list || []) : [];
  }

  window.SafetyGate = { decision: decision, allowed: allowed, badge: badge, warning: warning,
                        culinary: culinary, recipes: recipes, CULINARY_FIELDS: CULINARY_FIELDS, UNKNOWN: UNKNOWN };
})();
