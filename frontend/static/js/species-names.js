// ── Species names rule (Melvin, 20 Oct 2026) ───────────────────────────────
// A short species reference is "Common name (Latin name)", Latin in italics.
// Latin alone only when there is no common name. The common name itself comes
// from the server's one rule (display_common_name in app/models/species.py:
// preferred_common_name, else the first English name). Full species cards that
// show Latin and common on separate lines keep their own layout.
// The ONLY frontend formatter for this — pages pass the common name they have.
(function () {
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  // Sentence case for ONE English common name (Melvin, 21 Oct 2026): the first
  // character upper-cased when it is a letter, the rest exactly as sourced —
  // "disc mayweed" → "Disc mayweed", never "Disc Mayweed". Display only; stored
  // names stay as sourced, and German names never go through it. Server twin:
  // sentence_case_name() in app/models/species.py.
  function sentence(name) {
    var n = (name == null ? '' : String(name)).trim();
    return n && /\p{L}/u.test(n.charAt(0)) ? n.charAt(0).toUpperCase() + n.slice(1) : n;
  }
  function clean(common, sci) {
    var c = (common == null ? '' : String(common)).trim();
    return c && c.charAt(0) !== '[' && c.toLowerCase() !== String(sci || '').trim().toLowerCase() ? sentence(c) : '';
  }
  // One English common name for display ('' when none).
  window.spCommon = sentence;
  // A list of English common names, each sentence-cased, joined
  // ("disc mayweed · pineapple weed" → "Disc mayweed · Pineapple weed").
  window.spCommonList = function (names, sep) {
    return (names || []).map(sentence).filter(Boolean).join(sep == null ? ' · ' : sep);
  };
  // HTML: "Common (<em>Latin</em>)" or "<em>Latin</em>"
  window.spNameHtml = function (sci, common) {
    var c = clean(common, sci);
    return c ? esc(c) + ' (<em>' + esc(sci) + '</em>)' : '<em>' + esc(sci) + '</em>';
  };
  // Plain text (alerts, confirms, toasts, <option>): "Common (Latin)" or "Latin"
  window.spNameText = function (sci, common) {
    var c = clean(common, sci);
    return c ? c + ' (' + sci + ')' : String(sci == null ? '' : sci);
  };
})();
