/**
 * walk-publish.js — the Publish block on a loaded saved walk (Stage C, Melvin
 * 22 Oct 2026). Curator only: hidden for guests (data-guest-hide + the
 * guest-mode check below) and every endpoint refuses guests server-side.
 *
 * Lives in the Walk stats tab, below a divider, in its own box — never inline
 * with Edit / Re-route / Tidy. Flow: Plan (counts, changes since the page on
 * the site, blockers) → AI-agreed photos with "Confirm species" → in-panel
 * confirm (tick + button; no browser dialogs) → background job with steps
 * (also in the Jobs pop-up). Unpublish has its own button and confirm.
 *
 * Server: app/api/experience.py + app/services/experience_publish.py.
 */
(function () {
  'use strict';

  var state = { walkId: null, walkName: '', panel: null, plan: null, planning: false,
                confirmOpen: false, unpubOpen: false, confirmObs: null, job: null, error: '' };
  var pollTimer = null;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function isGuest() { return document.body.classList.contains('guest-mode'); }
  function el() { return document.getElementById('walk-publish'); }
  function slugify(s) {
    return String(s || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '')
      .replace(/ß/g, 'ss').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'walk';
  }
  function fmtDate(iso) {
    if (!iso) return '';
    var d = new Date(iso.endsWith('Z') ? iso : iso + 'Z');        // DB audit times are UTC
    return d.toLocaleString(undefined, { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  }
  async function api(method, url, body) {
    var r = await fetch(url, { method: method, headers: body ? { 'Content-Type': 'application/json' } : {},
                               body: body ? JSON.stringify(body) : undefined });
    var d = await r.json().catch(function () { return {}; });
    if (!r.ok) {
      var e = new Error(typeof d.detail === 'string' ? d.detail : ('HTTP ' + r.status));
      e.status = r.status;
      throw e;
    }
    return d;
  }

  // ── entry point: called by _renderWalkStats ─────────────────────────────────
  async function show(walkId, walkName) {
    var box = el();
    if (!box) return;
    if (!walkId || isGuest()) { box.style.display = 'none'; box.innerHTML = ''; return; }
    if (walkId !== state.walkId) {
      state = { walkId: walkId, walkName: walkName || '', panel: null, plan: null, planning: false,
                confirmOpen: false, unpubOpen: false, confirmObs: null, job: null, error: '' };
    }
    box.style.display = '';
    await reload();
  }

  async function reload() {
    try {
      state.panel = await api('GET', '/api/experience/walks/' + state.walkId + '/panel');
      state.error = '';
      var aj = state.panel.active_job;
      if (aj && aj.status === 'running' && state.panel.publication && aj.publication_id === state.panel.publication.id) {
        state.job = aj;
        poll();
      }
    } catch (e) {
      if (e.status === 403) { el().style.display = 'none'; el().innerHTML = ''; return; }   // guest
      state.error = e.message;
    }
    render();
  }

  // ── render ─────────────────────────────────────────────────────────────────
  function render() {
    var box = el();
    if (!box || !state.walkId) return;
    var h = '<hr class="wpub-divider"><section class="wpub-box" aria-labelledby="wpub-h">' +
            '<h3 id="wpub-h" class="wpub-h">🌐 Publish to the experience site</h3>';
    if (state.error) h += '<div class="wpub-err">' + esc(state.error) + '</div>';
    var p = state.panel && state.panel.publication;
    if (!state.panel) {
      h += '<div class="wpub-muted">Loading…</div>';
    } else if (!p) {
      h += renderCreate();
    } else {
      h += renderStatus(p);
      if (state.job) h += renderJob(state.job);
      else {
        h += renderPlan(p);
        if (p.status === 'published') h += renderUnpublish(p);
      }
    }
    box.innerHTML = h + '</section>';
  }

  function renderCreate() {
    var files = (state.panel.override_files || []);
    var opts = '<option value="">— none (title = walk name) —</option>' + files.map(function (f) {
      return '<option value="' + esc(f.file) + '">' + esc(f.file) + ' — ' + esc(f.title_en || f.slug) + '</option>';
    }).join('');
    return '<div class="wpub-row"><span class="wpub-k">Status</span><span>Not published</span></div>' +
      '<label class="wpub-field">Page address (slug)' +
      '<input id="wpub-new-slug" value="' + esc(slugify(state.walkName)) + '" autocomplete="off"></label>' +
      '<label class="wpub-field">Copy page text from' +
      '<select id="wpub-new-ov" onchange="WalkPublish._ovPicked(this)">' + opts + '</select></label>' +
      '<div class="wpub-hint">Walks already put online by the export script have their title and intro in a file — pick it to keep them.</div>' +
      '<button class="wpub-btn" onclick="WalkPublish.create()">Set up publishing</button>';
  }

  function renderStatus(p) {
    var site = state.panel.site_url;
    var url = p.url || (site + 'w/' + p.slug + '/');
    var st;
    if (p.status === 'published') {
      st = 'Published ' + esc(fmtDate(p.published_at)) + ' · commit <code>' + esc((p.published_commit || '').slice(0, 7)) +
           '</code> · <a href="' + esc(url) + '" target="_blank" rel="noopener">live page ↗</a>';
    } else if (p.status === 'unpublished') {
      st = 'Unpublished ' + esc(fmtDate(p.unpublished_at)) + ' (not on the site)';
    } else {
      st = 'Not published';
    }
    var lr = p.last_repair, rep = '';
    if (lr) {                                     // a run killed by a server restart, checked at start
      var cls = lr.state === 'repaired' ? 'wpub-ok' : (lr.state === 'pending' ? 'wpub-warn' : 'wpub-err');
      rep = '<div class="' + cls + '">' + esc(lr.message || '') + '</div>';
    }
    var locked = p.status === 'published';
    var title = (p.overrides && p.overrides.title_en) ? p.overrides.title_en : state.walkName;
    return '<div class="wpub-row"><span class="wpub-k">Status</span><span>' + st + '</span></div>' + rep +
      '<div class="wpub-row"><span class="wpub-k">Title</span><span>' + esc(title) + '</span></div>' +
      '<div class="wpub-row"><span class="wpub-k">Address</span><span>' +
        (locked ? '<code>' + esc(url) + '</code>'
                : '<input id="wpub-slug" class="wpub-slug" value="' + esc(p.slug) + '" autocomplete="off"> ' +
                  '<button class="wpub-btn-sm" onclick="WalkPublish.saveSlug()">Save</button>') +
      '</span></div>' +
      '<label class="wpub-row wpub-check"><input type="checkbox" id="wpub-default"' + (p.is_default ? ' checked' : '') +
        (state.job ? ' disabled' : '') + ' onchange="WalkPublish.setDefault(this.checked)"> ' +
        '<span>Front page of the site (default walk)' +
        (locked ? ' — takes effect when you republish' : '') + '</span></label>';
  }

  function renderPlan(p) {
    var again = p.status === 'published' ? 'Republish' : 'Publish';
    if (state.planning) return '<div class="wpub-muted">Planning… (reads the walk, nothing is written)</div>';
    if (!state.plan) {
      return '<button class="wpub-btn wpub-primary" onclick="WalkPublish.plan()">' + again + '… (plan first)</button>';
    }
    var pl = state.plan, h = '';
    if (!pl.ok) {
      h += '<div class="wpub-err">The plan could not be made: ' + esc(pl.build_error || 'unknown error') + '</div>';
    } else {
      var sm = pl.summary || {};
      h += '<div class="wpub-sub">Plan</div><div class="wpub-muted">' +
        esc(sm.species) + ' species · ' + esc(sm.stops) + ' stops · ' +
        esc(sm.photo_files) + ' photo files · ' + esc(sm.recipe_count) + ' recipes</div>';
      h += renderChanges(pl.changes || {});
    }
    var probs = pl.problems || [];
    if (probs.length) {
      h += '<div class="wpub-sub wpub-bad">Must be fixed before publishing</div><ul class="wpub-list wpub-bad">' +
        probs.map(function (x) { return '<li>' + esc(x) + '</li>'; }).join('') + '</ul>';
    }
    h += renderAiAgreed(pl.ai_agreed_obs || []);
    h += '<div class="wpub-actions"><button class="wpub-btn-sm" onclick="WalkPublish.plan()">↻ Plan again</button></div>';
    if (!probs.length && pl.ok) h += renderConfirm(p, again);
    return h;
  }

  function renderChanges(c) {
    var w = (c.withheld || []).map(function (x) { return x.species + ' (recipe ' + x.recipe_ids.join(', ') + ')'; });
    var h = '<div class="wpub-sub">Since the page now on the site</div>';
    if (c.first_publish) {
      h += '<div class="wpub-muted">Not on the site yet — this is the first publish of this page.</div>';
    } else {
      var lines = [];
      if (c.added && c.added.length) lines.push('Added: ' + c.added.join(', '));
      if (c.removed && c.removed.length) lines.push('Removed: ' + c.removed.join(', '));
      (c.badge_changes || []).forEach(function (b) { lines.push(b.species + ': ' + b.from + ' → ' + b.to); });
      if (c.recipes_added && c.recipes_added.length) lines.push('Recipes added: ' + c.recipes_added.join('; '));
      if (c.recipes_removed && c.recipes_removed.length) lines.push('Recipes removed: ' + c.recipes_removed.join('; '));
      h += lines.length ? '<ul class="wpub-list">' + lines.map(function (l) { return '<li>' + esc(l) + '</li>'; }).join('') + '</ul>'
                        : '<div class="wpub-muted">No species, badge or recipe changes (' + esc(c.species_now) + ' species).</div>';
    }
    if (w.length) h += '<div class="wpub-muted">Recipes withheld (caution, no curator warning): ' + esc(w.join('; ')) + '</div>';
    return h;
  }

  function renderAiAgreed(items) {
    if (!items.length) return '<div class="wpub-sub">AI-agreed photos</div><div class="wpub-muted">None — every photo on this walk is human-confirmed.</div>';
    var h = '<div class="wpub-sub">AI-agreed photos (' + items.length + ') — shown on the page only because both ID services agreed</div>';
    h += items.map(function (a) {
      var img = a.thumbnail ? '<img src="' + esc(a.thumbnail) + '" alt="" loading="lazy">' : '<div class="wpub-noimg">🌿</div>';
      var tag = a.hazard ? '<span class="wpub-tag wpub-bad">☠ hazard — blocks publishing</span>'
                         : (a.shown ? '<span class="wpub-tag">shown</span>' : '<span class="wpub-tag">not shown</span>');
      var act;
      if (state.confirmObs === a.obs_id) {
        act = '<span class="wpub-confirm-q">Confirm #' + esc(a.obs_id) + ' is ' + esc(a.name) + '?</span> ' +
              '<button class="wpub-btn-sm wpub-primary" onclick="WalkPublish.confirmSpecies(' + a.obs_id + ')">Yes, confirm</button> ' +
              '<button class="wpub-btn-sm" onclick="WalkPublish.askConfirm(null)">Cancel</button>';
      } else {
        act = '<button class="wpub-btn-sm" onclick="WalkPublish.askConfirm(' + a.obs_id + ')">✓ Confirm species</button>';
      }
      return '<div class="wpub-ai' + (a.hazard ? ' hazard' : '') + '">' + img + '<div class="wpub-ai-body">' +
        '<strong>' + esc(a.name) + '</strong> ' + tag +
        '<div class="wpub-muted">Stop ' + esc(a.stop) + ' · #' + esc(a.obs_id) +
          (a.toxicity_severity ? ' · toxicity ' + esc(a.toxicity_severity) : '') + '</div>' +
        '<div>' + act + '</div></div></div>';
    }).join('');
    return h;
  }

  function renderConfirm(p, again) {
    var url = p.url || (state.panel.site_url + 'w/' + p.slug + '/');
    if (!state.confirmOpen) {
      return '<button class="wpub-btn wpub-primary" onclick="WalkPublish.openConfirm(true)">' + again + '…</button>';
    }
    return '<div class="wpub-confirm">' +
      '<p><strong>This makes the exact route line and every stop location public</strong> at ' + esc(url) +
        (p.is_default ? ' and on the site\'s front page' : '') + '.</p>' +
      '<p>Unpublishing later removes the page from the site, but not from the site\'s git history or from copies other people, browsers or search engines have already saved.</p>' +
      '<label class="wpub-check"><input type="checkbox" id="wpub-tick" onchange="WalkPublish._tick(this)"> I understand — ' + esc(again.toLowerCase()) + ' this walk</label>' +
      '<div class="wpub-actions"><button id="wpub-go" class="wpub-btn wpub-primary" disabled onclick="WalkPublish.publish()">' + esc(again) + ' now</button> ' +
      '<button class="wpub-btn-sm" onclick="WalkPublish.openConfirm(false)">Cancel</button></div></div>';
  }

  function renderUnpublish(p) {
    var h = '<hr class="wpub-divider-inner">';
    if (!state.unpubOpen) {
      return h + '<button class="wpub-btn wpub-danger" onclick="WalkPublish.openUnpublish(true)">Unpublish…</button>';
    }
    return h + '<div class="wpub-confirm wpub-confirm-danger">' +
      '<p>Removes <strong>' + esc(p.url || '') + '</strong>' + (p.is_default ? ' and the site\'s front page' : '') +
      ' from the site in one commit. The saved walk stays here.</p>' +
      '<p>The page stays in the site\'s git history and in copies other people or search engines have already saved.</p>' +
      '<label class="wpub-check"><input type="checkbox" id="wpub-untick" onchange="WalkPublish._untick(this)"> I understand — unpublish this page</label>' +
      '<div class="wpub-actions"><button id="wpub-ungo" class="wpub-btn wpub-danger" disabled onclick="WalkPublish.unpublish()">Unpublish now</button> ' +
      '<button class="wpub-btn-sm" onclick="WalkPublish.openUnpublish(false)">Cancel</button></div></div>';
  }

  function renderJob(j) {
    var icon = { pending: '○', running: '◌', ok: '✓', failed: '✕' };
    var h = '<div class="wpub-sub">' + (j.kind === 'publish' ? 'Publishing' : 'Unpublishing') +
      (j.status === 'running' ? '…' : '') + '</div><ol class="wpub-steps">' +
      j.steps.map(function (s) {
        return '<li class="st-' + esc(s.state) + '"><span class="wpub-ic">' + (icon[s.state] || '') + '</span> ' + esc(s.label) +
          (s.detail ? ' <span class="wpub-muted">— ' + esc(s.detail) + '</span>' : '') + '</li>';
      }).join('') + '</ol>';
    if (j.status !== 'running') {
      h += '<div class="' + (j.status === 'done' ? 'wpub-ok' : 'wpub-err') + '">' + esc(j.message) + '</div>' +
        '<button class="wpub-btn-sm" onclick="WalkPublish.closeJob()">OK</button>';
    }
    return h;
  }

  // ── actions ────────────────────────────────────────────────────────────────
  async function create() {
    var slug = (document.getElementById('wpub-new-slug') || {}).value || '';
    var file = (document.getElementById('wpub-new-ov') || {}).value || null;
    try {
      await api('POST', '/api/experience/publications', { saved_walk_id: state.walkId, slug: slug.trim(), overrides_file: file || null });
      await reload();
    } catch (e) { state.error = e.message; render(); }
  }

  function _ovPicked(sel) {
    var f = (state.panel.override_files || []).filter(function (x) { return x.file === sel.value; })[0];
    if (f) { var i = document.getElementById('wpub-new-slug'); if (i) i.value = f.slug; }
  }

  async function saveSlug() {
    var p = state.panel.publication;
    var v = (document.getElementById('wpub-slug') || {}).value || '';
    try {
      await api('PATCH', '/api/experience/publications/' + p.id, { slug: v.trim() });
      state.plan = null; state.confirmOpen = false;
      await reload();
    } catch (e) { state.error = e.message; render(); }
  }

  async function setDefault(on) {
    var p = state.panel.publication;
    try {
      await api('PATCH', '/api/experience/publications/' + p.id, { is_default: !!on });
      state.plan = null; state.confirmOpen = false;
      await reload();
    } catch (e) { state.error = e.message; await reload(); }
  }

  async function plan() {
    var p = state.panel.publication;
    state.planning = true; state.confirmOpen = false; state.confirmObs = null; state.error = ''; render();
    try {
      state.plan = await api('POST', '/api/experience/publications/' + p.id + '/plan');
    } catch (e) {
      state.plan = null; state.error = 'Plan failed: ' + e.message;
    }
    state.planning = false;
    render();
  }

  function askConfirm(obsId) { state.confirmObs = obsId; render(); }

  // The existing manual-verify path (as the Review page's Critical section):
  // PATCH review → manually_verified, which makes it human-confirmed.
  async function confirmSpecies(obsId) {
    try {
      await api('PATCH', '/api/observations/' + obsId + '/review?status=manually_verified');
      state.confirmObs = null;
      await plan();                                           // the blocker list comes from the plan
    } catch (e) { state.error = 'Confirm failed for #' + obsId + ': ' + e.message; render(); }
  }

  function openConfirm(on) { state.confirmOpen = !!on; render(); }
  function openUnpublish(on) { state.unpubOpen = !!on; render(); }
  function _tick(cb) { var b = document.getElementById('wpub-go'); if (b) b.disabled = !cb.checked; }
  function _untick(cb) { var b = document.getElementById('wpub-ungo'); if (b) b.disabled = !cb.checked; }

  async function publish() {
    var tick = document.getElementById('wpub-tick');
    if (!tick || !tick.checked) return;                       // the server refuses it unticked too
    await startJob('publish');
  }

  async function unpublish() {
    var tick = document.getElementById('wpub-untick');
    if (!tick || !tick.checked) return;
    await startJob('unpublish');
  }

  async function startJob(kind) {
    var p = state.panel.publication;
    try {
      state.job = await api('POST', '/api/experience/publications/' + p.id + '/' + kind, { confirm: true });
      state.confirmOpen = false; state.unpubOpen = false; state.error = '';
      render();
      poll();
    } catch (e) { state.error = e.message; render(); }
  }

  function poll() {
    clearTimeout(pollTimer);
    if (!state.job || state.job.status !== 'running') return;
    pollTimer = setTimeout(async function () {
      try {
        state.job = await api('GET', '/api/experience/jobs/' + state.job.job_id);
      } catch (e) {
        state.job.status = 'failed'; state.job.message = e.message;
      }
      render();
      if (state.job.status === 'running') poll();
      else { state.plan = null; await reloadKeepJob(); }
    }, 2000);
  }

  async function reloadKeepJob() {
    var j = state.job;
    await reload();
    state.job = j;
    render();
  }

  async function closeJob() { state.job = null; state.plan = null; await reload(); }

  window.WalkPublish = { show: show, create: create, saveSlug: saveSlug, setDefault: setDefault, plan: plan,
                         askConfirm: askConfirm, confirmSpecies: confirmSpecies, openConfirm: openConfirm,
                         openUnpublish: openUnpublish, publish: publish, unpublish: unpublish, closeJob: closeJob,
                         _tick: _tick, _untick: _untick, _ovPicked: _ovPicked };
})();
