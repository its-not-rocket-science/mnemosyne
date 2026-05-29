/**
 * corpus-browser.test.mjs — structural tests for the corpus text browser.
 *
 * Run with: node frontend/tests/corpus-browser.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const html      = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
const mainJs    = readFileSync(path.join(ROOT, 'js', 'main.js'), 'utf8')
const i18n      = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')
const globalCss = readFileSync(path.join(ROOT, 'css', 'global.css'), 'utf8')

// ── HTML: open button ─────────────────────────────────────────────────────────

assert.ok(
  html.includes('id="open-corpus-browser-btn"'),
  'index.html must include #open-corpus-browser-btn'
)
console.log('✓ HTML: #open-corpus-browser-btn present')

// ── HTML: dialog structure ────────────────────────────────────────────────────

assert.ok(
  html.includes('id="corpus-browser-dialog"'),
  'index.html must include #corpus-browser-dialog'
)
assert.ok(
  html.includes('id="corpus-browser-heading"'),
  'dialog must have #corpus-browser-heading for aria-labelledby'
)
assert.ok(
  html.includes('id="corpus-browser-close-btn"'),
  'dialog must have a close button'
)
assert.ok(
  html.includes('id="corpus-browser-search"'),
  'dialog must have #corpus-browser-search input'
)
assert.ok(
  html.includes('id="corpus-browser-lang"'),
  'dialog must have #corpus-browser-lang language filter'
)
assert.ok(
  html.includes('id="corpus-browser-type"'),
  'dialog must have #corpus-browser-type content-type filter'
)
assert.ok(
  html.includes('id="corpus-browser-list"'),
  'dialog must have #corpus-browser-list'
)
assert.ok(
  html.includes('id="corpus-browser-more-btn"'),
  'dialog must have #corpus-browser-more-btn load-more button'
)
console.log('✓ HTML: corpus browser dialog structure present')

// ── HTML: filter options ──────────────────────────────────────────────────────

assert.ok(
  html.includes('value="pasted_text"') && html.includes('value="uploaded_file"'),
  'type filter must include pasted_text and uploaded_file options'
)
console.log('✓ HTML: content-type filter options present')

// ── i18n keys ─────────────────────────────────────────────────────────────────

const REQUIRED_KEYS = [
  'corpus_browser_btn',
  'corpus_browser_heading',
  'corpus_filter_search_placeholder',
  'corpus_type_all',
  'corpus_type_pasted',
  'corpus_type_file',
  'corpus_empty',
  'corpus_load_more',
  'corpus_open_btn',
  'corpus_char_count',
  'corpus_count',
]
for (const key of REQUIRED_KEYS) {
  assert.ok(i18n.includes(key), `i18n.js must define key: ${key}`)
}
console.log('✓ i18n: all corpus browser keys defined')

// Keys must appear in all 11 language blocks — spot check es and ar
assert.ok(
  (i18n.match(/corpus_browser_btn/g) ?? []).length >= 11,
  'corpus_browser_btn must appear in all 11 language blocks'
)
console.log('✓ i18n: corpus keys present across language blocks')

// ── main.js wiring ────────────────────────────────────────────────────────────

assert.ok(mainJs.includes('corpusBrowserDialog'),   'main.js must declare corpusBrowserDialog')
assert.ok(mainJs.includes('openCorpusBrowserBtn'),  'main.js must declare openCorpusBrowserBtn')
assert.ok(mainJs.includes('corpusBrowserList'),     'main.js must declare corpusBrowserList')
assert.ok(mainJs.includes('_loadCorpus'),           'main.js must define _loadCorpus')
assert.ok(mainJs.includes('_buildCorpusItem'),      'main.js must define _buildCorpusItem')
assert.ok(mainJs.includes('_corpusParams'),         'main.js must define _corpusParams')
assert.ok(mainJs.includes('_populateCorpusLangSelect'), 'main.js must define _populateCorpusLangSelect')
console.log('✓ main.js: corpus browser functions defined')

// ── API endpoint ──────────────────────────────────────────────────────────────

assert.ok(
  mainJs.includes('/corpus?'),
  'main.js must call /corpus endpoint'
)
assert.ok(
  mainJs.includes('content_type'),
  'main.js must pass content_type filter'
)
console.log('✓ main.js: /corpus endpoint called with filters')

// ── Load-more and search debounce ─────────────────────────────────────────────

assert.ok(
  mainJs.includes('_corpusSearchTimer'),
  'main.js must debounce corpus search'
)
assert.ok(
  mainJs.includes("_loadCorpus(true)"),
  'load-more button must call _loadCorpus(true)'
)
console.log('✓ main.js: search debounce and load-more wired')

// ── _loadSource closes corpus dialog ─────────────────────────────────────────

const loadSourceIdx  = mainJs.indexOf('async function _loadSource(')
const loadSourceBody = mainJs.slice(loadSourceIdx, loadSourceIdx + 300)
assert.ok(
  loadSourceBody.includes('corpusBrowserDialog'),
  '_loadSource must close corpusBrowserDialog'
)
console.log('✓ main.js: _loadSource closes corpus browser dialog')

// ── CSS ───────────────────────────────────────────────────────────────────────

const CSS_CLASSES = [
  '.corpus-browser-dialog',
  '.corpus-browser-filters',
  '.corpus-browser-list',
  '.corpus-browser-list__item',
  '.corpus-browser-list__btn',
  '.corpus-browser-list__title',
  '.corpus-browser-list__tag',
  '.corpus-browser-list__open',
  '.corpus-browser-count',
]
for (const cls of CSS_CLASSES) {
  assert.ok(globalCss.includes(cls), `CSS must define ${cls}`)
}
console.log('✓ CSS: all .corpus-browser-* classes defined')

assert.ok(
  globalCss.includes('forced-colors') && globalCss.includes('.corpus-browser'),
  'CSS must include forced-colors support for corpus browser'
)
console.log('✓ CSS: forced-colors support for corpus browser')

console.log('\nAll corpus-browser tests passed.')
