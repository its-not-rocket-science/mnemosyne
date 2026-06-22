/**
 * router.test.mjs — tests for js/router.js, the Session 3 hash router.
 *
 * router.js touches `window.location` and `window.addEventListener` at
 * module load time, so a minimal window/location shim is installed before
 * the dynamic import. This mirrors how the module is actually used (loaded
 * once per page), while keeping the test self-contained under node --test.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

// ── Minimal window/location shim ────────────────────────────────────────────

class FakeLocation {
  #hash = ''
  get hash() { return this.#hash }
  set hash(value) {
    const normalized = value.startsWith('#') ? value : `#${value}`
    if (normalized === this.#hash) return
    this.#hash = normalized
    for (const fn of this._listeners) fn()
  }
  _listeners = []
}

const fakeLocation = new FakeLocation()
const hashChangeListeners = []

globalThis.window = globalThis.window ?? globalThis
globalThis.window.location = fakeLocation
globalThis.window.addEventListener = (type, fn) => {
  if (type === 'hashchange') {
    hashChangeListeners.push(fn)
    fakeLocation._listeners.push(fn)
  }
}
globalThis.window.removeEventListener = () => {}
// router.js reads window.location.hash directly via the global `window`
// reference — since we aliased globalThis.window to globalThis itself,
// `window.location` resolves through globalThis too.
globalThis.location = fakeLocation

const router = await import('../js/router.js')
const { parseRoute, navigate, onRoute } = router

// ── parseRoute ───────────────────────────────────────────────────────────────

describe('router — parseRoute', () => {
  it('parses the home route', () => {
    assert.deepEqual(parseRoute(''), { path: 'home', params: {} })
    assert.deepEqual(parseRoute('#/'), { path: 'home', params: {} })
  })

  it('parses #/explore', () => {
    assert.deepEqual(parseRoute('#/explore'), { path: 'explore', params: {} })
  })

  it('parses #/lesson/:id', () => {
    assert.deepEqual(parseRoute('#/lesson/abc-123'), { path: 'lesson', params: { id: 'abc-123' } })
  })

  it('parses #/review', () => {
    assert.deepEqual(parseRoute('#/review'), { path: 'review', params: {} })
  })

  it('parses #/library and #/library/vocab as distinct routes', () => {
    assert.deepEqual(parseRoute('#/library'), { path: 'library', params: {} })
    assert.deepEqual(parseRoute('#/library/vocab'), { path: 'library-vocab', params: {} })
  })

  it('parses #/create/:id', () => {
    assert.deepEqual(parseRoute('#/create/doc-9'), { path: 'create', params: { id: 'doc-9' } })
  })

  it('decodes URI-encoded ids', () => {
    assert.deepEqual(parseRoute('#/lesson/a%20b'), { path: 'lesson', params: { id: 'a b' } })
  })

  it('degrades gracefully on unrecognised hashes (no throw)', () => {
    const route = parseRoute('#/totally-bogus')
    assert.equal(route.path, 'unknown')
    assert.equal(route.raw, '/totally-bogus')
  })
})

// ── navigate + onRoute ─────────────────────────────────────────────────────────

describe('router — navigate / onRoute', () => {
  it('navigate() sets window.location.hash', () => {
    navigate('#/library')
    assert.equal(window.location.hash, '#/library')
  })

  it('navigate() accepts paths without a leading #', () => {
    navigate('/explore')
    assert.equal(window.location.hash, '#/explore')
  })

  it('onRoute() fires immediately with the current route', () => {
    navigate('#/review')
    let received = null
    onRoute((route) => { received = route })
    assert.equal(received.path, 'review')
  })

  it('onRoute() fires again on navigate() to a new hash', () => {
    navigate('#/explore')
    const seen = []
    onRoute((route) => { seen.push(route.path) })
    navigate('#/library')
    assert.ok(seen.includes('explore'), 'immediate fire on registration')
    assert.ok(seen.includes('library'), 'fired again after navigate()')
  })

  it('onRoute() returns an unsubscribe function', () => {
    navigate('#/explore')
    let calls = 0
    const unsub = onRoute(() => { calls += 1 })
    const callsAfterSubscribe = calls
    unsub()
    navigate('#/library')
    assert.equal(calls, callsAfterSubscribe, 'handler must not fire after unsubscribe')
  })

})

// ── Source-level checks ────────────────────────────────────────────────────────

describe('router — source conventions', () => {
  it('does not use the History API (no bundler/server rewrite needed)', async () => {
    const { readSource } = await import('./lib/dom.mjs')
    const src = readSource('js/router.js')
    assert.ok(!src.includes('.pushState('),    'router.js must not call history.pushState()')
    assert.ok(!src.includes('.replaceState('), 'router.js must not call history.replaceState()')
    assert.ok(src.includes('window.location.hash'), 'router.js must use window.location.hash')
  })

  it('exports navigate, onRoute, and parseRoute', async () => {
    const { readSource } = await import('./lib/dom.mjs')
    const src = readSource('js/router.js')
    assert.ok(src.includes('export function navigate'))
    assert.ok(src.includes('export function onRoute'))
    assert.ok(src.includes('export function parseRoute'))
  })
})
