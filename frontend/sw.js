/**
 * Mnemosyne service worker.
 *
 * Strategy
 * ─────────
 * Static assets (HTML, CSS, JS, manifest): cache-first after the first load so
 * the app shell works offline.  On install the assets listed in STATIC_ASSETS
 * are pre-cached; subsequent fetches update the cache lazily.
 *
 * API requests (/parse, /review, /lesson/*, etc.): not intercepted here.
 * Network errors on POST /review are handled in the JS layer (offline.js)
 * which queues the review in IndexedDB and replays it on reconnection.
 *
 * Cache versioning
 * ────────────────
 * Bump CACHE_VERSION when static assets change significantly so users get a
 * fresh cache after the service worker updates.  Old caches are deleted during
 * the activate event.
 */

const CACHE_VERSION   = 'v9.16';
console.log(`Service worker cache version: ${CACHE_VERSION}`);
const CACHE_NAME      = `mnemosyne-static-${CACHE_VERSION}`;

const STATIC_ASSETS = [
  '/',
  '/manifest.json',
  '/css/global.css',
  '/css/layout.css',
  '/css/components.css',
  '/js/main.js',
  '/js/layout.js',
  '/js/auth.js',
  '/js/i18n.js',
  '/js/offline.js',
  '/js/playback.js',
  '/js/types.js',
  '/components/mnemosyne-modal.js',
  '/components/mnemosyne-pill.js',
  '/components/mnemosyne-filter-bar.js',
  '/components/mnemosyne-text-panel.js',
  '/components/mnemosyne-annotation-card.js',
  '/components/mnemosyne-top-nav.js',
  '/components/mnemosyne-detail-pane.js',
  '/components/mnemosyne-player.js',
  '/components/mnemosyne-now-playing-bar.js',
];

// ── Install ───────────────────────────────────────────────────────────────────

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// ── Activate ──────────────────────────────────────────────────────────────────

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(
        keys
          .filter(k => k !== CACHE_NAME)
          .map(k => caches.delete(k))
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch ─────────────────────────────────────────────────────────────────────

self.addEventListener('fetch', event => {
  // Only intercept GET requests (POSTs to the API must go to the network).
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  // Only serve cached responses for same-origin requests.
  if (url.origin !== self.location.origin) return;

  const path = url.pathname;

  // Only cache static asset paths; let all API paths fall through to the
  // network so stale data is never served from cache for JSON responses.
  const isStaticAsset =
    path === '/'                      ||
    path === '/privacy.html'          ||
    path === '/manifest.json'         ||
    path === '/sw.js'                 ||
    path.startsWith('/css/')          ||
    path.startsWith('/js/')           ||
    path.startsWith('/components/');

  if (!isStaticAsset) return;

  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;

      // Not in cache yet — fetch from network and store for next time.
      return fetch(event.request).then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      });
    })
  );
});
