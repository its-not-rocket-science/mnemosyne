/**
 * router.js — Hash-based client-side router.
 *
 * Session 3 of the frontend refactor: turns the main application surfaces
 * into navigable, bookmarkable, back-button-friendly routes. Intentionally
 * uses window.location.hash rather than the History API (pushState) — hash
 * routing needs no server rewrite rule, which matters for this no-bundler,
 * statically-served setup (see CLAUDE.md: minimalism, no build step).
 *
 * Supported routes:
 *   #/              → home
 *   #/explore       → Explorer mode (text intake / picker)
 *   #/lesson/:id    → Lesson mode for a specific corpus text
 *   #/review        → Review session
 *   #/library       → Library / corpus browser
 *   #/library/vocab → Vocabulary browser
 *   #/create/:id    → Create / annotate mode (save-lesson flow) for a text
 *
 * Unrecognised hashes resolve to a route object with path `'unknown'` so
 * callers can decide how to degrade (we do not throw — conservative
 * correctness over hard failure for a navigation primitive).
 */

const ROUTES = [
  { path: 'home',         pattern: /^\/?$/ },
  { path: 'explore',      pattern: /^\/explore\/?$/ },
  { path: 'lesson',       pattern: /^\/lesson\/([^/]+)\/?$/,    params: ['id'] },
  { path: 'review',       pattern: /^\/review\/?$/ },
  { path: 'library-vocab', pattern: /^\/library\/vocab\/?$/ },
  { path: 'library',      pattern: /^\/library\/?$/ },
  { path: 'create',       pattern: /^\/create\/([^/]+)\/?$/,    params: ['id'] },
]

const _listeners = new Set()

/**
 * Parse window.location.hash into a route object: { path, params }.
 * Exported mainly for tests; app code should use onRoute() instead of
 * calling this directly so it stays in sync with navigation events.
 */
export function parseRoute(hash = window.location.hash) {
  // Strip leading '#', tolerate both '#/x' and bare '/x'.
  const raw = (hash || '').replace(/^#/, '') || '/'

  for (const route of ROUTES) {
    const match = route.pattern.exec(raw)
    if (!match) continue
    const params = {}
    if (route.params) {
      route.params.forEach((name, i) => { params[name] = decodeURIComponent(match[i + 1]) })
    }
    return { path: route.path, params }
  }

  return { path: 'unknown', params: {}, raw }
}

/**
 * Navigate to a path, e.g. navigate('#/explore') or navigate('#/lesson/42').
 * Accepts paths with or without a leading '#'. Setting window.location.hash
 * pushes a new entry onto the browser's session history automatically —
 * no History API calls needed for back/forward to work.
 */
export function navigate(path) {
  const hash = path.startsWith('#') ? path : `#${path}`
  if (window.location.hash === hash) {
    // Hash unchanged — hashchange won't fire, but callers (e.g. a nav link
    // clicked twice) still expect listeners to run once for the current route.
    _dispatch()
    return
  }
  window.location.hash = hash
}

/**
 * Register a listener called with the current route object on every
 * navigation (hashchange) and once immediately with the current route.
 * Returns an unsubscribe function.
 */
export function onRoute(handler) {
  _listeners.add(handler)
  // Fire immediately so late-registering coordinators see the initial route
  // without waiting for the next hashchange.
  handler(parseRoute())
  return () => _listeners.delete(handler)
}

function _dispatch() {
  const route = parseRoute()
  for (const handler of _listeners) {
    try { handler(route) } catch (err) { console.error('router: route handler failed', err) }
  }
}

window.addEventListener('hashchange', _dispatch)
