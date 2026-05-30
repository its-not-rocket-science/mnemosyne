/**
 * corpus-sort.test.mjs — structural tests for corpus browser reading-progress
 * sort/filter: select element, _corpusParams wiring, i18n keys.
 *
 * Run with: node frontend/tests/corpus-sort.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

const mainJs = readFileSync(path.join(ROOT, 'js', 'main.js'), 'utf8')
const html   = readFileSync(path.join(ROOT, 'index.html'), 'utf8')
const i18n   = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')

// ── index.html: #corpus-browser-sort select ───────────────────────────────────

assert.ok(html.includes('id="corpus-browser-sort"'), 'index.html must have #corpus-browser-sort select')

const sortSelectIdx  = html.indexOf('id="corpus-browser-sort"')
const sortSelectBody = html.slice(sortSelectIdx, sortSelectIdx + 600)

assert.ok(sortSelectBody.includes('value="recent"'),      '#corpus-browser-sort must have recent option')
assert.ok(sortSelectBody.includes('value="in_progress"'), '#corpus-browser-sort must have in_progress option')
assert.ok(sortSelectBody.includes('value="not_started"'), '#corpus-browser-sort must have not_started option')
assert.ok(sortSelectBody.includes('value="complete"'),    '#corpus-browser-sort must have complete option')
assert.ok(sortSelectBody.includes('corpus_sort_recent'),       'recent option must use corpus_sort_recent i18n key')
assert.ok(sortSelectBody.includes('corpus_sort_in_progress'),  'in_progress option must use corpus_sort_in_progress key')
assert.ok(sortSelectBody.includes('corpus_sort_not_started'),  'not_started option must use corpus_sort_not_started key')
assert.ok(sortSelectBody.includes('corpus_sort_complete'),     'complete option must use corpus_sort_complete key')
console.log('✓ index.html: #corpus-browser-sort with all 4 option values and i18n keys')

// ── main.js: ref declared ─────────────────────────────────────────────────────

assert.ok(mainJs.includes('corpusBrowserSort'), 'main.js must declare corpusBrowserSort')
assert.ok(
  mainJs.includes("querySelector('#corpus-browser-sort')"),
  "main.js must query '#corpus-browser-sort'"
)
console.log('✓ main.js: corpusBrowserSort ref declared')

// ── _corpusParams includes sort ───────────────────────────────────────────────

const paramsIdx  = mainJs.indexOf('function _corpusParams()')
const paramsBody = mainJs.slice(paramsIdx, paramsIdx + 400)

assert.ok(paramsBody.includes('corpusBrowserSort'), '_corpusParams must read corpusBrowserSort')
assert.ok(paramsBody.includes("p.set('sort'"),      "_corpusParams must set 'sort' param")
console.log('✓ main.js: _corpusParams reads sort and sends it to API')

// ── change event wired ────────────────────────────────────────────────────────

assert.ok(
  mainJs.includes("corpusBrowserSort?.addEventListener('change'"),
  'main.js must wire change event on corpusBrowserSort'
)
console.log('✓ main.js: corpusBrowserSort change event wired to _loadCorpus')

// ── i18n: sort keys in all 11 language blocks ─────────────────────────────────

for (const key of ['corpus_sort_recent', 'corpus_sort_in_progress', 'corpus_sort_not_started', 'corpus_sort_complete']) {
  const count = (i18n.match(new RegExp(key, 'g')) ?? []).length
  assert.ok(count >= 11, `${key} must appear in all 11 language blocks (found ${count})`)
}
console.log('✓ i18n: all 4 corpus_sort_* keys in all 11 language blocks')

console.log('\nAll corpus-sort tests passed.')
