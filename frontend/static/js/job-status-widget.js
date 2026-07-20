/**
 * job-status-widget.js — global banner for background jobs.
 *
 * Shows a horizontal bar below the top nav when background processes or
 * job-queue items are running.  Same mechanism as offline.js / pending-
 * connection.js banners: inserts after #header, adjusts body padding so
 * page content is not overlapped.
 *
 * Include once per page:
 *   <script src="/static/js/job-status-widget.js"></script>
 */
(function () {
  'use strict';

  // Idempotence: site-header.js injects this file on every page. Guard in case a
  // page also carries a legacy <script> tag, which would otherwise start a
  // second poller and a second banner.
  if (window.__jobStatusWidgetInit) return;
  window.__jobStatusWidgetInit = true;

  var POLL_MS = 3000;
  var BANNER_ID = 'job-status-banner';
  var BANNER_H = 32; // px reserved for body padding

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
  };

  // ── Banner management ────────────────────────────────────────────────────

  function _showBanner(html) {
    var b = document.getElementById(BANNER_ID);
    if (!b) {
      b = document.createElement('div');
      b.id = BANNER_ID;
      b.setAttribute('role', 'status');
      b.style.cssText = [
        'position:sticky', 'top:0', 'z-index:1100',
        'display:flex', 'align-items:center', 'gap:10px',
        'padding:6px 16px',
        'background:#1e2a1e', 'color:#e8e0d0',
        'font-size:0.82rem', 'font-family:system-ui,sans-serif',
        'border-bottom:1px solid rgba(90,138,90,0.4)',
        'box-shadow:0 1px 4px rgba(0,0,0,0.25)',
        'min-height:28px',
      ].join(';');
      // Mount into the anchor owned by site-header.js. (#header was the old
      // target and no longer exists on any page; body.firstChild remains only
      // as a fallback for a page that somehow loads this without the header.)
      var mount = document.getElementById('job-status-mount');
      if (mount) {
        mount.appendChild(b);
      } else {
        document.body.insertBefore(b, document.body.firstChild);
      }
    }
    b.innerHTML = html;
  }

  function _hideBanner() {
    var b = document.getElementById(BANNER_ID);
    if (b && b.parentNode) {
      b.parentNode.removeChild(b);
    }
  }

  // ── Data fetching ────────────────────────────────────────────────────────

  var pollTimer = null;
  var lastJSON = '';

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
        });
        if (j.status === 'running') queueRunningTypes[j.job_type] = true;
      }
    });

    // running/paused are live. failed and interrupted are TERMINAL but shown
    // briefly: /api/processes/active only returns terminal rows while their
    // heartbeat is inside its 90 s window, so they surface then drop by
    // themselves. 'complete' is deliberately excluded — every finished job
    // lingering for 90 s would be noise.
    processes.forEach(function (p) {
      var live = (p.status === 'running' || p.status === 'paused');
      var recentlyEnded = (p.status === 'failed' || p.status === 'interrupted');
      if (!live && !recentlyEnded) return;
      if (live && queueRunningTypes[p.process_type]) return;
      items.push({
        label:   PROCESS_LABELS[p.process_type] || p.process_type || 'Process',
        status:  p.status,
        current: p.progress_current || 0,
        total:   p.progress_total || 0,
      });
    });

    var order = { running: 0, paused: 1, queued: 2, failed: 3, interrupted: 3 };
    items.sort(function (a, b) {
      return (order[a.status] || 9) - (order[b.status] || 9);
    });
    return items;
  }

  // ── Rendering ────────────────────────────────────────────────────────────

  function esc(s) {
    var d = document.createElement('span');
    d.textContent = s;
    return d.innerHTML;
  }

  function render(items) {
    if (!items.length) {
      _hideBanner();
      return;
    }

    var parts = [];
    items.forEach(function (it) {
      var text = esc(it.label);
      if (it.total > 0) text += ' — ' + it.current + '/' + it.total;
      if (it.status === 'paused') text += ' (paused)';
      if (it.status === 'queued') text += ' (queued)';
      // interrupted renders like failed: the run stopped without finishing.
      if (it.status === 'failed') text += ' (failed)';
      if (it.status === 'interrupted') text += ' (interrupted)';
      parts.push(text);
    });

    var dot = '<span style="color:#5a8a5a;animation:jsw-pulse 1.6s ease-in-out infinite;font-size:0.7rem;margin-right:2px">●</span>';
    var html = dot + '<span style="flex:1">' + parts.join(' &nbsp;·&nbsp; ') + '</span>';
    _showBanner(html);
  }

  // ── Pulse animation (inject once) ────────────────────────────────────────

  var s = document.createElement('style');
  s.textContent = '@keyframes jsw-pulse{0%,100%{opacity:1}50%{opacity:.4}}';
  document.head.appendChild(s);

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
