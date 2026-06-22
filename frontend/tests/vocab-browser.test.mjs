/**
 * vocab-browser.test.mjs — structural tests for the vocabulary browser dialog.
 *
 * Run with: node frontend/tests/vocab-browser.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const html      = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
// Vocabulary browser lives in js/modes/library.js after the main.js split
// (Session 1 of the frontend refactor).
const mainJs    = readFileSync(path.join(ROOT, 'js', 'modes', 'library.js'), 'utf8')
const i18n      = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')
const globalCss = readFileSync(path.join(ROOT, 'css', 'global.css'), 'utf8')

// ── HTML elements ─────────────────────────────────────────────────────────────

assert.ok(html.includes('id="vocab-browser-dialog"'),   'vocab-browser-dialog must exist')
assert.ok(html.includes('id="open-vocab-browser-btn"'), 'open-vocab-browser-btn must exist')
assert.ok(html.includes('id="vocab-browser-search"'),   'vocab-browser-search input must exist')
assert.ok(html.includes('id="vocab-browser-level"'),    'vocab-browser-level select must exist')
assert.ok(html.includes('id="vocab-browser-sort"'),     'vocab-browser-sort select must exist')
assert.ok(html.includes('id="vocab-browser-list"'),     'vocab-browser-list must exist')
assert.ok(html.includes('id="vocab-browser-more-btn"'), 'vocab-browser-more-btn must exist')
assert.ok(html.includes('id="vocab-export-csv-btn"'),   'vocab-export-csv-btn must exist')
assert.ok(html.includes('id="vocab-export-anki-btn"'),  'vocab-export-anki-btn must exist')
assert.ok(html.includes('id="vocab-browser-count"'),    'vocab-browser-count must exist')
assert.ok(html.includes('id="vocab-browser-status"'),   'vocab-browser-status must exist')
console.log('✓ HTML: all vocab-browser elements present')

// list is accessible
const listStart = html.indexOf('id="vocab-browser-list"')
const listEl    = html.slice(listStart, html.indexOf('>', listStart) + 1)
assert.ok(listEl.includes('role="list"'), 'vocab-browser-list must have role=list')
console.log('✓ HTML: vocab-browser-list has role=list')

// status has aria-live
const statusStart = html.indexOf('id="vocab-browser-status"')
const statusEl    = html.slice(statusStart, html.indexOf('>', statusStart) + 1)
assert.ok(statusEl.includes('aria-live="polite"'), 'vocab-browser-status must have aria-live=polite')
console.log('✓ HTML: vocab-browser-status has aria-live=polite')

// sort options include all three values
assert.ok(html.includes('value="mastery"'), 'sort select must have mastery option')
assert.ok(html.includes('value="alpha"'),   'sort select must have alpha option')
assert.ok(html.includes('value="due"'),     'sort select must have due option')
console.log('✓ HTML: sort select has mastery/alpha/due options')

// ── CSS ───────────────────────────────────────────────────────────────────────

assert.ok(globalCss.includes('.vocab-browser-dialog'),          'CSS must define .vocab-browser-dialog')
assert.ok(globalCss.includes('.vocab-browser-filters'),         'CSS must define .vocab-browser-filters')
assert.ok(globalCss.includes('.vocab-browser-list'),            'CSS must define .vocab-browser-list')
assert.ok(globalCss.includes('.vocab-browser-item'),            'CSS must define .vocab-browser-item')
assert.ok(globalCss.includes('.vocab-browser-item__word'),      'CSS must define .vocab-browser-item__word')
assert.ok(globalCss.includes('.vocab-browser-item__gloss'),     'CSS must define .vocab-browser-item__gloss')
assert.ok(globalCss.includes('.vocab-browser-item__cefr'),      'CSS must define .vocab-browser-item__cefr')
assert.ok(globalCss.includes('.vocab-browser-item__mastery'),   'CSS must define .vocab-browser-item__mastery')
assert.ok(globalCss.includes('.vocab-browser-footer'),          'CSS must define .vocab-browser-footer')
console.log('✓ CSS: all vocab-browser classes defined')

// ── i18n keys ─────────────────────────────────────────────────────────────────

const REQUIRED_KEYS = [
  'vocab_browser_btn',
  'vocab_search_placeholder',
  'vocab_sort_mastery',
  'vocab_sort_alpha',
  'vocab_sort_due',
  'vocab_load_more',
  'vocab_count',
  'vocab_empty',
  'vocab_loading',
  'vocab_export_csv',
  'vocab_export_anki',
  'vocab_export_busy',
]
for (const key of REQUIRED_KEYS) {
  assert.ok(i18n.includes(key), `i18n.js must define ${key}`)
}
console.log('✓ i18n: all vocab-browser keys present')

// ── main.js wiring ────────────────────────────────────────────────────────────

assert.ok(mainJs.includes('vocabBrowserDialog'),    'main.js must reference vocabBrowserDialog')
assert.ok(mainJs.includes('vocabBrowserList'),      'main.js must reference vocabBrowserList')
assert.ok(mainJs.includes('vocabBrowserSearch'),    'main.js must reference vocabBrowserSearch')
assert.ok(mainJs.includes('vocabBrowserSort'),      'main.js must reference vocabBrowserSort')
assert.ok(mainJs.includes('vocabBrowserMoreBtn'),   'main.js must reference vocabBrowserMoreBtn')
assert.ok(mainJs.includes('_loadVocab'),            'main.js must define _loadVocab')
assert.ok(mainJs.includes('_vocabParams'),          'main.js must define _vocabParams')
assert.ok(mainJs.includes('/users/me/vocabulary'),  'main.js must call /users/me/vocabulary endpoint')
assert.ok(mainJs.includes('vocabExportCsvBtn'),     'main.js must reference vocabExportCsvBtn')
assert.ok(mainJs.includes('vocabExportAnkiBtn'),    'main.js must reference vocabExportAnkiBtn')
assert.ok(mainJs.includes('_downloadVocabExport'),  'main.js must define _downloadVocabExport')
assert.ok(mainJs.includes('/users/me/vocabulary/export'), 'main.js must call export endpoint')
console.log('✓ main.js: vocab browser functions and references wired')

// open button wired
const openBlock = mainJs.slice(
  mainJs.indexOf("openVocabBrowserBtn?.addEventListener"),
  mainJs.indexOf("openVocabBrowserBtn?.addEventListener") + 200,
)
assert.ok(openBlock.includes('showModal'), 'open button must call showModal on dialog')
assert.ok(openBlock.includes('_loadVocab'), 'open button must call _loadVocab')
console.log('✓ main.js: open button wired to showModal + _loadVocab')

// filters trigger reload
assert.ok(
  mainJs.includes("vocabBrowserLevel?.addEventListener('change', () => _loadVocab(false))"),
  'level filter must trigger _loadVocab reload'
)
assert.ok(
  mainJs.includes("vocabBrowserSort?.addEventListener('change', () => _loadVocab(false))"),
  'sort filter must trigger _loadVocab reload'
)
assert.ok(
  mainJs.includes("vocabBrowserSearch?.addEventListener('input', _scheduleVocabSearch)"),
  'search input must be debounced via _scheduleVocabSearch'
)
console.log('✓ main.js: filter changes trigger reload; search is debounced')

// load more
assert.ok(
  mainJs.includes("vocabBrowserMoreBtn?.addEventListener('click', () => _loadVocab(true))"),
  'load-more button must call _loadVocab(true) to append'
)
console.log('✓ main.js: load-more appends rather than replacing list')

// ── Pagination constants ──────────────────────────────────────────────────────

assert.ok(mainJs.includes('_VOCAB_PAGE_SIZE'), 'main.js must define _VOCAB_PAGE_SIZE')
assert.ok(mainJs.includes('_vocabOffset'),     'main.js must track _vocabOffset')
assert.ok(mainJs.includes('_vocabTotal'),      'main.js must track _vocabTotal')
console.log('✓ main.js: pagination state variables defined')

// ── Export: filters forwarded to export endpoint ──────────────────────────────

const downloadFn = mainJs.slice(
  mainJs.indexOf('async function _downloadVocabExport'),
  mainJs.indexOf('async function _downloadVocabExport') + 1500,
)
assert.ok(downloadFn.includes("format === 'csv'"),   '_downloadVocabExport must branch on csv format')
assert.ok(downloadFn.includes("format === 'anki'"),  '_downloadVocabExport must branch on anki format')
assert.ok(downloadFn.includes('language'),           '_downloadVocabExport must forward language filter')
assert.ok(downloadFn.includes('level'),              '_downloadVocabExport must forward level filter')
assert.ok(downloadFn.includes('createObjectURL'),    '_downloadVocabExport must use object URL for download')
assert.ok(downloadFn.includes('revokeObjectURL'),    '_downloadVocabExport must revoke object URL after download')
assert.ok(downloadFn.includes('content-disposition'), '_downloadVocabExport must parse Content-Disposition filename')
console.log('✓ main.js: _downloadVocabExport forwards filters, handles blob download correctly')

// Export buttons wired
assert.ok(
  mainJs.includes("vocabExportCsvBtn?.addEventListener('click', () => _downloadVocabExport('csv'))"),
  'CSV button must be wired to _downloadVocabExport'
)
assert.ok(
  mainJs.includes("vocabExportAnkiBtn?.addEventListener('click', () => _downloadVocabExport('anki'))"),
  'Anki button must be wired to _downloadVocabExport'
)
console.log('✓ main.js: export buttons wired to correct format')

console.log('\nAll vocab-browser tests passed.')
