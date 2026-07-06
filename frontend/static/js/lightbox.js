/**
 * Shared lightbox component — used by index.html, review.html, species.html.
 *
 * Each page must include the lightbox HTML (same structure):
 *   <div id="lightbox" style="display:none" onclick="if(event.target===this)closeLightbox()">
 *     <button class="lb-close" onclick="closeLightbox()" title="Close (Esc)">✕</button>
 *     <button class="lb-nav" id="lb-prev" onclick="event.stopPropagation();_lbNav(-1)">‹</button>
 *     <div class="lb-inner">
 *       <img id="lb-img" src="" alt="" onclick="event.stopPropagation();_lbToggleZoom(this)">
 *       <div class="lb-footer">
 *         <span id="lb-caption"></span>
 *         <button class="lb-pin-btn" id="lb-pin-btn"
 *                 onclick="event.stopPropagation();_lbGoToPin()"
 *                 title="Jump to this pin on the map">📍</button>
 *         <span id="lb-counter"></span>
 *       </div>
 *     </div>
 *     <button class="lb-nav" id="lb-next" onclick="event.stopPropagation();_lbNav(+1)">›</button>
 *   </div>
 *
 * API:
 *   openLightbox(images, startIdx)
 *     images: [{ src, caption, hasGPS? }]
 *   closeLightbox()
 *   openEnrichLightbox(url)   – single-image, no nav
 *
 * Pin-button hook (optional, page-specific):
 *   window._lbOnGoToPin = function(obs) { ... }
 */

(function () {
  'use strict';

  let _lbImages   = [];
  let _lbIdx      = 0;
  let _lbZoomScale = 1;
  const _LB_ZOOM_MAX  = 4;
  const _LB_ZOOM_STEP = 0.4;

  function openLightbox(images, startIdx) {
    _lbImages    = images;
    _lbIdx       = (startIdx || 0);
    _lbZoomScale = 1;
    _lbRender();
    document.getElementById('lightbox').style.display = 'flex';
    document.addEventListener('keydown', _lbKey);
  }
  window.openLightbox = openLightbox;

  function closeLightbox() {
    document.getElementById('lightbox').style.display = 'none';
    document.removeEventListener('keydown', _lbKey);
  }
  window.closeLightbox = closeLightbox;

  // Single-image lightbox for enrichment thumbnails (no nav, no pin button)
  function openEnrichLightbox(url) {
    _lbImages    = [{ src: url, caption: '' }];
    _lbIdx       = 0;
    _lbZoomScale = 1;
    const img    = document.getElementById('lb-img');
    if (img) { img.src = url; img.style.transform = ''; img.classList.remove('lb-zoomed'); }
    const caption = document.getElementById('lb-caption');
    const counter = document.getElementById('lb-counter');
    const pinBtn  = document.getElementById('lb-pin-btn');
    if (caption) caption.textContent = '';
    if (counter) counter.textContent = '';
    if (pinBtn)  pinBtn.style.display = 'none';
    const prev = document.getElementById('lb-prev');
    const next = document.getElementById('lb-next');
    if (prev) prev.style.visibility = 'hidden';
    if (next) next.style.visibility = 'hidden';
    document.getElementById('lightbox').style.display = 'flex';
    document.removeEventListener('keydown', _lbKey);
    document.addEventListener('keydown', _enrichLbKey);
  }
  window.openEnrichLightbox = openEnrichLightbox;

  function _enrichLbKey(e) {
    if (e.key === 'Escape') {
      closeLightbox();
      document.removeEventListener('keydown', _enrichLbKey);
    }
  }

  function _lbKey(e) {
    if (e.key === 'Escape')     { closeLightbox(); return; }
    if (e.key === 'ArrowLeft')  { _lbNav(-1);      return; }
    if (e.key === 'ArrowRight') { _lbNav(+1);      return; }
  }

  function _lbNav(dir) {
    _lbIdx = ((_lbIdx + dir) + _lbImages.length) % _lbImages.length;
    _lbZoomScale = 1;
    _lbRender();
  }
  window._lbNav = _lbNav;

  function _lbRender() {
    const item   = _lbImages[_lbIdx] || {};
    const img    = document.getElementById('lb-img');
    if (img) {
      img.src = item.src || '';
      img.style.transform = '';
      img.classList.remove('lb-zoomed');
    }
    const caption = document.getElementById('lb-caption');
    const counter = document.getElementById('lb-counter');
    const pinBtn  = document.getElementById('lb-pin-btn');
    const multi   = _lbImages.length > 1;
    if (caption) caption.textContent = item.caption || '';
    if (counter) counter.textContent = multi ? `${_lbIdx + 1} / ${_lbImages.length}` : '';
    if (pinBtn)  pinBtn.style.display = item.hasGPS ? '' : 'none';
    const prev = document.getElementById('lb-prev');
    const next = document.getElementById('lb-next');
    if (prev) prev.style.visibility = multi ? '' : 'hidden';
    if (next) next.style.visibility = multi ? '' : 'hidden';
  }

  function _lbToggleZoom(img) {
    if (!img) return;
    if (_lbZoomScale > 1) {
      _lbZoomScale = 1;
      img.style.transform = '';
      img.classList.remove('lb-zoomed');
    } else {
      _lbZoomScale = 2.5;
      img.style.transform = `scale(${_lbZoomScale})`;
      img.classList.add('lb-zoomed');
    }
  }
  window._lbToggleZoom = _lbToggleZoom;

  function _lbGoToPin() {
    const obs = _lbImages[_lbIdx];
    if (!obs || !obs.hasGPS) return;
    closeLightbox();
    // Delegate to page-specific handler if defined
    if (typeof window._lbOnGoToPin === 'function') window._lbOnGoToPin(obs);
  }
  window._lbGoToPin = _lbGoToPin;

  // Wire wheel-zoom after DOM is ready
  document.addEventListener('DOMContentLoaded', function () {
    const lb = document.getElementById('lightbox');
    if (!lb) return;
    lb.addEventListener('wheel', function (e) {
      const img = document.getElementById('lb-img');
      if (!img || lb.style.display === 'none') return;
      e.preventDefault();
      _lbZoomScale = Math.max(1, Math.min(_LB_ZOOM_MAX,
        _lbZoomScale + (e.deltaY < 0 ? _LB_ZOOM_STEP : -_LB_ZOOM_STEP)));
      img.style.transform = _lbZoomScale > 1 ? `scale(${_lbZoomScale})` : '';
      img.classList.toggle('lb-zoomed', _lbZoomScale > 1);
    }, { passive: false });
  });
})();
