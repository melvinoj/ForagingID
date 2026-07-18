/**
 * git-banner.js — shared "remember to push" notification banner.
 *
 * Usage:  showGitBanner()
 *
 * The banner appears at the bottom centre of the screen, auto-dismisses after
 * 10 seconds, and has a "Copy git command" button that copies
 * "git push origin main" to the clipboard.
 *
 * Include once per page:
 *   <script src="/static/js/git-banner.js"></script>
 */

(function () {
  'use strict';

  const COMMAND  = 'cd ~/ForagingID\ngit push origin main';
  const AUTO_MS  = 10000;   // auto-dismiss delay

  let _banner    = null;
  let _timer     = null;
  let _injected  = false;

  function _inject() {
    if (_injected) return;
    _injected = true;

    // ── Styles ────────────────────────────────────────────────────────────
    const style = document.createElement('style');
    style.textContent = `
      #git-push-banner {
        position: fixed;
        bottom: -90px;           /* starts off-screen */
        left: 50%;
        transform: translateX(-50%);
        z-index: 9999;
        background: #1a3a0a;
        color: #e8f5d0;
        border-radius: 10px;
        box-shadow: 0 4px 18px rgba(0,0,0,.35);
        padding: 10px 14px 10px 16px;
        display: flex;
        align-items: center;
        gap: 10px;
        font-family: system-ui, sans-serif;
        font-size: 0.82rem;
        white-space: nowrap;
        min-width: 260px;
        max-width: min(520px, 92vw);
        transition: bottom 0.28s cubic-bezier(.22,1,.36,1);
        pointer-events: none;
        opacity: 0;
      }
      #git-push-banner.visible {
        bottom: 22px;
        pointer-events: auto;
        opacity: 1;
      }
      #git-push-banner .gbanner-icon { font-size: 1rem; flex-shrink: 0; }
      #git-push-banner .gbanner-text { flex: 1; line-height: 1.35; white-space: normal; }
      #git-push-banner .gbanner-text strong { color: #b8d48a; }
      #git-push-banner .gbanner-copy {
        padding: 5px 11px;
        background: #3a6b1e;
        border: 1px solid #5a9e30;
        color: white;
        border-radius: 6px;
        font-size: 0.76rem;
        cursor: pointer;
        flex-shrink: 0;
        transition: background 0.15s;
        font-family: inherit;
      }
      #git-push-banner .gbanner-copy:hover   { background: #4d8c28; }
      #git-push-banner .gbanner-copy.copied  {
        background: #256e14; border-color: #7ed348; color: #c8f5a0;
      }
      #git-push-banner .gbanner-dismiss {
        background: transparent;
        border: none;
        color: #8aad60;
        font-size: 1.1rem;
        line-height: 1;
        cursor: pointer;
        padding: 2px 4px;
        border-radius: 4px;
        flex-shrink: 0;
        font-family: inherit;
        transition: color 0.1s;
      }
      #git-push-banner .gbanner-dismiss:hover { color: white; }
      #git-push-progress {
        position: absolute;
        bottom: 0; left: 0;
        height: 2px;
        border-radius: 0 0 10px 10px;
        background: #5a9e30;
        width: 100%;
        transform-origin: left;
        transition: transform linear;
      }
    `;
    document.head.appendChild(style);

    // ── HTML ──────────────────────────────────────────────────────────────
    const el = document.createElement('div');
    el.id = 'git-push-banner';
    el.innerHTML = `
      <span class="gbanner-icon">📤</span>
      <span class="gbanner-text">
        <strong>Changes saved</strong> — remember to push to GitHub
      </span>
      <button class="gbanner-copy" onclick="window._gitBannerCopy()" title="Copies two lines: cd ~/ForagingID &amp;&amp; git push origin main">
        Copy git command
      </button>
      <button class="gbanner-dismiss" onclick="window._gitBannerDismiss()" aria-label="Dismiss">✕</button>
      <div id="git-push-progress"></div>
    `;
    document.body.appendChild(el);
    _banner = el;
  }

  // ── Public API ────────────────────────────────────────────────────────────

  window.showGitBanner = function () {
    _inject();
    if (!_banner) return;

    // Reset any running timer
    clearTimeout(_timer);

    // Show
    _banner.classList.add('visible');

    // Progress bar countdown
    const bar = document.getElementById('git-push-progress');
    if (bar) {
      bar.style.transition = 'none';
      bar.style.transform  = 'scaleX(1)';
      // Force reflow so transition applies
      void bar.offsetWidth;
      bar.style.transition = `transform ${AUTO_MS}ms linear`;
      bar.style.transform  = 'scaleX(0)';
    }

    // Auto-dismiss
    _timer = setTimeout(() => {
      window._gitBannerDismiss();
    }, AUTO_MS);
  };

  window._gitBannerDismiss = function () {
    clearTimeout(_timer);
    if (_banner) _banner.classList.remove('visible');
  };

  window._gitBannerCopy = function () {
    navigator.clipboard.writeText(COMMAND).then(() => {
      const btn = _banner && _banner.querySelector('.gbanner-copy');
      if (!btn) return;
      btn.textContent = '✓ Copied!';
      btn.classList.add('copied');
      setTimeout(() => {
        btn.textContent = 'Copy git command';
        btn.classList.remove('copied');
      }, 2200);
    }).catch(() => {
      // Fallback for browsers without clipboard API (e.g. older Safari)
      const ta = document.createElement('textarea');
      ta.value = COMMAND;
      ta.style.cssText = 'position:fixed;top:-9999px;left:-9999px';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      ta.remove();
      const btn = _banner && _banner.querySelector('.gbanner-copy');
      if (btn) {
        btn.textContent = '✓ Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.textContent = 'Copy git command';
          btn.classList.remove('copied');
        }, 2200);
      }
    });
  };
})();
