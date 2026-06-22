/**
 * sentence-translate.test.mjs — structural tests for per-sentence translation toggle.
 *
 * Run with: node frontend/tests/sentence-translate.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

// Sentence translation lives in js/modes/lesson.js after the main.js split
// (Session 1 of the frontend refactor).
const mainJs = readFileSync(path.join(ROOT, 'js', 'modes', 'lesson.js'), 'utf8')
const i18n   = ['core','annotations','lesson','library','review'].map(f => readFileSync(path.join(ROOT, 'js', 'i18n', `${f}.js`), 'utf8')).join('\n')
const css    = readFileSync(path.join(ROOT, 'css', 'components.css'), 'utf8')

// ── State variables ───────────────────────────────────────────────────────────

assert.ok(mainJs.includes('_sentenceTranslations'), 'main.js must declare _sentenceTranslations')
console.log('✓ main.js: _sentenceTranslations cache declared')

// _loadSource lives in js/modes/library.js; _sentenceTranslations is private
// to lesson.js, so library.js clears it via the exported clearSentenceTranslations().
const libraryJs       = readFileSync(path.join(ROOT, 'js', 'modes', 'library.js'), 'utf8')
const loadSourceIdx  = libraryJs.indexOf('async function _loadSource(')
const loadSourceBody = libraryJs.slice(loadSourceIdx, loadSourceIdx + 600)
assert.ok(
  loadSourceBody.includes('clearSentenceTranslations()'),
  '_loadSource must clear sentence translations via clearSentenceTranslations()'
)
console.log('✓ library.js: _loadSource clears translation cache via lesson.js export')

// ── renderResults: translate button + reveal span ─────────────────────────────

const renderIdx  = mainJs.indexOf('function renderResults(')
const renderBody = mainJs.slice(renderIdx, renderIdx + 4000)
assert.ok(renderBody.includes('reader-sentence__translate-btn'),  'renderResults must add translate-btn')
assert.ok(renderBody.includes('reader-sentence__translation'),    'renderResults must add translation span')
assert.ok(renderBody.includes('aria-expanded'),                   'translate btn must have aria-expanded')
assert.ok(renderBody.includes('sentence_translate'),              'translate btn must use i18n key')
assert.ok(
  renderBody.includes("language !== currentUiLang()"),
  'translate btn must be skipped when source == UI language'
)
console.log('✓ main.js: renderResults adds translate button and reveal span with aria-expanded')

// ── fetchSentenceTranslation ──────────────────────────────────────────────────
// Exported (no leading underscore) since renderResults' click handler now
// calls it across the module boundary within lesson.js.

assert.ok(mainJs.includes('export async function fetchSentenceTranslation('), 'lesson.js must define fetchSentenceTranslation')
const fetchIdx  = mainJs.indexOf('export async function fetchSentenceTranslation(')
const fetchBody = mainJs.slice(fetchIdx, fetchIdx + 1000)
assert.ok(fetchBody.includes('_sentenceTranslations.get('),  'must check cache before fetching')
assert.ok(fetchBody.includes('/translate'),                  'must call /translate endpoint')
assert.ok(fetchBody.includes('source_language'),             'must send source_language')
assert.ok(fetchBody.includes('target_language'),             'must send target_language')
assert.ok(fetchBody.includes('currentUiLang()'),             'target_language must use currentUiLang()')
assert.ok(fetchBody.includes('_sentenceTranslations.set('),  'must cache result')
console.log('✓ main.js: _fetchSentenceTranslation checks cache, fetches /translate, caches result')

// ── _renderSentenceTranslation ────────────────────────────────────────────────

assert.ok(mainJs.includes('function _renderSentenceTranslation('), 'main.js must define _renderSentenceTranslation')
const renderTransIdx  = mainJs.indexOf('function _renderSentenceTranslation(')
const renderTransBody = mainJs.slice(renderTransIdx, renderTransIdx + 400)
assert.ok(renderTransBody.includes('sentence_translation_na'), 'error state uses i18n key')
assert.ok(renderTransBody.includes('data-state'),              'error state sets data-state attribute')
assert.ok(renderTransBody.includes('translation-attr'),        'attribution element rendered')
console.log('✓ main.js: _renderSentenceTranslation handles success, error, and attribution')

// ── i18n keys ─────────────────────────────────────────────────────────────────

const KEYS = ['sentence_translate', 'sentence_translating', 'sentence_translation_na']
for (const key of KEYS) {
  assert.ok(i18n.includes(key), `i18n.js must define key: ${key}`)
}
console.log('✓ i18n: sentence_translate keys defined')

assert.ok(
  (i18n.match(/sentence_translate:/g) ?? []).length >= 11,
  'sentence_translate must appear in all 11 language blocks'
)
console.log('✓ i18n: sentence_translate present across all 11 language blocks')

// ── CSS ───────────────────────────────────────────────────────────────────────

assert.ok(css.includes('.reader-sentence__translate-btn'),    'CSS must define translate-btn')
assert.ok(css.includes('.reader-sentence__translation'),      'CSS must define translation reveal')
assert.ok(css.includes('.reader-sentence__translation-attr'), 'CSS must define attribution span')
assert.ok(css.includes('opacity: 0'),                        'translate btn hidden by default (opacity:0)')
assert.ok(css.includes('prefers-reduced-motion'),            'CSS must respect prefers-reduced-motion')
assert.ok(css.includes('forced-colors'),                     'CSS must include forced-colors support')
console.log('✓ CSS: translate button and reveal defined with a11y variants')

console.log('\nAll sentence-translate tests passed.')
