/**
 * annotation-search.test.mjs — structural tests for annotation text search.
 *
 * Run with: node frontend/tests/annotation-search.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const html   = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
// Annotation search lives entirely in js/modes/lesson.js after the main.js
// split (Session 1 of the frontend refactor) — it owns "Annotation filters".
const mainJs = readFileSync(path.join(ROOT, 'js', 'modes', 'lesson.js'), 'utf8')
const css    = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')
const i18n   = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')

// ── HTML ──────────────────────────────────────────────────────────────────────

assert.ok(html.includes('id="annotation-search"'), 'index.html must have #annotation-search input')
assert.ok(html.includes('type="search"'), '#annotation-search must be type=search')
assert.ok(html.includes('data-i18n-placeholder="annotation_search_placeholder"'), 'input must have i18n placeholder attr')
assert.ok(html.includes('data-i18n="annotation_search_label"'), 'label must have i18n attr')
console.log('✓ HTML: #annotation-search present with type=search, i18n attrs')

// ── main.js: DOM ref and state ────────────────────────────────────────────────

assert.ok(mainJs.includes('annotationSearch'), 'main.js must declare annotationSearch')
assert.ok(
  mainJs.includes("querySelector('#annotation-search')"),
  'main.js must query #annotation-search'
)
assert.ok(mainJs.includes('activeSearchTerm'), 'main.js must declare activeSearchTerm')
console.log('✓ main.js: annotationSearch ref and activeSearchTerm state declared')

// ── applyAnnotationFilter uses searchAllowed ──────────────────────────────────

const filterIdx  = mainJs.indexOf('function applyAnnotationFilter(')
const filterBody = mainJs.slice(filterIdx, filterIdx + 900)
assert.ok(filterBody.includes('searchAllowed'), 'applyAnnotationFilter must use searchAllowed')
assert.ok(filterBody.includes('activeSearchTerm'), 'applyAnnotationFilter must check activeSearchTerm')
assert.ok(filterBody.includes('dataset.label'), 'search must match against dataset.label')
assert.ok(filterBody.includes('textContent'), 'search must match against textContent')
console.log('✓ main.js: applyAnnotationFilter applies search gate on surface text and label')

// ── input is debounced ────────────────────────────────────────────────────────

assert.ok(mainJs.includes("annotationSearch.addEventListener('input'"), 'input event wired on annotationSearch')
assert.ok(mainJs.includes('_searchDebounce'), 'search input must be debounced')
console.log('✓ main.js: input debounced via _searchDebounce')

// ── clears on new source load ─────────────────────────────────────────────────

assert.ok(
  mainJs.includes("annotationSearch.value = ''"),
  'annotationSearch must be cleared on source load'
)
assert.ok(
  mainJs.includes("setActiveSearchTerm('')"),
  'activeSearchTerm must be reset (via setActiveSearchTerm) on source load'
)
console.log('✓ main.js: search cleared on new source load')

// ── CSS ───────────────────────────────────────────────────────────────────────

assert.ok(css.includes('.annotation-search'), 'components.css must style .annotation-search')
assert.ok(css.includes('.annotation-search-wrap'), 'components.css must style .annotation-search-wrap')
assert.ok(css.includes('.annotation-search:focus-visible'), '.annotation-search must have focus style')
console.log('✓ CSS: annotation search styles defined')

// ── i18n ──────────────────────────────────────────────────────────────────────

assert.ok(i18n.includes('annotation_search_label'), 'i18n must define annotation_search_label')
assert.ok(i18n.includes('annotation_search_placeholder'), 'i18n must define annotation_search_placeholder')
assert.ok(
  (i18n.match(/annotation_search_label/g) ?? []).length >= 11,
  'annotation_search_label must appear in all 11 language blocks'
)
console.log('✓ i18n: annotation_search keys in all 11 language blocks')

console.log('\nAll annotation-search tests passed.')
