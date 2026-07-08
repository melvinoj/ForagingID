// ForagingID service worker — Phase 10a (Session C).
//
// Caching strategy:
//   STATIC_CACHE   — app shell (JS/CSS/icons/manifest), network-first with cache fallback
//   RUNTIME_CACHE  — same-origin API + navigations, network-first with cache fallback
//   TILE_CACHE     — OSM/ESRI/OpenTopoMap tiles, cache-on-use, bulk 30-day expiry
//   SPECIES_CACHE  — /api/species/* GET responses, cache-first with 7-day per-entry TTL
//                    (except /api/species/taxonomy-tree, whose shape isn't stable enough
//                    for a long-lived cache — routed through RUNTIME_CACHE instead)
//
// Tile caching is cache-on-request only. No bounding boxes, no pre-fetch.
// Tiles load naturally as the user browses the map and are stored for offline use.
//
// Writes (POST / PATCH / DELETE) are never intercepted — they always go to the network.

const CACHE_VERSION  = 'foragingid-v7';   // bump → old STATIC/RUNTIME caches evicted on activate
const STATIC_CACHE   = CACHE_VERSION + '-static';
const RUNTIME_CACHE  = CACHE_VERSION + '-runtime';
// TILE_CACHE and SPECIES_CACHE are deliberately version-independent. Both
// already self-evict on their own TTL (tiles: 30-day bulk, species: 7-day
// per-entry), so they don't need version-driven clearing — and if they were
// suffixed with CACHE_VERSION, bumping it to flush stale JS/HTML would also
// rename them, and the activate cleanup below would then delete the old
// name, wiping every offline map tile on that one deploy. Fixed names avoid that.
const TILE_CACHE     = 'foragingid-tiles';
const SPECIES_CACHE  = 'foragingid-species';

const TILE_TTL_MS    = 30 * 24 * 60 * 60 * 1000;   // 30 days — bulk cache expiry
const SPECIES_TTL_MS =  7 * 24 * 60 * 60 * 1000;   // 7 days  — per-entry TTL

// Tile origins to intercept (cache-on-use)
const TILE_ORIGINS = [
  'tile.openstreetmap.org',
  'server.arcgisonline.com',
  'tile.opentopomap.org',
];

const APP_SHELL = [
  '/',
  '/static/manifest.json',
  '/static/js/pwa.js',
  '/static/js/guest-mode.js',
  '/static/js/offline.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  '/static/icons/dandelion-icon.svg',
];

// ---------------------------------------------------------------------------
// Route classifiers
// ---------------------------------------------------------------------------

function isTile(url) {
  return TILE_ORIGINS.some(h => url.hostname === h || url.hostname.endsWith('.' + h));
}

function isSpeciesGet(url) {
  // Same-origin /api/species/* reads. Non-GET requests are already excluded
  // by the early-return in the fetch handler, so this is safe to apply broadly.
  // Exception: /api/species/taxonomy-tree is excluded on purpose. Per-species
  // profile reads rarely change shape, which is what makes a 7-day cache-first
  // policy safe for them; taxonomy-tree's response shape has changed multiple
  // times as the tree view evolved, and a stale cached body of an older shape
  // crashes the tree renderer (see buildTree()/buildFungiTree() in
  // taxonomy.html). It falls through to isApi() below instead, which is
  // network-first with no long-lived TTL to go stale against.
  return url.origin === self.location.origin && url.pathname.startsWith('/api/species/')
      && url.pathname !== '/api/species/taxonomy-tree';
}

function isApi(url) {
  return url.origin === self.location.origin && url.pathname.startsWith('/api/');
}

function isStatic(url) {
  return url.origin === self.location.origin && url.pathname.startsWith('/static/');
}

// ---------------------------------------------------------------------------
// Cache helpers
// ---------------------------------------------------------------------------

// Store a same-origin Response with a cached-at timestamp header so we can
// check freshness later without external metadata.
async function _putStamped(cache, request, response) {
  const buf  = await response.arrayBuffer();
  const hdrs = new Headers(response.headers);
  hdrs.set('x-sw-cached-at', String(Date.now()));
  await cache.put(request, new Response(buf, {
    status:     response.status,
    statusText: response.statusText,
    headers:    hdrs,
  }));
}

function _isFreshEnough(response, ttlMs) {
  const at = response.headers.get('x-sw-cached-at');
  return at ? (Date.now() - parseInt(at, 10)) < ttlMs : false;
}

// ---------------------------------------------------------------------------
// Fetch strategies
// ---------------------------------------------------------------------------

// Tile: pure cache-first, no per-tile TTL (tile cache is bulk-expired on activate).
// Opaque tile responses (no-cors img requests) are stored as-is — we can't
// inspect their status, so we store unconditionally and accept the rare risk of
// caching a CDN error. Leaflet handles missing / broken tiles gracefully.
async function tileFirst(request) {
  const cache  = await caches.open(TILE_CACHE);
  const cached = await cache.match(request);
  if (cached) return cached;

  const fresh = await fetch(request);  // throws when offline and not cached
  if (fresh && (fresh.ok || fresh.type === 'opaque')) {
    cache.put(request, fresh.clone()).catch(() => {});
  }
  return fresh;
}

// Species API: cache-first, but only if the entry is within the 7-day TTL.
// If stale or absent: network-first. If offline and stale: serve stale (better
// than failing — the species data changes rarely).
async function speciesFirst(request) {
  const cache  = await caches.open(SPECIES_CACHE);
  const cached = await cache.match(request);

  if (cached && _isFreshEnough(cached, SPECIES_TTL_MS)) return cached;
  if (cached) await cache.delete(request);  // evict stale proactively

  try {
    const fresh = await fetch(request);
    if (fresh && fresh.ok) await _putStamped(cache, request, fresh.clone());
    return fresh;
  } catch (err) {
    if (cached) return cached;  // serve stale when offline (better than error)
    throw err;
  }
}

// API (non-species): network-first, fall back to RUNTIME_CACHE.
async function networkFirst(request) {
  try {
    const fresh = await fetch(request);
    if (fresh && fresh.ok) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request, fresh.clone()).catch(() => {});
    }
    return fresh;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw err;
  }
}

// Static assets (JS/CSS/icons/manifest under /static/): network-first, so an
// edited shell file shows up on the next reload instead of waiting on a
// CACHE_VERSION bump + the browser noticing sw.js changed. Falls back to
// STATIC_CACHE when offline — preserves the same offline app-shell behaviour
// cache-first gave, it just no longer serves stale content while online.
async function networkFirstStatic(request) {
  try {
    const fresh = await fetch(request);
    if (fresh && fresh.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, fresh.clone()).catch(() => {});
    }
    return fresh;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw err;
  }
}

// ---------------------------------------------------------------------------
// Tile cache age marker — bulk expiry
// ---------------------------------------------------------------------------

const _TILE_AGE_KEY = 'https://fid.local/_tile-cache-created';

async function _evictStaleTileCache() {
  try {
    const cache  = await caches.open(TILE_CACHE);
    const marker = await cache.match(_TILE_AGE_KEY);
    if (marker) {
      const { t } = await marker.json().catch(() => ({ t: 0 }));
      if ((Date.now() - t) < TILE_TTL_MS) return;  // cache is still fresh
    }
    // No marker, or marker too old — wipe the tile cache and stamp a fresh one.
    await caches.delete(TILE_CACHE);
    const fresh = await caches.open(TILE_CACHE);
    await fresh.put(_TILE_AGE_KEY, new Response(
      JSON.stringify({ t: Date.now() }),
      { headers: { 'Content-Type': 'application/json' } }
    ));
  } catch (e) {
    console.warn('[sw] tile cache eviction failed:', e);
  }
}

// ---------------------------------------------------------------------------
// Lifecycle
// ---------------------------------------------------------------------------

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) =>
      Promise.all(
        APP_SHELL.map((url) =>
          cache.add(url).catch((err) => console.warn('[sw] precache skipped', url, err))
        )
      )
    ).then(() => self.skipWaiting())
  );
});

// One-time migration: TILE_CACHE/SPECIES_CACHE used to be version-suffixed
// (foragingid-vN-tiles / foragingid-vN-species, back when they derived from
// CACHE_VERSION). Copy any existing versioned cache forward into the new
// fixed-name cache before the generic cleanup below deletes it, so shipping
// this fix doesn't itself wipe tiles on the one deploy that ships it.
async function _migrateVersionedCache(oldNamePattern, newCacheName) {
  const keys = await caches.keys();
  const oldKey = keys.find(k => oldNamePattern.test(k) && k !== newCacheName);
  if (!oldKey) return;
  const oldCache = await caches.open(oldKey);
  const newCache = await caches.open(newCacheName);
  const reqs = await oldCache.keys();
  await Promise.all(reqs.map(async (req) => {
    const res = await oldCache.match(req);
    if (res) await newCache.put(req, res);
  }));
}

self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      // Migrate tiles/species forward from their old version-suffixed cache
      // names (pre-decoupling) before the generic cleanup below deletes them.
      await _migrateVersionedCache(/^foragingid-v\d+-tiles$/, TILE_CACHE);
      await _migrateVersionedCache(/^foragingid-v\d+-species$/, SPECIES_CACHE);
      // Remove all caches from previous versions
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter(k => k.startsWith('foragingid-') &&
                       ![STATIC_CACHE, RUNTIME_CACHE, TILE_CACHE, SPECIES_CACHE].includes(k))
          .map(k => caches.delete(k))
      );
      // Evict tile cache if it has aged past 30 days
      await _evictStaleTileCache();
      await self.clients.claim();
    })()
  );
});

// ---------------------------------------------------------------------------
// Fetch routing
// ---------------------------------------------------------------------------

self.addEventListener('fetch', (event) => {
  const { request } = event;

  // Writes always go to the network; never intercept.
  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Cross-origin tile CDNs → tile cache
  if (isTile(url)) {
    event.respondWith(tileFirst(request));
    return;
  }

  // Same-origin species API reads → species cache with 7-day TTL
  if (isSpeciesGet(url)) {
    event.respondWith(speciesFirst(request));
    return;
  }

  // Other same-origin API reads → network-first
  if (isApi(url)) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Same-origin static assets → network-first, cache fallback when offline
  if (isStatic(url)) {
    event.respondWith(networkFirstStatic(request));
    return;
  }

  // Navigations + other same-origin pages → network-first with shell fallback
  if (request.mode === 'navigate' || url.origin === self.location.origin) {
    event.respondWith(
      networkFirst(request).catch(() => caches.match('/'))
    );
  }
  // Cross-origin non-tile requests (e.g. CDN fonts) → unhandled (browser default)
});

// ---------------------------------------------------------------------------
// Message channel — used by settings page / offline.js
// ---------------------------------------------------------------------------

self.addEventListener('message', (event) => {
  if (!event.data) return;

  switch (event.data.type) {

    case 'clear-species-cache':
      caches.delete(SPECIES_CACHE).then(() => {
        if (event.source) event.source.postMessage({ type: 'species-cache-cleared' });
      }).catch(() => {});
      break;

    case 'cache-tiles':
      // Cache a list of tile URLs for offline walk use.
      (async () => {
        const urls   = Array.isArray(event.data.urls) ? event.data.urls : [];
        const cache  = await caches.open(TILE_CACHE);
        let   count  = 0;
        // Fetch in small batches to avoid overwhelming the network.
        const BATCH = 8;
        for (let i = 0; i < urls.length; i += BATCH) {
          const batch = urls.slice(i, i + BATCH);
          await Promise.all(batch.map(async (url) => {
            try {
              if (await cache.match(url)) { count++; return; }  // already cached
              const resp = await fetch(url, { mode: 'cors' });
              if (resp.ok) { await cache.put(url, resp); count++; }
            } catch (_) {}
          }));
        }
        if (event.source) event.source.postMessage({ type: 'cache-tiles-done', count });
      })().catch(() => {});
      break;

    case 'get-cache-status':
      (async () => {
        const tileCache    = await caches.open(TILE_CACHE);
        const speciesCache = await caches.open(SPECIES_CACHE);
        const [tileKeys, speciesKeys] = await Promise.all([
          tileCache.keys(), speciesCache.keys(),
        ]);
        const tileMarker   = await tileCache.match(_TILE_AGE_KEY);
        const tileAge      = tileMarker
          ? (await tileMarker.json().catch(() => null))?.t ?? null
          : null;
        if (event.source) event.source.postMessage({
          type:          'cache-status-result',
          tileCount:     Math.max(0, tileKeys.length - 1),  // exclude age marker
          tileCreatedAt: tileAge,
          speciesCount:  speciesKeys.length,
        });
      })().catch(() => {});
      break;
  }
});
