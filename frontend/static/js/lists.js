/**
 * lists.js — shared "current species list" state for the /lists workflow.
 *
 * Backed by localStorage (key: foragingid_current_list) so a selection survives
 * the select-mode reach-back flow (lists ↔ map ↔ species). Cleared only by an
 * explicit Clear action — never automatically.
 *
 * Shape:
 *   {
 *     species:    ["Scientific name", ...],   // ordered selection
 *     photos:     { "Scientific name": "thumb-file.jpg" },  // chosen PDF photo
 *     modes:      ["field", "workshop"],       // multi-select print modes (min 1)
 *     mode:       "field" | "workshop",        // derived: highest-priority active mode (read-only)
 *     showPhotos: true                          // global photo visibility
 *   }
 */
(function (global) {
  const KEY = 'foragingid_current_list';
  const VALID_MODES = ['field', 'workshop', 'workshops'];
  // Priority for deriving .mode and choosing layout template
  const MODE_PRIORITY = { workshops: 2, workshop: 1, field: 0 };

  function _default() {
    return { species: [], photos: {}, modes: ['field'], showPhotos: true };
  }

  function load() {
    let o = null;
    try {
      const raw = localStorage.getItem(KEY);
      if (raw) o = JSON.parse(raw);
    } catch (_) { /* fall through to default */ }
    if (!o || typeof o !== 'object') o = _default();
    if (!Array.isArray(o.species)) o.species = [];
    if (!o.photos || typeof o.photos !== 'object') o.photos = {};

    // Migrate from legacy single-string mode to modes array
    if (!Array.isArray(o.modes)) {
      const legacy = o.mode;
      o.modes = (legacy && VALID_MODES.includes(legacy)) ? [legacy] : ['field'];
    }
    // Validate: keep only known values, ensure at least one
    o.modes = o.modes.filter(m => VALID_MODES.includes(m));
    if (!o.modes.length) o.modes = ['field'];

    // Derive .mode (highest-priority selected mode) for backward-compat consumers
    o.mode = o.modes.reduce((best, m) =>
      (MODE_PRIORITY[m] ?? 0) > (MODE_PRIORITY[best] ?? 0) ? m : best,
    o.modes[0]);

    if (typeof o.showPhotos !== 'boolean') o.showPhotos = true;
    return o;
  }

  function save(o) {
    try { localStorage.setItem(KEY, JSON.stringify(o)); } catch (_) {}
    return o;
  }

  function has(name)   { return load().species.includes(name); }
  function count()     { return load().species.length; }
  function species()   { return load().species.slice(); }

  function add(name) {
    const o = load();
    if (name && !o.species.includes(name)) o.species.push(name);
    return save(o);
  }

  function remove(name) {
    const o = load();
    const i = o.species.indexOf(name);
    if (i >= 0) { o.species.splice(i, 1); delete o.photos[name]; }
    return save(o);
  }

  function toggle(name) {
    return has(name) ? remove(name) : add(name);
  }

  function setPhoto(name, file) {
    const o = load();
    if (file) o.photos[name] = file; else delete o.photos[name];
    return save(o);
  }

  function getPhoto(name) { return load().photos[name] || null; }

  function setPref(key, val) {
    const o = load();
    o[key] = val;
    return save(o);
  }

  function clear() {
    try { localStorage.removeItem(KEY); } catch (_) {}
  }

  global.ForagingList = {
    KEY, load, save, has, count, species,
    add, remove, toggle, setPhoto, getPhoto, setPref, clear,
  };
})(window);
