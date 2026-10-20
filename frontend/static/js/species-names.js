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
  function clean(common, sci) {
    var c = (common == null ? '' : String(common)).trim();
    return c && c.charAt(0) !== '[' && c.toLowerCase() !== String(sci || '').trim().toLowerCase() ? c : '';
  }
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
