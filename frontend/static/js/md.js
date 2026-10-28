// One Markdown dialect for recipe text (batch 15, P4, 28 Oct 2026).
// JS twin of app/services/markdown.py — both must produce byte-identical HTML
// for the same input (tests/test_batch15_markdown.py runs both on one golden
// list). Replaces print.html / lists.html _mdLite and species.html _renderMd.
//
//   escape first; no raw HTML; [text](url) → text only, never <a>
//   blocks on blank lines; each line: # heading / - * + 1. 1) list item / paragraph
//   **bold** __bold__ *italic* _italic_ (not inside words) `code`; --- rules dropped
//
// Only recipe text goes through here. Curator warnings are escaped plain text
// on every surface and must never be rendered as Markdown.
// No regex lookbehind: older phone Safari cannot parse it.
(function () {
  'use strict';

  var ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  function esc(s) { return window.lmEsc(s); }

  var LINK = /\[([^\]\n]+)\]\(([^)\s]+)\)/g;
  var CODE = /`([^`\n]+)`/g;
  var BOLD_A = /\*\*(.+?)\*\*/g;
  var BOLD_U = /__(.+?)__/g;
  var EM_A = /(^|[^A-Za-z0-9_*])\*(?=\S)(.*?\S)\*(?![A-Za-z0-9_*])/g;
  var EM_U = /(^|[^A-Za-z0-9_])_(?=\S)(.*?\S)_(?![A-Za-z0-9_])/g;

  var BLOCK_SPLIT = /\n[ \t]*\n/;
  var HR = /^[-*_]{3,}$/;
  var HEAD = /^(#{1,6})[ \t]+(.*?)[ \t]*$/;
  var ITEM = /^[ \t]*([-*+]|[0-9]+[.)])[ \t]+(.*)$/;
  var CITATION = /\[[^\]]*\]\s*/g;

  function inline(text) {
    return esc(text)
      .replace(LINK, '$1')
      .replace(CODE, '<code>$1</code>')
      .replace(BOLD_A, '<strong>$1</strong>')
      .replace(BOLD_U, '<strong>$1</strong>')
      .replace(EM_A, '$1<em>$2</em>')
      .replace(EM_U, '$1<em>$2</em>');
  }

  function rawBlocks(text) {
    var out = [];
    String(text === null || text === undefined ? '' : text).replace(/\r/g, '').split(BLOCK_SPLIT)
      .forEach(function (b) {
        b = b.trim();
        if (b && !HR.test(b)) out.push(b);
      });
    return out;
  }

  function parseBlock(b) {
    var out = [], para = [], lst = null;
    b.split('\n').forEach(function (line) {
      var s = line.trim();
      if (!s) return;
      var h = s.match(HEAD);
      var it = h ? null : line.match(ITEM);
      if (h) {
        if (para.length) { out.push(['p', para]); para = []; }
        if (lst) { out.push(lst); lst = null; }
        out.push(['h', h[1].length, h[2]]);
      } else if (it) {
        if (para.length) { out.push(['p', para]); para = []; }
        var kind = /^[0-9]/.test(it[1]) ? 'ol' : 'ul';
        if (lst && lst[0] === kind) lst[1].push(it[2]);
        else { if (lst) out.push(lst); lst = [kind, [it[2]]]; }
      } else {
        if (lst) { out.push(lst); lst = null; }
        para.push(s);
      }
    });
    if (para.length) out.push(['p', para]);
    if (lst) out.push(lst);
    return out;
  }

  function defaultHeading() { return ['h3', null]; }

  // opts.heading(level) → [tag, class]; handouts: h3 for every level (default),
  // the species page: h4–h6 class recipe-h.
  function render(text, opts) {
    var heading = (opts && opts.heading) || defaultHeading;
    var out = [];
    rawBlocks(text).forEach(function (b) {
      parseBlock(b).forEach(function (blk) {
        if (blk[0] === 'h') {
          var hc = heading(blk[1]);
          out.push('<' + hc[0] + (hc[1] ? ' class="' + hc[1] + '"' : '') + '>' + inline(blk[2]) + '</' + hc[0] + '>');
        } else if (blk[0] === 'ul' || blk[0] === 'ol') {
          out.push('<' + blk[0] + '>' + blk[1].map(function (i) { return '<li>' + inline(i) + '</li>'; }).join('') +
                   '</' + blk[0] + '>');
        } else {
          out.push('<p>' + blk[1].map(inline).join('<br>') + '</p>');
        }
      });
    });
    return out.join('');
  }

  // Drop PFAF-style [n] / [source] citation brackets (the id_notes clean-up).
  // Placeholder guard (28 Oct 2026): text that is nothing but dots / ellipses once
  // the brackets go ("[iNaturalist] ...") is no content — return '' so it never prints.
  function stripCitations(text) {
    var out = String(text || '').replace(CITATION, '').trim();
    return /^[.…\s]*$/.test(out) ? '' : out;
  }

  window.LmMd = { render: render, stripCitations: stripCitations };
})();
