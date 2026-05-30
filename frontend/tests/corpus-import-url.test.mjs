/**
 * corpus-import-url.test.mjs — structural tests for "Import from URL" feature.
 *
 * Run with: node frontend/tests/corpus-import-url.test.mjs
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

// ── index.html: import URL panel ──────────────────────────────────────────────

assert.ok(html.includes('id="corpus-import-url-toggle"'), 'index.html must have #corpus-import-url-toggle')
assert.ok(html.includes('id="corpus-import-url-form"'),   'index.html must have #corpus-import-url-form')
assert.ok(html.includes('id="corpus-import-url-input"'),  'index.html must have #corpus-import-url-input')
assert.ok(html.includes('id="corpus-import-url-lang"'),   'index.html must have #corpus-import-url-lang')
assert.ok(html.includes('id="corpus-import-url-submit"'), 'index.html must have #corpus-import-url-submit')
assert.ok(html.includes('id="corpus-import-url-status"'), 'index.html must have #corpus-import-url-status')
assert.ok(html.includes('value="article"'),               'index.html must have article option in type filter')
console.log('✓ index.html: import URL panel elements present')

// ── main.js: refs ─────────────────────────────────────────────────────────────

assert.ok(mainJs.includes('corpusImportToggle'),  'main.js must declare corpusImportToggle ref')
assert.ok(mainJs.includes('corpusImportForm'),    'main.js must declare corpusImportForm ref')
assert.ok(mainJs.includes('corpusImportInput'),   'main.js must declare corpusImportInput ref')
assert.ok(mainJs.includes('corpusImportLang'),    'main.js must declare corpusImportLang ref')
assert.ok(mainJs.includes('corpusImportSubmit'),  'main.js must declare corpusImportSubmit ref')
assert.ok(mainJs.includes('corpusImportStatus'),  'main.js must declare corpusImportStatus ref')
console.log('✓ main.js: corpusImport* refs declared')

// ── main.js: _populateImportLangSelect ────────────────────────────────────────

assert.ok(mainJs.includes('function _populateImportLangSelect('), 'main.js must define _populateImportLangSelect')
const popIdx  = mainJs.indexOf('function _populateImportLangSelect(')
const popBody = mainJs.slice(popIdx, popIdx + 400)
assert.ok(popBody.includes('/languages'),       '_populateImportLangSelect must fetch /languages')
assert.ok(popBody.includes('corpusImportLang'), '_populateImportLangSelect must populate corpusImportLang')
console.log('✓ main.js: _populateImportLangSelect fetches /languages')

// ── main.js: _importCorpusUrl ─────────────────────────────────────────────────

assert.ok(mainJs.includes('function _importCorpusUrl('), 'main.js must define _importCorpusUrl')
const impIdx  = mainJs.indexOf('function _importCorpusUrl(')
const impBody = mainJs.slice(impIdx, impIdx + 1200)
assert.ok(impBody.includes('/corpus/import-url'),         '_importCorpusUrl must POST to /corpus/import-url')
assert.ok(impBody.includes("method: 'POST'"),             '_importCorpusUrl must use POST')
assert.ok(impBody.includes('corpus_import_url_success'),  '_importCorpusUrl must use corpus_import_url_success key')
assert.ok(impBody.includes('corpus_import_url_error'),    '_importCorpusUrl must use corpus_import_url_error key')
assert.ok(impBody.includes('_loadCorpus()'),              '_importCorpusUrl must reload corpus on success')
console.log('✓ main.js: _importCorpusUrl POSTs to /corpus/import-url and handles success/error')

// ── main.js: event wiring ─────────────────────────────────────────────────────

assert.ok(mainJs.includes("corpusImportToggle?.addEventListener('click'"), 'main.js must wire toggle click')
assert.ok(mainJs.includes("corpusImportSubmit?.addEventListener('click'"), 'main.js must wire submit click')
assert.ok(mainJs.includes("corpusImportInput?.addEventListener('keydown'"), 'main.js must wire Enter key')
console.log('✓ main.js: import URL event listeners wired')

// ── i18n: all 7 new keys in all 11 language blocks ───────────────────────────

const newKeys = [
  'corpus_type_article',
  'corpus_import_url_btn',
  'corpus_import_url_placeholder',
  'corpus_import_url_lang_aria',
  'corpus_import_url_submit',
  'corpus_import_url_success',
  'corpus_import_url_error',
]

for (const key of newKeys) {
  const count = (i18n.match(new RegExp(key, 'g')) ?? []).length
  assert.ok(count >= 11, `${key} must appear in all 11 language blocks (found ${count})`)
}
console.log('✓ i18n: all 7 corpus-import-url keys in all 11 language blocks')

console.log('\nAll corpus-import-url tests passed.')
