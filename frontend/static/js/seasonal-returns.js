/*
 * seasonal-returns.js — Seasonal return notifications bell (Phase 11b).
 *
 * Injects a bell into the page header (owner-only) showing species you've
 * confirmed before that are now coming back into season — driven by phenology
 * where set, falling back to the anniversary of your last sighting. In-app only;
 * no browser push. Dismissals are deduped per species per season server-side.
 *
 * Shared across all pages: include with <script src="/static/js/seasonal-returns.js"></script>.
 */
(function () {
  "use strict";

  var _items = [];        // currently loaded items (top N, or all once expanded)
  var _total = 0;         // full ranked count (drives badge + "Show all (N)")
  var _allLoaded = false; // true once the full list has been fetched
  var _open = false;

  function _esc(s) {
    if (s == null) return "";
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;")
      .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  function _injectStyles() {
    if (document.getElementById("seasonal-returns-styles")) return;
    var css = document.createElement("style");
    css.id = "seasonal-returns-styles";
    css.textContent = [
      "#sr-bell{position:relative;margin-left:auto;background:transparent;border:none;",
      "cursor:pointer;font-size:1.25rem;line-height:1;padding:4px 6px;color:#cfe6a8;}",
      "#sr-bell:hover{color:#fff;}",
      "#sr-badge{position:absolute;top:-2px;right:-2px;min-width:16px;height:16px;",
      "padding:0 4px;border-radius:8px;background:#cf5a2a;color:#fff;font-size:0.66rem;",
      "font-weight:700;display:flex;align-items:center;justify-content:center;}",
      "#sr-panel{position:absolute;top:46px;right:8px;z-index:1300;width:min(380px,92vw);",
      "max-height:70vh;overflow-y:auto;background:#1f1f1f;border:1px solid #3a3a3a;",
      "border-radius:10px;box-shadow:0 8px 28px rgba(0,0,0,0.5);padding:8px;}",
      "#sr-panel.hidden{display:none;}",
      "#sr-panel .sr-head{font-size:0.78rem;color:#9fb886;text-transform:uppercase;",
      "letter-spacing:0.04em;padding:6px 8px 8px;}",
      ".sr-item{display:flex;gap:10px;padding:9px 8px;border-top:1px solid #2e2e2e;align-items:flex-start;}",
      ".sr-item .sr-ico{font-size:1.1rem;flex-shrink:0;margin-top:1px;}",
      ".sr-item .sr-body{flex:1;min-width:0;}",
      ".sr-sp{font-size:0.9rem;font-weight:600;color:#c8e6a0;font-style:italic;}",
      ".sr-sp small{font-style:normal;font-weight:400;color:#9a9a9a;}",
      ".sr-reason{font-size:0.78rem;margin-top:2px;}",
      ".sr-reason.now{color:#8fd16a;}.sr-reason.soon{color:#d8c06a;}",
      ".sr-last{font-size:0.72rem;color:#8a8a8a;margin-top:3px;}",
      ".sr-links{margin-top:5px;display:flex;gap:10px;}",
      ".sr-links a{font-size:0.74rem;color:#7fb3e8;text-decoration:none;}",
      ".sr-links a:hover{text-decoration:underline;}",
      ".sr-dismiss{background:transparent;border:1px solid #444;color:#999;border-radius:5px;",
      "padding:3px 7px;font-size:0.74rem;cursor:pointer;flex-shrink:0;}",
      ".sr-dismiss:hover{border-color:#aa4444;color:#f87171;}",
      "#sr-showall{display:block;width:100%;margin-top:6px;padding:8px;border:none;",
      "border-top:1px solid #2e2e2e;background:transparent;color:#7fb3e8;font-size:0.8rem;",
      "cursor:pointer;}",
      "#sr-showall:hover{color:#a8d0f8;text-decoration:underline;}",
      "#sr-empty{padding:14px 10px;color:#777;font-size:0.82rem;text-align:center;}"
    ].join("");
    document.head.appendChild(css);
  }

  function _renderItem(it) {
    var name = it.common_name
      ? '<span class="sr-sp">' + _esc(it.scientific_name) + ' <small>(' + _esc(it.common_name) + ')</small></span>'
      : '<span class="sr-sp">' + _esc(it.scientific_name) + '</span>';
    var lastDate = it.last_seen ? new Date(it.last_seen).toLocaleDateString() : "";
    var lastBits = [];
    if (lastDate) lastBits.push("Last seen " + _esc(lastDate));
    if (it.last_seen_place) lastBits.push(_esc(it.last_seen_place));
    var peak = it.peak_season ? ' · peak ' + _esc(it.peak_season) : "";

    var mapHref = "/?species=" + encodeURIComponent(it.scientific_name);
    var seasonHref = "/my-season?species=" + encodeURIComponent(it.species_id);

    return '<div class="sr-item" data-sid="' + it.species_id + '" data-key="' + _esc(it.season_key) + '">' +
      '<div class="sr-ico">' + (it.timing === "now" ? "🌿" : "🌱") + '</div>' +
      '<div class="sr-body">' +
        name +
        '<div class="sr-reason ' + (it.timing === "now" ? "now" : "soon") + '">' + _esc(it.reason) + peak + '</div>' +
        (lastBits.length ? '<div class="sr-last">' + lastBits.join(" · ") + '</div>' : "") +
        '<div class="sr-links">' +
          '<a href="' + _esc(mapHref) + '">View on map</a>' +
          '<a href="' + _esc(seasonHref) + '">My Season</a>' +
        '</div>' +
      '</div>' +
      '<button class="sr-dismiss" title="Dismiss for this season">Dismiss</button>' +
    '</div>';
  }

  function _renderPanel() {
    var panel = document.getElementById("sr-panel");
    if (!panel) return;

    var header = '<div class="sr-head">Seasonal returns' +
      (_total ? ' · ' + (_allLoaded ? _total : Math.min(_items.length, _total) + ' of ' + _total) : '') +
      '</div>';

    if (!_items.length) {
      panel.innerHTML = header +
        '<div id="sr-empty">Nothing returning right now. Check back as the seasons turn.</div>';
      return;
    }

    var body = _items.map(_renderItem).join("");
    // "Show all" only when there are more on the server than we've loaded.
    var showAll = (!_allLoaded && _total > _items.length)
      ? '<button id="sr-showall" type="button">Show all (' + _total + ')</button>'
      : "";
    panel.innerHTML = header + body + showAll;

    panel.querySelectorAll(".sr-dismiss").forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.stopPropagation();
        var row = btn.closest(".sr-item");
        _dismiss(row.getAttribute("data-sid"), row.getAttribute("data-key"));
      });
    });
    var saBtn = document.getElementById("sr-showall");
    if (saBtn) saBtn.addEventListener("click", function (ev) { ev.stopPropagation(); _loadAll(); });
  }

  function _updateBadge() {
    var badge = document.getElementById("sr-badge");
    if (!badge) return;
    if (_total > 0) {
      badge.textContent = _total > 99 ? "99+" : String(_total);
      badge.style.display = "";
    } else {
      badge.style.display = "none";
    }
  }

  function _dismiss(speciesId, seasonKey) {
    fetch("/api/notifications/seasonal-returns/dismiss", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ species_id: Number(speciesId), season_key: seasonKey })
    }).then(function (r) {
      if (!r.ok) throw new Error("dismiss failed");
      _items = _items.filter(function (it) {
        return !(String(it.species_id) === String(speciesId) && it.season_key === seasonKey);
      });
      _total = Math.max(0, _total - 1);
      _updateBadge();
      _renderPanel();
    }).catch(function () { /* stay silent — will reappear next load */ });
  }

  function _toggle() {
    var panel = document.getElementById("sr-panel");
    if (!panel) return;
    _open = !_open;
    panel.classList.toggle("hidden", !_open);
    if (_open) _renderPanel();
  }

  function _mount() {
    var header = document.getElementById("header");
    if (!header || document.getElementById("sr-bell")) return;

    var bell = document.createElement("button");
    bell.id = "sr-bell";
    bell.type = "button";
    bell.setAttribute("aria-label", "Seasonal returns");
    bell.title = "Seasonal returns";
    bell.innerHTML = '🔔<span id="sr-badge" style="display:none">0</span>';

    var panel = document.createElement("div");
    panel.id = "sr-panel";
    panel.className = "hidden";

    bell.addEventListener("click", function (ev) { ev.stopPropagation(); _toggle(); });
    document.addEventListener("click", function (ev) {
      if (_open && !panel.contains(ev.target) && ev.target !== bell) {
        _open = false; panel.classList.add("hidden");
      }
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && _open) { _open = false; panel.classList.add("hidden"); }
    });

    header.appendChild(bell);
    header.appendChild(panel);
  }

  function _load() {
    fetch("/api/notifications/seasonal-returns")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        _items = data.items || [];
        _total = data.total || 0;
        _allLoaded = _items.length >= _total;
        _updateBadge();
        if (_open) _renderPanel();
      })
      .catch(function () { /* offline or unavailable — leave bell quiet */ });
  }

  function _loadAll() {
    var saBtn = document.getElementById("sr-showall");
    if (saBtn) { saBtn.disabled = true; saBtn.textContent = "Loading…"; }
    fetch("/api/notifications/seasonal-returns?all=true")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) { if (saBtn) { saBtn.disabled = false; saBtn.textContent = "Show all (" + _total + ")"; } return; }
        _items = data.items || [];
        _total = data.total || 0;
        _allLoaded = true;
        _updateBadge();
        _renderPanel();
      })
      .catch(function () {
        if (saBtn) { saBtn.disabled = false; saBtn.textContent = "Show all (" + _total + ")"; }
      });
  }

  function _init() {
    // Owner-only: guests never see the bell (their sightings aren't theirs).
    fetch("/api/me")
      .then(function (r) { return r.ok ? r.json() : {}; })
      .catch(function () { return {}; })
      .then(function (me) {
        if (me && me.is_guest) return;
        _injectStyles();
        _mount();
        _load();
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", _init);
  } else {
    _init();
  }
})();
