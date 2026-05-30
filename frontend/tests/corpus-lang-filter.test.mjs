/**
 * corpus-lang-filter.test.mjs — structural tests for the corpus browser
 * language filter: API-driven select, per-language counts, pre-selection.
 *
 * Run with: node frontend/tests/corpus-lang-filter.test.mjs
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

// ── index.html: lang select with corpus_lang_all i18n key ────────────────────

const langSelectIdx  = html.indexOf('id="corpus-browser-lang"')
const langSelectBody = html.slice(langSelectIdx, langSelectIdx + 300)
assert.ok(langSelectIdx !== -1, 'index.html must have #corpus-browser-lang select')
assert.ok(
  langSelectBody.includes('data-i18n="corpus_lang_all"'),
  '#corpus-browser-lang default option must use corpus_lang_all i18n key (not choose_language)'
)
console.log('✓ index.html: #corpus-browser-lang uses corpus_lang_all i18n key')

// ── main.js: async _populateCorpusLangSelect ──────────────────────────────────

assert.ok(
  mainJs.includes('async function _populateCorpusLangSelect()'),
  'main.js must define async _populateCorpusLangSelect'
)

const populateFnIdx  = mainJs.indexOf('async function _populateCorpusLangSelect()')
const populateFnBody = mainJs.slice(populateFnIdx, populateFnIdx + 1400)

assert.ok(
  populateFnBody.includes('/corpus/languages'),
  '_populateCorpusLangSelect must fetch /corpus/languages'
)
assert.ok(
  populateFnBody.includes('language') && populateFnBody.includes('count'),
  '_populateCorpusLangSelect must destructure language and count from API response'
)
assert.ok(
  populateFnBody.includes('_makeAllLangsOption'),
  '_populateCorpusLangSelect must use _makeAllLangsOption for the default option'
)
assert.ok(
  populateFnBody.includes('hasPreselect'),
  '_populateCorpusLangSelect must check whether current language is in corpus'
)
assert.ok(
  populateFnBody.includes("languageSelect?.value"),
  '_populateCorpusLangSelect must read current app language for pre-selection'
)
console.log('✓ main.js: _populateCorpusLangSelect fetches API, uses counts, pre-selects app language')

// ── _makeAllLangsOption uses corpus_lang_all ──────────────────────────────────

assert.ok(mainJs.includes('function _makeAllLangsOption()'), 'main.js must define _makeAllLangsOption')

const makeOptIdx  = mainJs.indexOf('function _makeAllLangsOption()')
const makeOptBody = mainJs.slice(makeOptIdx, makeOptIdx + 150)
assert.ok(
  makeOptBody.includes("corpus_lang_all"),
  '_makeAllLangsOption must use t("corpus_lang_all")'
)
console.log('✓ main.js: _makeAllLangsOption uses corpus_lang_all i18n key')

// ── fallback to static list on fetch error ────────────────────────────────────

assert.ok(
  populateFnBody.includes('languageCapabilities'),
  '_populateCorpusLangSelect fallback must use languageCapabilities'
)
console.log('✓ main.js: static fallback uses languageCapabilities on fetch error')

// ── openCorpusBrowserBtn awaits populate before loading ───────────────────────

const openBtnIdx  = mainJs.indexOf("openCorpusBrowserBtn?.addEventListener('click'")
const openBtnBody = mainJs.slice(openBtnIdx, openBtnIdx + 250)
assert.ok(
  openBtnBody.includes('await _populateCorpusLangSelect()'),
  'open button handler must await _populateCorpusLangSelect before _loadCorpus'
)
assert.ok(
  openBtnBody.includes('await _loadCorpus()'),
  'open button handler must await _loadCorpus'
)
// populate must come before load in the handler
const populatePos = openBtnBody.indexOf('await _populateCorpusLangSelect()')
const loadPos     = openBtnBody.indexOf('await _loadCorpus()')
assert.ok(populatePos < loadPos, 'populate must run before loadCorpus in click handler')
console.log('✓ main.js: open handler awaits populate (with pre-selection) before load')

// ── i18n: corpus_lang_all in all 11 language blocks ──────────────────────────

assert.ok(i18n.includes('corpus_lang_all'), 'i18n.js must define corpus_lang_all')
const matchCount = (i18n.match(/corpus_lang_all/g) ?? []).length
assert.ok(
  matchCount >= 11,
  `corpus_lang_all must appear in all 11 language blocks (found ${matchCount})`
)
console.log(`✓ i18n: corpus_lang_all defined in all 11 language blocks`)

console.log('\nAll corpus-lang-filter tests passed.')
