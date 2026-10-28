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

  function _h(s) { return window.lmEsc(s); }

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

  // ── Batch 6 (B2-03): warnings and outgoing surfaces ───────────────────────
  // The server serves safety.warnings (in-app: {preparation, look_alike}, each
  // {text, reviewed} or null — app/models/species.py species_warnings) and
  // safety.handout_warnings (outgoing: curator-authored text only, toxic
  // fallback included — handout_warnings), plus handout_culinary_allowed /
  // handout_label. Text is never cut here; compact surfaces collapse it.
  const UNREVIEWED = 'Source text — not yet reviewed';
  const CAUTION_UNREVIEWED = '⚠ caution — warning not yet reviewed';
  const WARN_TITLES = { look_alike: 'Look-alike warning', preparation: 'Preparation warning' };

  // Outgoing surfaces (print, PDF, Export summary): culinary content also needs
  // a curator-authored caution warning. Missing field (old payload) fails closed.
  function handoutAllowed(safety) {
    const d = decision(safety);
    return allowed(d) && d.handout_culinary_allowed === true;
  }

  function handoutCulinary(cul, safety) {
    const out = Object.assign({}, cul || {});
    if (!handoutAllowed(safety)) CULINARY_FIELDS.forEach(function (f) { delete out[f]; });
    return out;
  }

  function handoutRecipes(list, safety) {
    return handoutAllowed(safety) ? (list || []) : [];
  }

  // Badge for outgoing surfaces: "⚠ caution — warning not yet reviewed" for a
  // caution species without a curator-authored warning.
  function handoutBadge(safety, extraStyle) {
    const d = decision(safety);
    let label = typeof d.handout_label === 'string' ? d.handout_label : d.label;
    if (d.level === 'caution' && d.handout_culinary_allowed !== true) label = CAUTION_UNREVIEWED;
    return badge(Object.assign({}, d, { label: label }), extraStyle);
  }

  function _warnBox(title, text, note, collapsed) {
    const head = '⚠ ' + _h(title) + (note ? ' <span class="sw-unreviewed" style="font-weight:400;font-style:italic;' +
      'font-size:0.92em;color:#78716c">(' + _h(note) + ')</span>' : '');
    const box = 'font-size:0.78rem;color:#7a2000;background:#fff7ed;border-left:3px solid #ea580c;' +
      'padding:4px 8px;margin:4px 0;line-height:1.4;white-space:pre-wrap';
    if (collapsed) {
      return '<details class="safety-warn-text" style="' + box + '"><summary style="cursor:pointer;' +
        'font-weight:700;white-space:normal">' + head + '</summary>' + _h(text) + '</details>';
    }
    return '<div class="safety-warn-text" style="' + box + '"><strong>' + head + '</strong><br>' + _h(text) + '</div>';
  }

  // In-app warnings (map pop-up, walk stop card, proximity alert, species
  // page): every warning, full text; text that is not curator-authored is
  // labelled, never dropped. opts.collapse: 'all' collapses every warning,
  // 'auto' collapses all but a caution species' preparation warning.
  function warnings(safety, opts) {
    const d = decision(safety);
    const w = (d && d.warnings) || {};
    const collapse = (opts && opts.collapse) || 'none';
    return ['look_alike', 'preparation'].map(function (k) {
      const x = w[k];
      if (!x || !x.text) return '';
      const folded = collapse === 'all' || (collapse === 'auto' && !(k === 'preparation' && d.level === 'caution'));
      return _warnBox(WARN_TITLES[k], x.text, x.reviewed ? '' : UNREVIEWED, folded);
    }).join('');
  }

  // Outgoing warnings: {preparation, look_alike} text (curator-authored, toxic
  // fallback included), for printers that lay the text out themselves.
  function handoutWarnings(safety) {
    const hw = (decision(safety) || {}).handout_warnings || {};
    return { preparation: (hw.preparation || '').trim(), look_alike: (hw.look_alike || '').trim() };
  }

  // Outgoing warnings as printed lines (Lists, browser print): look-alikes, then
  // the preparation warning — "Caution:" for a caution species, whose reason it
  // is. Always printed when present, whatever the content toggles say.
  function handoutWarningsHtml(safety, tag, cls) {
    const d = decision(safety);
    const hw = handoutWarnings(d);
    const t = tag || 'p';
    const open = '<' + t + (cls ? ' class="' + cls + '"' : '') + '>';
    const out = [];
    if (hw.look_alike) out.push(open + '⚠ Look-alikes: ' + _h(hw.look_alike) + '</' + t + '>');
    if (hw.preparation) out.push(open + '⚠ ' + (d.level === 'caution' ? 'Caution' : 'Preparation') + ': ' +
                                 _h(hw.preparation) + '</' + t + '>');
    return out.join('');
  }

  // Cautionary text that travels with culinary content (Melvin, 22 Oct 2026 —
  // Fix B): look-alike AND preparation warnings, wherever a recipe, edible
  // parts, taste notes or a culinary hint is shown or printed — unless the
  // species-level warning block already sits directly beside it on the same
  // card (then that block is the warning; never print it twice).
  // In-app: safety.warnings, full text; uncurated text labelled "Source text —
  // not yet reviewed" (batch 6). opts.handout: curator text only, uncut
  // (safety.handout_warnings); opts.tag / opts.cls let a printer lay the lines
  // out like its others. No warning text → ''.
  // Python twin: app/models/species.py culinary_warnings().
  function culinaryWarnings(safety, opts) {
    const d = decision(safety);
    const o = opts || {};
    if (o.handout) {
      const hw = handoutWarnings(d);
      const tag = o.tag || 'div';
      const st = o.cls ? '' : ' style="font-size:0.85em;color:#7a2000;border-left:3px solid #ea580c;padding:2px 6px;margin:4px 0;white-space:pre-wrap"';
      const line = (head, t) => '<' + tag + ' class="culinary-warning' + (o.cls ? ' ' + o.cls : '') + '"' + st + '>⚠ ' +
        head + ': ' + _h(t) + '</' + tag + '>';
      const out = [];
      if (hw.look_alike) out.push(line('Look-alikes', hw.look_alike));
      if (hw.preparation) out.push(line(d.level === 'caution' ? 'Caution' : 'Preparation', hw.preparation));
      return out.length ? '<div class="culinary-warnings">' + out.join('') + '</div>' : '';
    }
    const w = (d && d.warnings) || {};
    const boxes = ['look_alike', 'preparation'].map(function (k) {
      const x = w[k];
      return x && x.text ? _warnBox(WARN_TITLES[k], x.text, x.reviewed ? '' : UNREVIEWED, false) : '';
    }).join('');
    return boxes ? '<div class="culinary-warnings">' + boxes + '</div>' : '';
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

  // Seasonal Returns entry (Melvin, 28 Oct 2026): the same gate as a curator-
  // picked species — handout badge + handout warnings, uncut. A toxic / deadly
  // entry without a badge or without warning text returns null (drop it):
  // never "in season" without both. A missing decision fails closed (unknown).
  // Python twin: app/services/seasonal_returns.py seasonal_return_gate().
  // Returns null, or { badge, warnings } HTML strings.
  function seasonalReturn(safety) {
    const d = decision(safety);
    const hw = handoutWarnings(d);
    const label = typeof d.handout_label === 'string' ? d.handout_label : d.label;
    const red = d.level === 'deadly' || d.level === 'toxic';
    if (red && !(label && (hw.look_alike || hw.preparation))) return null;
    return { badge: handoutBadge(d), warnings: handoutWarningsHtml(d, 'div', 'sr-warn') };
  }

  window.SafetyGate = { decision: decision, seasonalReturn: seasonalReturn, allowed: allowed, badge: badge, warning: warning,
                        culinary: culinary, recipes: recipes, CULINARY_FIELDS: CULINARY_FIELDS, UNKNOWN: UNKNOWN,
                        warnings: warnings, handoutWarnings: handoutWarnings, handoutWarningsHtml: handoutWarningsHtml,
                        handoutAllowed: handoutAllowed,
                        handoutCulinary: handoutCulinary, handoutRecipes: handoutRecipes,
                        handoutBadge: handoutBadge, culinaryWarnings: culinaryWarnings, UNREVIEWED: UNREVIEWED };
})();
