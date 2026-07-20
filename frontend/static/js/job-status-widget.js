/**
 * job-status-widget.js — global floating widget for background jobs.
 *
 * Pinned top-right card listing every live background process / queue job,
 * minimizable to a pill, fully hidden when nothing is active. Rows are visually
 * identical to a row in the scan page's Job Queue panel — that row look is
 * ported here (see "Ported row styles" below); the floating shell, the
 * minimize/expand control and the show/hide behaviour are new to this file,
 * because the scan panel is a static inline block with none of those.
 *
 * Display-only: it renders what /api/processes/active and /api/queue/list
 * already return and sends nothing back. Per-process End is a later pass.
 *
 * Loaded once per page by site-header.js, owner-only (guests never see it —
 * process detail carries species names), into the #job-status-mount anchor.
 */
(function () {
  'use strict';

  // Idempotence: site-header.js injects this file on every page. Guard in case a
  // page also carries a legacy <script> tag, which would otherwise start a
  // second poller and a second widget.
  if (window.__jobStatusWidgetInit) return;
  window.__jobStatusWidgetInit = true;

  var POLL_MS   = 3000;
  var WIDGET_ID = 'job-status-widget';
  var STYLE_ID  = 'job-status-widget-css';

  // Rows shown while live (running/paused) plus terminal rows that are still
  // inside the server's recency window. ONE window governs this, and it lives
  // server-side: processes.py _RECENT_WINDOW_S = 90 s. /api/processes/active
  // returns terminal rows only while their heartbeat is inside that window, so
  // a failed/interrupted row surfaces briefly and then drops out on its own —
  // this file adds no second timer of its own. 'complete' stays excluded so the
  // widget auto-hides the moment work finishes rather than lingering for 90 s.

  var PROCESS_LABELS = {
    'enrichment_run':            'Enrichment',
    'itis_backfill':             'ITIS Backfill',
    'fungi_edibility_backfill':  'Fungi Edibility',
    'bulk_review':               'Bulk Review',
    'bulk_retry_identify':       'Bulk Retry ID',
    'bulk_unlock_prefilter':     'Bulk Unlock',
    'reprocess_pending':         'Re-processing',
    'p1_syncthing':              'Phone ingest',
    'ai_draft_backfill':         'AI Drafts',
    'ai_draft_backfill_id_notes':'AI ID Notes',
    // Pass C — the seven previously-invisible processes.
    'p2_delta':                  'Scan batch',
    'archive_scan':              'Archive scan',
    'auto_enrich':               'Auto-enrichment',
    'p1_reprocess':              'P1 reprocess',
    'folder_scan':               'Folder ingest',
    'rescan_unknown':            'Rescan unknown',
    'elevation_enrich':          'Elevation',
  };

  // Minimize state — transient, client-side only. Not persisted: a reload
  // brings the widget back expanded. It deliberately survives an auto-hide, so
  // minimizing during a long batch stays minimized when the next job starts.
  var collapsed = false;

  // ── Styles ───────────────────────────────────────────────────────────────
  // Every ported rule is scoped under #job-status-widget rather than declared
  // as a bare .jq-* / .status-badge rule. The declarations are verbatim from
  // scan.html, so rows render identically, but scoping means this file can
  // never restyle the scan page's own Job Queue panel (or any other page's
  // .status-badge) by loading on it. Same look, no shared-class blast radius.

  function _injectStyles() {
    if (document.getElementById(STYLE_ID)) return;
    var st = document.createElement('style');
    st.id = STYLE_ID;
    st.textContent = [
      '@keyframes jsw-pulse{0%,100%{opacity:1}50%{opacity:.4}}',
      '@keyframes jsw-spin{to{transform:rotate(360deg)}}',

      /* ── Floating shell (new) ── */
      /* Top-right, deliberately. Bottom-right is already occupied on four of
         the app pages — taxonomy's .controls (permanent zoom buttons, which a
         widget here would sit on top of and block), seasons' .pheno-legend and
         #my-season-bar, review's #toast, and the map's Leaflet attribution plus
         its 300px right pane. Top-right's only occupants are the .lb-close
         lightbox buttons, and those live inside full-screen overlays that cover
         this widget anyway. The nav chip is top-LEFT, so nav is never blocked. */
      '#job-status-widget{',
      '  position:fixed;right:16px;top:16px;z-index:1300;',
      '  width:300px;max-width:calc(100vw - 32px);',
      '  font-family:system-ui,-apple-system,sans-serif;',
      '  background:#2a3330;border:1px solid #4a5e5a;border-radius:10px;',
      '  box-shadow:0 4px 18px rgba(0,0,0,.35);overflow:hidden;',
      '}',
      /* Collapsed pill: shrink to content, drop the list entirely. */
      '#job-status-widget.jsw-collapsed{width:auto;}',
      '#job-status-widget.jsw-collapsed .jsw-body{display:none;}',

      '#job-status-widget .jsw-head{',
      '  display:flex;align-items:center;justify-content:space-between;gap:10px;',
      '  padding:8px 12px;background:#2f3d3a;border-bottom:1px solid #4a5e5a;',
      '}',
      '#job-status-widget.jsw-collapsed .jsw-head{border-bottom:none;}',
      '#job-status-widget .jsw-title{',
      '  display:flex;align-items:center;gap:7px;',
      '  font-size:0.78rem;font-weight:700;color:#9aaa88;',
      '  text-transform:uppercase;letter-spacing:0.06em;white-space:nowrap;',
      '}',
      '#job-status-widget .jsw-spinner{',
      '  width:11px;height:11px;flex:none;border-radius:50%;',
      '  border:2px solid #4a5e5a;border-top-color:#86efac;',
      '  animation:jsw-spin 0.9s linear infinite;',
      '}',
      '#job-status-widget .jsw-dot{color:#5a8a5a;font-size:0.7rem;',
      '  animation:jsw-pulse 1.6s ease-in-out infinite;}',
      '#job-status-widget .jsw-toggle{',
      '  flex:none;min-width:26px;min-height:26px;padding:0 6px;',
      '  background:#2a3c3a;color:#d8e4d8;border:1px solid #4a6060;border-radius:4px;',
      '  font-family:inherit;font-size:0.8rem;font-weight:700;line-height:1;',
      '  cursor:pointer;touch-action:manipulation;transition:background 0.12s;',
      '}',
      '#job-status-widget .jsw-toggle:hover{background:#3a4e4a;}',
      /* N-concurrent: rows stack; the list scrolls rather than growing off-screen. */
      '#job-status-widget .jsw-body{max-height:min(52vh,340px);overflow-y:auto;padding:4px 0;}',

      /* ── Ported row styles — verbatim declarations from scan.html ── */
      '#job-status-widget .jq-job{',
      '  padding:8px 16px;border-bottom:1px solid #3a4e4a;',
      '  display:flex;flex-direction:column;gap:4px;',
      '}',
      '#job-status-widget .jq-job:last-child{border-bottom:none;}',
      '#job-status-widget .jq-job-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}',
      '#job-status-widget .jq-label{font-size:0.82rem;font-weight:600;color:#d8e4d8;flex:1;}',
      '#job-status-widget .jq-progress-track{',
      '  height:5px;background:#3a4e4a;border-radius:3px;overflow:hidden;margin-top:2px;',
      '}',
      '#job-status-widget .jq-progress-fill{height:100%;background:#7aabce;border-radius:3px;transition:width 0.4s;}',
      '#job-status-widget .jq-progress-fill.ok{background:#86efac;}',
      '#job-status-widget .jq-progress-text{font-size:0.7rem;color:#7a9e88;font-variant-numeric:tabular-nums;}',
      '#job-status-widget .jq-error{font-size:0.72rem;color:#fca5a5;}',
      '#job-status-widget .status-badge{',
      '  display:inline-block;font-size:0.68rem;font-weight:700;',
      '  padding:2px 7px;border-radius:10px;vertical-align:middle;',
      '  text-transform:uppercase;letter-spacing:0.03em;',
      '}',
      '#job-status-widget .status-badge.running     {background:#166534;color:#fff;}',
      '#job-status-widget .status-badge.complete    {background:#1c1c1c;color:#fff;}',
      '#job-status-widget .status-badge.stalled     {background:#991b1b;color:#fff;}',
      '#job-status-widget .status-badge.failed      {background:#7f1d1d;color:#fff;}',
      '#job-status-widget .status-badge.queued      {background:#ede9fe;color:#6d28d9;}',
      '#job-status-widget .status-badge.paused      {background:#991b1b;color:#fff;}',
      '#job-status-widget .status-badge.interrupted {background:#92400e;color:#fff;}',

      /* Mobile: full-width under the top edge. Left inset clears the 44px nav
         chip at top:12px/left:12px so the drawer trigger stays tappable. */
      '@media (max-width:600px){',
      '  #job-status-widget{right:10px;top:10px;left:68px;width:auto;}',
      '  #job-status-widget.jsw-collapsed{left:auto;}',
      '}',
    ].join('\n');
    document.head.appendChild(st);
  }

  // ── Shell management ─────────────────────────────────────────────────────

  function _widget() {
    var w = document.getElementById(WIDGET_ID);
    if (w) return w;
    _injectStyles();
    w = document.createElement('div');
    w.id = WIDGET_ID;
    w.setAttribute('role', 'status');
    w.setAttribute('aria-live', 'polite');
    w.setAttribute('aria-label', 'Background jobs');
    // Mount into the anchor owned by site-header.js. (body.firstChild remains
    // only as a fallback for a page that somehow loads this without the header.
    // position:fixed means the widget pins to the viewport either way.)
    var mount = document.getElementById('job-status-mount');
    if (mount) mount.appendChild(w);
    else document.body.insertBefore(w, document.body.firstChild);
    return w;
  }

  function _hideWidget() {
    var w = document.getElementById(WIDGET_ID);
    if (w && w.parentNode) w.parentNode.removeChild(w);
  }

  // Exposed so the header button's onclick can reach it from the global scope.
  window.__jswToggle = function () {
    collapsed = !collapsed;
    render(lastItems);
  };

  // ── Data fetching ────────────────────────────────────────────────────────

  var pollTimer = null;
  var lastJSON  = '';
  var lastItems = [];

  function fetchBoth() {
    return Promise.all([
      fetch('/api/processes/active').then(function (r) { return r.ok ? r.json() : []; }).catch(function () { return []; }),
      fetch('/api/queue/list').then(function (r) { return r.ok ? r.json() : []; }).catch(function () { return []; }),
    ]);
  }

  function mergeItems(processes, queueJobs) {
    var items = [];
    var queueRunningTypes = {};

    queueJobs.forEach(function (j) {
      if (j.status === 'running' || j.status === 'paused' || j.status === 'queued') {
        items.push({
          label:   j.label || j.job_type || 'Job',
          status:  j.status,
          current: j.progress_current || 0,
          total:   j.progress_total || 0,
          error:   j.error_message || '',
        });
        if (j.status === 'running') queueRunningTypes[j.job_type] = true;
      }
    });

    // running/paused are live. failed and interrupted are TERMINAL but shown
    // briefly: /api/processes/active only returns terminal rows while their
    // heartbeat is inside its 90 s window, so they surface then drop by
    // themselves. 'complete' is deliberately excluded — every finished job
    // lingering for 90 s would be noise, and excluding it is what makes the
    // widget disappear promptly when the work is done.
    processes.forEach(function (p) {
      var live = (p.status === 'running' || p.status === 'paused');
      var recentlyEnded = (p.status === 'failed' || p.status === 'interrupted');
      if (!live && !recentlyEnded) return;
      if (live && queueRunningTypes[p.process_type]) return;
      items.push({
        label:   PROCESS_LABELS[p.process_type] || p.process_type || 'Process',
        // A running row whose heartbeat has gone stale is shown as stalled, the
        // same word (and badge colour) the scan page uses for a stalled session.
        status:  (p.status === 'running' && p.is_stalled) ? 'stalled' : p.status,
        current: p.progress_current || 0,
        total:   p.progress_total || 0,
        error:   p.error || '',
      });
    });

    var order = { running: 0, stalled: 1, paused: 1, queued: 2, failed: 3, interrupted: 3 };
    items.sort(function (a, b) {
      return (order[a.status] || 9) - (order[b.status] || 9);
    });
    return items;
  }

  // ── Rendering ────────────────────────────────────────────────────────────

  function esc(s) {
    var d = document.createElement('span');
    d.textContent = (s === null || s === undefined) ? '' : String(s);
    return d.innerHTML;
  }

  function n(v) {
    return (v || 0).toLocaleString();
  }

  // Same markup shape as scan.html's _jqRenderJob, minus .jq-actions: this pass
  // ships no per-row controls (End is Pass E), so the actions row is omitted
  // rather than rendered empty.
  function renderRow(it) {
    var prog = '';
    if (it.total > 0) {
      var pct = Math.round(it.current / it.total * 100);
      prog = '<div class="jq-progress-track"><div class="jq-progress-fill' +
             (it.current >= it.total ? ' ok' : '') +
             '" style="width:' + pct + '%"></div></div>' +
             '<div class="jq-progress-text">' + n(it.current) + ' / ' + n(it.total) +
             ' (' + pct + '%)</div>';
    }
    var err = it.error ? '<div class="jq-error">' + esc(it.error) + '</div>' : '';
    return '<div class="jq-job">' +
             '<div class="jq-job-top">' +
               '<span class="jq-label">' + esc(it.label) + '</span>' +
               '<span class="status-badge ' + esc(it.status) + '">' + esc(it.status) + '</span>' +
             '</div>' +
             prog + err +
           '</div>';
  }

  function render(items) {
    lastItems = items;

    // Auto-hide: fully removed from the DOM when nothing is active, not merely
    // collapsed — an empty shell pinned to the corner is clutter, not status.
    if (!items.length) {
      _hideWidget();
      return;
    }

    var running = 0;
    items.forEach(function (it) { if (it.status === 'running') running++; });

    var title = collapsed
      ? '<span class="jsw-spinner"></span>' +
        (running ? running + ' running' : items.length + ' job' + (items.length === 1 ? '' : 's'))
      : '<span class="jsw-dot">●</span>Background jobs' +
        (items.length > 1 ? ' (' + items.length + ')' : '');

    var w = _widget();
    // The poll rebuilds innerHTML every time the data changes (same approach as
    // the scan panel's list). That discards the toggle button, so a keyboard
    // user focused on it would silently lose focus mid-interaction every few
    // seconds. Remember and restore it.
    var hadFocus = !!(document.activeElement &&
                      document.activeElement.classList &&
                      document.activeElement.classList.contains('jsw-toggle'));

    w.className = collapsed ? 'jsw-collapsed' : '';
    w.innerHTML =
      '<div class="jsw-head">' +
        '<span class="jsw-title">' + title + '</span>' +
        '<button type="button" class="jsw-toggle" onclick="window.__jswToggle()" ' +
                'aria-expanded="' + (collapsed ? 'false' : 'true') + '" ' +
                'aria-controls="jsw-body" ' +
                'title="' + (collapsed ? 'Expand' : 'Minimize') + '">' +
          // The widget is anchored to the TOP edge, so it grows downward:
          // collapsed offers ▾ (expand down), expanded offers ▴ (fold back up).
          (collapsed ? '▾' : '▴') +
        '</button>' +
      '</div>' +
      '<div class="jsw-body" id="jsw-body">' +
        items.map(renderRow).join('') +
      '</div>';

    if (hadFocus) {
      var btn = w.querySelector('.jsw-toggle');
      if (btn) btn.focus();
    }
  }

  // ── Poll loop ────────────────────────────────────────────────────────────

  function poll() {
    fetchBoth().then(function (results) {
      var items = mergeItems(results[0], results[1]);
      var json = JSON.stringify(items);
      if (json !== lastJSON) {
        lastJSON = json;
        render(items);
      }
    });
  }

  function startPolling() {
    if (pollTimer) return;
    poll();
    pollTimer = setInterval(poll, POLL_MS);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  document.addEventListener('visibilitychange', function () {
    if (document.hidden) stopPolling(); else startPolling();
  });

  startPolling();
})();
