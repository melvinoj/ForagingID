/**
 * guest-mode.js — detect ngrok guest sessions and apply read-only UI.
 *
 * Included on every page. Calls /api/me (fast, local) and if is_guest=true:
 *  - Adds body.guest-mode class (CSS hook for per-page element hiding)
 *  - Injects CSS to hide admin-only controls
 *
 * Nav link hiding, the Map→/map repoint, and the guest badge moved into
 * site-header.js's own /api/me read (Map Redesign P3-nav) — this file's own
 * copies used to target #header nav, which no longer exists on any page.
 */
(async function _guestModeInit() {
  let d = {};
  try {
    const r = await fetch('/api/me');
    if (r.ok) d = await r.json();
  } catch (_) { /* graceful degradation */ }
  const isGuest = !!d.is_guest;

  // Owner-only: surface a degraded iNaturalist token so it isn't silent — an expired
  // token routes every scan to needs_review (PlantNet-only). Dismissible per session.
  if (!isGuest && d.inat && d.inat.state && d.inat.state !== 'ok' && d.inat.state !== 'unknown') {
    _showInatBanner(d.inat);
  }

  if (!isGuest) return;

  // ── Mark body ──────────────────────────────────────────────────────────
  document.body.classList.add('guest-mode');

  // ── Inject guest-mode CSS ──────────────────────────────────────────────
  const style = document.createElement('style');
  style.textContent = `
    /* Elements that should always be hidden from guests */
    body.guest-mode [data-guest-hide],
    body.guest-mode .rename-btn,
    body.guest-mode .sp-rename-btn,
    body.guest-mode .rename-species-btn,
    body.guest-mode .audit-str-btn,
    body.guest-mode .det-btn.danger,
    body.guest-mode .det-btn.enrich,
    body.guest-mode #recipe-review-link,
    body.guest-mode .edit-in-review,
    body.guest-mode .prof-rename-btns {
      display: none !important;
    }
    /* "Send to review queue" button in map detail panel */
    body.guest-mode .det-btn[onclick*="sendToReview"] { display: none !important; }
  `;
  document.head.appendChild(style);
})();

// ── iNaturalist-down banner (owner-only) ───────────────────────────────────────
// Function declaration → hoisted, so the async IIFE above can call it. Dismissible
// per browser session (re-appears next session if iNat is still degraded).
function _showInatBanner(inat) {
  if (document.getElementById('inat-down-banner')) return;
  try { if (sessionStorage.getItem('fid_inat_banner_dismissed') === inat.state) return; } catch (e) {}

  var urgent = (inat.state === 'token_expired');
  var msg;
  if (inat.state === 'token_expired')      msg = 'iNaturalist token expired — identification is running PlantNet-only, so new scans route to the review queue.';
  else if (inat.state === 'unreachable')   msg = 'iNaturalist is unreachable — identification is running PlantNet-only (scans route to review).';
  else if (inat.state === 'rate_limited')  msg = 'iNaturalist is rate-limiting — some scans may route to review until it recovers.';
  else                                     msg = 'iNaturalist error (' + (inat.detail || inat.state) + ') — identification may be degraded.';

  var prevPad = document.body.style.paddingTop || '';
  var bar = document.createElement('div');
  bar.id = 'inat-down-banner';
  bar.setAttribute('role', 'status');
  bar.style.cssText = [
    'position:fixed', 'top:0', 'left:0', 'right:0', 'z-index:10050',
    'display:flex', 'align-items:center', 'gap:12px', 'padding:8px 14px',
    'background:' + (urgent ? '#7a1f1f' : '#7a5a1f'), 'color:#fff',
    'font:600 0.82rem system-ui,-apple-system,sans-serif',
    'box-shadow:0 2px 8px rgba(0,0,0,0.3)',
  ].join(';');
  bar.innerHTML =
    '<span style="font-size:1rem">⚠️</span>' +
    '<span style="flex:1">' + msg +
      ' <a href="/settings" style="color:#ffe;text-decoration:underline">Refresh token in Settings →</a></span>' +
    '<button aria-label="Dismiss" style="background:rgba(255,255,255,.18);border:none;color:#fff;' +
      'border-radius:6px;padding:3px 9px;cursor:pointer;font-weight:700">Dismiss</button>';
  bar.querySelector('button').addEventListener('click', function () {
    try { sessionStorage.setItem('fid_inat_banner_dismissed', inat.state); } catch (e) {}
    if (bar.parentNode) bar.parentNode.removeChild(bar);
    document.body.style.paddingTop = prevPad;
    if (window.__setNavChipOffset) window.__setNavChipOffset(0);
  });
  document.body.style.paddingTop = (parseInt(prevPad || '0', 10) + 40) + 'px';
  document.body.insertBefore(bar, document.body.firstChild);
  if (window.__setNavChipOffset) window.__setNavChipOffset(40);
}
