// ── Shared site nav: chip → drawer (Map Redesign P3-nav) ───────────────────
// Extracted from the map-page nav drawer (Map Redesign P1). Builds and mounts
// itself into <body> on script load. Exposes openNavDrawer()/closeNavDrawer()
// globally so page-specific code (e.g. Escape-key handlers) can still call
// them. Dispatches a 'sitenav:open' window event on open so map-only chrome
// (the config sheet) can close itself without this file knowing it exists.

(function () {
  // curatorOnly mirrors the server's own guest gate (main.py _GUEST_BLOCKED_PATHS
  // + the guest middleware's redirect-away behaviour) — one flag instead of the
  // two separate, inconsistent lists (guest-mode.js's hide-list vs. the old
  // per-page .curator-nav class) that predated this file.
  var NAV_LINKS = [
    { href: '/',           label: 'Map' },
    { href: '/seasons',    label: 'Seasons' },
    { href: '/taxonomy',   label: 'Taxonomy' },
    { href: '/species',    label: 'Species' },
    { href: '/sightings',  label: 'Sightings' },
    { href: '/encounters', label: 'Encounters', badgeId: 'nav-badge-encounters' },
    { href: '/lists',      label: 'Booklets' },
    { href: '/workshops',  label: 'Workshops', curatorOnly: true },
    { href: '/review',     label: 'Review', badgeId: 'nav-badge-review', curatorOnly: true },
    { href: '/scan',       label: 'Scan', curatorOnly: true },
    { href: '/settings',   label: 'Settings', curatorOnly: true },
    { href: '/about',      label: 'About' }
  ];

  function _buildHeader() {
    var here = location.pathname;

    var chip = document.createElement('button');
    chip.id = 'site-nav-chip';
    chip.setAttribute('aria-label', 'Open navigation');
    chip.setAttribute('aria-haspopup', 'true');
    chip.setAttribute('aria-expanded', 'false');
    chip.innerHTML = '<img src="/static/icons/dandelion-icon.svg" alt="" width="27" height="27" style="filter:brightness(0) invert(1)">';
    chip.onclick = window.openNavDrawer;

    var scrim = document.createElement('div');
    scrim.id = 'nav-drawer-scrim';
    scrim.onclick = window.closeNavDrawer;

    var drawer = document.createElement('div');
    drawer.id = 'nav-drawer';
    drawer.setAttribute('role', 'dialog');
    drawer.setAttribute('aria-modal', 'true');
    drawer.setAttribute('aria-label', 'Navigation');

    var header = document.createElement('div');
    header.id = 'nav-drawer-header';
    var titleWrap = document.createElement('div');
    titleWrap.id = 'nav-drawer-title-wrap';
    var title = document.createElement('span');
    title.id = 'nav-drawer-title';
    title.textContent = 'LandMemory';
    var guestBadge = document.createElement('span');
    guestBadge.id = 'nav-guest-badge';
    guestBadge.textContent = '👁 Guest view';
    titleWrap.appendChild(title);
    titleWrap.appendChild(guestBadge);
    var closeBtn = document.createElement('button');
    closeBtn.id = 'nav-drawer-close';
    closeBtn.setAttribute('aria-label', 'Close navigation');
    closeBtn.textContent = '✕';
    closeBtn.onclick = window.closeNavDrawer;
    header.appendChild(titleWrap);
    header.appendChild(closeBtn);

    var nav = document.createElement('nav');
    nav.id = 'nav-drawer-links';
    NAV_LINKS.forEach(function (item) {
      var a = document.createElement('a');
      a.href = item.href;
      if (item.href === here || (item.href === '/' && here === '/map')) {
        a.className = 'active';
      }
      a.appendChild(document.createTextNode(item.label));
      if (item.badgeId) {
        var badge = document.createElement('span');
        badge.className = 'nav-badge';
        badge.id = item.badgeId;
        a.appendChild(badge);
      }
      if (item.curatorOnly) {
        a.classList.add('curator-nav');
        a.style.display = 'none';
      }
      nav.appendChild(a);
    });

    drawer.appendChild(header);
    drawer.appendChild(nav);

    // Explicit mount point for the global job-status widget. The widget used to
    // look for #header, which no longer exists on any page, and silently fell
    // back to document.body.firstChild. This anchor is owned by the header so
    // the widget has one predictable, site-wide home.
    var jobMount = document.createElement('div');
    jobMount.id = 'job-status-mount';

    document.body.appendChild(chip);
    document.body.appendChild(scrim);
    document.body.appendChild(drawer);
    document.body.insertBefore(jobMount, document.body.firstChild);
  }

  // Load the global job widget once, owner-only. Guests must never see process
  // detail (it carries species names), same reasoning as the curatorOnly links.
  function _loadJobWidget() {
    if (window.__jobStatusWidgetLoaded) return;
    window.__jobStatusWidgetLoaded = true;
    var s = document.createElement('script');
    s.src = '/static/js/job-status-widget.js';
    s.defer = true;
    document.head.appendChild(s);
  }

  // The chip is position:fixed, so it ignores body.style.paddingTop — the
  // mechanism guest-mode.js's iNaturalist-down banner uses to push flow
  // content clear of itself. This lets that banner nudge the chip down too,
  // via a CSS variable (not the element directly) so it applies correctly
  // even if called before this file has built the chip — guest-mode.js's
  // /api/me fetch can resolve before this script runs.
  window.__setNavChipOffset = function (px) {
    document.documentElement.style.setProperty('--nav-chip-offset', px + 'px');
  };

  window.openNavDrawer = function () {
    document.getElementById('nav-drawer').classList.add('open');
    document.getElementById('nav-drawer-scrim').classList.add('show');
    document.getElementById('site-nav-chip').setAttribute('aria-expanded', 'true');
    window.dispatchEvent(new Event('sitenav:open'));
  };
  window.closeNavDrawer = function () {
    document.getElementById('nav-drawer').classList.remove('open');
    document.getElementById('nav-drawer-scrim').classList.remove('show');
    document.getElementById('site-nav-chip').setAttribute('aria-expanded', 'false');
  };

  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape') window.closeNavDrawer();
  });

  function _initIdentity() {
    // Single /api/me read driving every guest-vs-owner nav decision: revealing
    // curatorOnly links, repointing Map to the guest-stable /map URL (bare "/"
    // serves the guest landing page instead), showing the guest badge, and
    // gating the Encounters transcript-badge fetch below (consolidated from
    // guest-mode.js and auto-transcribe.js, which used to find these elements
    // via the now-removed per-page #header nav).
    fetch('/api/me').then(function (r) { return r.json(); }).then(function (d) {
      if (d.is_guest) {
        var mapLink = document.querySelector('#nav-drawer-links a[href="/"]');
        if (mapLink) mapLink.setAttribute('href', '/map');
        var badge = document.getElementById('nav-guest-badge');
        if (badge) badge.classList.add('visible');
      } else {
        document.querySelectorAll('.curator-nav').forEach(function (el) { el.style.display = ''; });
        _initEncountersBadge();
        _loadJobWidget();
      }
    }).catch(function () {});
  }

  function _initEncountersBadge() {
    if (location.pathname === '/encounters') return;
    fetch('/api/encounters/pending-transcripts').then(function (r) {
      return r.ok ? r.json() : null;
    }).then(function (d) {
      var count = d && d.count || 0;
      var badge = document.getElementById('nav-badge-encounters');
      if (!badge || !count) return;
      badge.textContent = count;
      badge.title = count + ' encounter' + (count === 1 ? '' : 's') + ' with audio not yet transcribed';
      badge.classList.add('visible');
    }).catch(function () {});
  }

  function _initReviewBadge() {
    // Links to whichever bucket (pending vs needs_review) is larger, same
    // priority rule as the old stats-bar link (Map Redesign P1).
    fetch('/api/observations/stats').then(function (r) {
      return r.ok ? r.json() : null;
    }).then(function (d) {
      if (!d) return;
      var pending = d.pending_review || 0;
      var flagged = d.needs_review || 0;
      var n = pending + flagged;
      var badge = document.getElementById('nav-badge-review');
      if (!badge) return;
      if (n > 0) {
        var status = flagged > 0 ? 'needs_review' : 'pending';
        badge.textContent = n;
        badge.classList.add('visible');
        badge.closest('a').href = '/review?status=' + status;
      } else {
        badge.classList.remove('visible');
      }
    }).catch(function () {});
  }

  _buildHeader();
  _initIdentity();
  _initReviewBadge();
})();
