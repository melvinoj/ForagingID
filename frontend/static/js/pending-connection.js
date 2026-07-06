/*
 * Reconnect hook (offline-hardening Fix 2).
 *
 * On app load, checks for observations parked as 'pending_connection' — IDs
 * that could not run because the device was offline. If any exist, shows a
 * single dismissible banner with a "Run now" button that triggers the
 * identification pipeline for all pending observations.
 *
 * Behaviour:
 *  - Banner appears only when pending_connection observations exist.
 *  - Dismissible (session-scoped): once dismissed it stays hidden until the
 *    next page load / app open.
 *  - Not automatic — a single button is enough.
 */
(function () {
  "use strict";

  var DISMISS_KEY = "foragingid_pending_conn_dismissed";

  function el(tag, attrs, html) {
    var n = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    if (html != null) n.innerHTML = html;
    return n;
  }

  function removeBanner() {
    var b = document.getElementById("pending-conn-banner");
    if (b && b.parentNode) b.parentNode.removeChild(b);
  }

  function showBanner(count) {
    if (document.getElementById("pending-conn-banner")) return;

    var banner = el("div", { id: "pending-conn-banner", role: "status" });
    banner.style.cssText = [
      "position:sticky", "top:0", "z-index:1200",
      "display:flex", "align-items:center", "gap:12px",
      "padding:10px 16px",
      "background:#fff4d6", "border-bottom:1px solid #e0c068",
      "color:#5a4500", "font-size:0.9rem",
      "box-shadow:0 1px 4px rgba(0,0,0,0.08)"
    ].join(";");

    var label = count === 1
      ? "1 observation waiting for identification"
      : count.toLocaleString() + " observations waiting for identification";

    var text = el("span", null,
      "📡 <strong>" + label + "</strong> — couldn't run while offline.");
    text.style.flex = "1";

    var runBtn = el("button", { id: "pending-conn-run", type: "button" }, "Run now");
    runBtn.style.cssText = [
      "background:#2d5a1b", "color:#fff", "border:none", "border-radius:6px",
      "padding:6px 14px", "font-size:0.85rem", "font-weight:600", "cursor:pointer"
    ].join(";");

    var dismissBtn = el("button", { id: "pending-conn-dismiss", type: "button",
      title: "Dismiss", "aria-label": "Dismiss" }, "✕");
    dismissBtn.style.cssText = [
      "background:transparent", "border:none", "color:#5a4500",
      "font-size:1rem", "cursor:pointer", "padding:4px 6px"
    ].join(";");

    runBtn.addEventListener("click", function () {
      runBtn.disabled = true;
      runBtn.textContent = "Starting…";
      fetch("/api/identify/run-pending", { method: "POST" })
        .then(function (r) { return r.json().then(function (j) { return { ok: r.ok, j: j }; }); })
        .then(function (res) {
          if (!res.ok) throw new Error((res.j && res.j.detail) || "Failed to start");
          runBtn.textContent = "✓ Running";
          text.innerHTML = "📡 <strong>Identifying " + label.replace("waiting for identification", "") .trim() +
            "</strong> — this runs in the background.";
          // Clear the banner shortly after kickoff; the queue will refresh on next load.
          setTimeout(removeBanner, 4000);
        })
        .catch(function (err) {
          runBtn.disabled = false;
          runBtn.textContent = "Run now";
          text.innerHTML = "⚠️ <strong>Couldn't start:</strong> " + (err.message || err);
        });
    });

    dismissBtn.addEventListener("click", function () {
      try { sessionStorage.setItem(DISMISS_KEY, "1"); } catch (e) {}
      removeBanner();
    });

    banner.appendChild(text);
    banner.appendChild(runBtn);
    banner.appendChild(dismissBtn);
    document.body.insertBefore(banner, document.body.firstChild);
  }

  function check() {
    try {
      if (sessionStorage.getItem(DISMISS_KEY) === "1") return;
    } catch (e) {}

    // Guest/read-only sessions never run identification — skip the banner.
    fetch("/api/me")
      .then(function (r) { return r.ok ? r.json() : {}; })
      .catch(function () { return {}; })
      .then(function (me) {
        if (me && me.is_guest) return;
        return fetch("/api/identify/pending-connection")
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (data) {
            if (data && data.count > 0) showBanner(data.count);
          });
      })
      .catch(function () { /* offline or endpoint unavailable — stay silent */ });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", check);
  } else {
    check();
  }
})();
