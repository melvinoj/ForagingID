// The ONE HTML escaper for the app's pages (batch 15, P15, 28 Oct 2026).
// Replaces 27 page-local copies (4-char, 5-char and textContent variants).
// Python twin: app/services/markdown.esc. The exported experience page
// (scripts/experience_export/templates) keeps its own, on purpose.
//
//   lmEsc(s)   text / attribute value: & < > " ' escaped; null/undefined → '',
//              0 → '0'. Safe in element text and in single- or double-quoted
//              attributes.
//   lmJsArg(s) a JS string ARGUMENT for an inline handler, quotes included:
//              onclick="fn(${lmJsArg(name)})". Use it instead of the old
//              '${_esc(x).replace(/'/g, "\\'")}' pattern — that only worked
//              with a 4-char escaper; with lmEsc the apostrophe is already
//              &#39;, which the attribute decodes back to ' and breaks the
//              string (and opens an injection path).
//
// Load it before any page script or module that escapes (safety-gate.js,
// species-names.js, guest-notes.js, … call window.lmEsc at render time).
(function () {
  'use strict';
  var MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  function lmEsc(s) {
    return s === null || s === undefined ? '' : String(s).replace(/[&<>"']/g, function (c) { return MAP[c]; });
  }
  function lmJsArg(s) {
    // JSON.stringify gives a valid JS string literal; U+2028/U+2029 are line
    // terminators in older engines, so they are escaped too. Then HTML-escape
    // it for the attribute.
    var lit = JSON.stringify(s === null || s === undefined ? '' : String(s))
      .replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
    return lmEsc(lit);
  }
  window.lmEsc = lmEsc;
  window.lmJsArg = lmJsArg;
})();
