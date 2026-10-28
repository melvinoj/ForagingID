// Large / Grid / List view switch — the one copy (Melvin, 28 Oct 2026),
// shared by species.html and recipes.html. It owns the views, the remembered
// view (one localStorage key per page, passed in), the toggle buttons, the
// scroll anchor that keeps the reader's place across a switch, and the list
// views' safety sort order. Each page renders its own items.
(function () {
  const VIEWS = ['large', 'grid', 'list'];
  const TIPS = { large: ['Large — big photo cards', 'Large view'],
                 grid:  ['Grid — compact cards', 'Grid view'],
                 list:  ['List — sortable rows', 'List view'] };
  const ICONS = {
    large: '<rect x="1" y="1" width="6" height="6" rx="1"/><rect x="9" y="1" width="6" height="6" rx="1"/><rect x="1" y="9" width="6" height="6" rx="1"/><rect x="9" y="9" width="6" height="6" rx="1"/>',
    grid:  '<rect x="1" y="1" width="4" height="4" rx=".6"/><rect x="6" y="1" width="4" height="4" rx=".6"/><rect x="11" y="1" width="4" height="4" rx=".6"/><rect x="1" y="6" width="4" height="4" rx=".6"/><rect x="6" y="6" width="4" height="4" rx=".6"/><rect x="11" y="6" width="4" height="4" rx=".6"/><rect x="1" y="11" width="4" height="4" rx=".6"/><rect x="6" y="11" width="4" height="4" rx=".6"/><rect x="11" y="11" width="4" height="4" rx=".6"/>',
    list:  '<rect x="1" y="2" width="3" height="3" rx=".6"/><rect x="6" y="2.75" width="9" height="1.5" rx=".5"/><rect x="1" y="6.5" width="3" height="3" rx=".6"/><rect x="6" y="7.25" width="9" height="1.5" rx=".5"/><rect x="1" y="11" width="3" height="3" rx=".6"/><rect x="6" y="11.75" width="9" height="1.5" rx=".5"/>',
  };

  // The remembered view for this page's key; `dflt` when unset, unknown or
  // storage is blocked.
  function stored(key, dflt) {
    try { const v = localStorage.getItem(key); return VIEWS.includes(v) ? v : dflt; }
    catch (_) { return dflt; }
  }
  function remember(key, view) {
    try { localStorage.setItem(key, view); } catch (_) {}
  }

  // The three toggle buttons. `handler` is the page's global function name
  // (e.g. 'setSpeciesView'); `btnClass` the page's button class.
  function toggleHtml(btnClass, handler) {
    return VIEWS.map(v => `
      <button type="button" class="${btnClass}" data-view="${v}" onclick="${handler}('${v}')" title="${TIPS[v][0]}" aria-label="${TIPS[v][1]}">
        <svg viewBox="0 0 16 16" aria-hidden="true">${ICONS[v]}</svg>
      </button>`).join('');
  }

  function sync(btnSelector, view) {
    document.querySelectorAll(btnSelector).forEach(b => {
      const on = b.dataset.view === view;
      b.classList.toggle('active', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  // Scroll anchor: the first item still on screen and its offset from the top
  // of the window, so a view switch keeps the reader's place where possible
  // (at the top of the page nothing moves). Items carry data-name.
  function firstVisible(itemSelector) {
    if (window.scrollY <= 0) return null;
    for (const el of document.querySelectorAll(itemSelector)) {
      const top = el.getBoundingClientRect().top;
      if (el.getBoundingClientRect().bottom > 60) return { name: el.dataset.name, top };
    }
    return null;
  }
  function scrollTo(anchor, itemSelector) {
    if (!anchor) return;
    const el = [...document.querySelectorAll(itemSelector)].find(e => e.dataset.name === anchor.name);
    if (el) window.scrollBy(0, el.getBoundingClientRect().top - anchor.top);
  }

  // List sort order for the safety column: deadly, toxic, unknown, caution,
  // edible, not edible — read from the served decision (ordering only).
  const SAFETY_ORDER = { deadly: 0, toxic: 1, unknown: 2, caution: 3 };
  function safetyRank(safety) {
    const d = SafetyGate.decision(safety);
    if (d.level in SAFETY_ORDER) return SAFETY_ORDER[d.level];
    return d.verdict === 'edible' ? 4 : 5;
  }

  window.LmViewSwitch = { VIEWS, stored, remember, toggleHtml, sync, firstVisible, scrollTo, safetyRank };
})();
