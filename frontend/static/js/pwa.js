// ForagingID PWA bootstrap — Phase 10a.1.
// Registers the service worker (served from /sw.js for root scope).
// Install App button removed — users add to home screen via browser menu.
//
// New-version prompt (17-B2, 28 Oct 2026): when a new service worker takes
// control of a page that already had one, show a "New version available —
// Reload" bar. It never reloads by itself — a reload could drop an unsent note
// or a walk in progress, so only the user's tap reloads. The first install
// (no controller yet) shows nothing. An installed app tab can stay open for
// days, so the worker is re-checked whenever the page becomes visible again.
(function () {
  'use strict';

  if (!('serviceWorker' in navigator)) return;

  var hadController = !!navigator.serviceWorker.controller;

  function showReloadBar() {
    if (document.getElementById('pwa-reload-bar')) return;
    var bar = document.createElement('div');
    bar.id = 'pwa-reload-bar';
    bar.setAttribute('role', 'status');
    bar.style.cssText = 'position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:100000;' +
      'display:flex;align-items:center;gap:10px;padding:8px 10px 8px 14px;border-radius:10px;' +
      'background:#2d5016;color:#fff;font:14px/1.3 system-ui,sans-serif;box-shadow:0 4px 14px rgba(0,0,0,.25);' +
      'max-width:calc(100vw - 32px)';
    var txt = document.createElement('span');
    txt.textContent = 'New version available';
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = 'Reload';
    btn.style.cssText = 'padding:4px 12px;border:0;border-radius:6px;background:#fff;color:#2d5016;font-weight:600;cursor:pointer';
    btn.onclick = function () { window.location.reload(); };
    var close = document.createElement('button');
    close.type = 'button';
    close.textContent = '×';
    close.setAttribute('aria-label', 'Dismiss');
    close.style.cssText = 'padding:0 6px;border:0;background:none;color:#fff;font-size:18px;cursor:pointer';
    close.onclick = function () { bar.remove(); };
    bar.appendChild(txt); bar.appendChild(btn); bar.appendChild(close);
    document.body.appendChild(bar);
  }

  navigator.serviceWorker.addEventListener('controllerchange', function () {
    if (hadController) showReloadBar();
    hadController = true;
  });

  window.addEventListener('load', function () {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .then(function (reg) {
        console.log('[pwa] service worker registered, scope:', reg.scope);
        document.addEventListener('visibilitychange', function () {
          if (document.visibilityState === 'visible') reg.update().catch(function () {});
        });
      })
      .catch(function (err) { console.warn('[pwa] service worker registration failed:', err); });
  });
})();
