/**
 * annotation-depth-per-type.test.mjs — structural tests for per-category depth locks.
 *
 * Run with: node frontend/tests/annotation-depth-per-type.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const mainJs  = readFileSync(path.join(ROOT, 'js', 'main.js'), 'utf8')
const barJs   = readFileSync(path.join(ROOT, 'components', 'mnemosyne-filter-bar.js'), 'utf8')

// ── Filter bar: lock state ────────────────────────────────────────────────────

assert.ok(barJs.includes('#locks'), 'filter-bar must declare #locks Set')
assert.ok(barJs.includes('setLocks'), 'filter-bar must define setLocks public method')
assert.ok(barJs.includes('data-locked'), 'filter-bar must set data-locked attribute on locked pills')
assert.ok(barJs.includes('e.shiftKey'), 'filter-bar must handle Shift+click for locking')
console.log('✓ filter-bar: #locks state, setLocks method, Shift+click handler, data-locked attr')

// #dispatch includes locked and lockedTypes
const dispatchIdx  = barJs.indexOf('#dispatch() {')
const dispatchBody = barJs.slice(dispatchIdx, dispatchIdx + 600)
assert.ok(dispatchBody.includes('locked'), '#dispatch must include locked in event detail')
assert.ok(dispatchBody.includes('lockedTypes'), '#dispatch must include lockedTypes in event detail')
console.log('✓ filter-bar: #dispatch emits locked and lockedTypes in filter-change detail')

// #syncPill reflects lock state
const syncPillIdx  = barJs.indexOf('#syncPill(btn) {')
const syncPillBody = barJs.slice(syncPillIdx, syncPillIdx + 300)
assert.ok(syncPillBody.includes('data-locked'), '#syncPill must toggle data-locked attribute')
console.log('✓ filter-bar: #syncPill reflects lock state via data-locked')

// CSS for locked pill
assert.ok(barJs.includes('.pill[data-locked]'), 'CSS must define .pill[data-locked] styles')
assert.ok(barJs.includes('dashed'), '.pill[data-locked] must use dashed indicator')
console.log('✓ filter-bar CSS: .pill[data-locked] with dashed indicator')

// ── main.js: lock state + persistence ────────────────────────────────────────

assert.ok(mainJs.includes('activeLockedTypes'), 'main.js must declare activeLockedTypes')
assert.ok(mainJs.includes('activeLockedCatIds'), 'main.js must declare activeLockedCatIds')
assert.ok(mainJs.includes("'mn-cat-locks'"), 'main.js must use mn-cat-locks localStorage key')
assert.ok(mainJs.includes("'mn-cat-lock-types'"), 'main.js must use mn-cat-lock-types localStorage key')
console.log('✓ main.js: activeLockedTypes/CatIds declared with localStorage keys')

// filter-change handler persists locks
const fcIdx  = mainJs.indexOf("filterBar?.addEventListener('filter-change'")
const fcBody = mainJs.slice(fcIdx, fcIdx + 600)
assert.ok(fcBody.includes('detail.locked'), 'filter-change handler must read detail.locked')
assert.ok(fcBody.includes('detail.lockedTypes'), 'filter-change handler must read detail.lockedTypes')
assert.ok(fcBody.includes("localStorage.setItem('mn-cat-locks'"), 'filter-change handler must persist lock IDs')
console.log('✓ main.js: filter-change handler persists locked categories')

// Locks restored on page load
assert.ok(mainJs.includes('setLocks'), 'main.js must call filterBar.setLocks to restore locks')
console.log('✓ main.js: setLocks called on page load to restore persisted locks')

// ── applyAnnotationFilter: new semantics ─────────────────────────────────────

const filterFnIdx  = mainJs.indexOf('function applyAnnotationFilter()')
const filterFnBody = mainJs.slice(filterFnIdx, filterFnIdx + 800)

// Session filter overrides depth (no intersection with depthTypes)
assert.ok(
  filterFnBody.includes('activeFilterTypes !== null'),
  'applyAnnotationFilter must branch on activeFilterTypes !== null'
)
assert.ok(
  filterFnBody.includes('activeFilterTypes.has(type)'),
  'applyAnnotationFilter: session filter must check activeFilterTypes.has(type)'
)
// Locked types bypass depth model
assert.ok(
  filterFnBody.includes('activeLockedTypes.has(type)'),
  'applyAnnotationFilter must check activeLockedTypes.has(type)'
)
assert.ok(
  filterFnBody.match(/depthTypes\.has\(type\).*activeLockedTypes\.has\(type\)|activeLockedTypes\.has\(type\).*depthTypes\.has\(type\)/),
  'applyAnnotationFilter must union depthTypes and activeLockedTypes when no session filter'
)
console.log('✓ applyAnnotationFilter: session filter overrides depth; locks union with depth model')

console.log('\nAll annotation-depth-per-type tests passed.')
