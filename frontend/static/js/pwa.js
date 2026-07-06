// ForagingID PWA bootstrap — Phase 10a.1.
// Registers the service worker (served from /sw.js for root scope).
// Install App button removed — users add to home screen via browser menu.
(function () {
  'use strict';

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .then(function (reg) { console.log('[pwa] service worker registered, scope:', reg.scope); })
        .catch(function (err) { console.warn('[pwa] service worker registration failed:', err); });
    });
  }
})();
