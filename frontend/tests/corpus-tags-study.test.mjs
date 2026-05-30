/**
 * corpus-tags-study.test.mjs — structural tests for corpus tag system
 * and "Study this document" feature.
 *
 * Run with: node frontend/tests/corpus-tags-study.test.mjs
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

// ── index.html: #corpus-browser-tag select ────────────────────────────────────

assert.ok(html.includes('id="corpus-browser-tag"'),   'index.html must have #corpus-browser-tag select')
assert.ok(html.includes('corpus_tag_all'),             '#corpus-browser-tag must have corpus_tag_all option')
assert.ok(html.includes('corpus_tag_filter_aria'),     '#corpus-browser-tag must use corpus_tag_filter_aria')
console.log('✓ index.html: #corpus-browser-tag select with i18n keys')

// ── main.js: refs ─────────────────────────────────────────────────────────────

assert.ok(mainJs.includes('corpusBrowserTag'),                     'main.js must declare corpusBrowserTag ref')
assert.ok(mainJs.includes("querySelector('#corpus-browser-tag')"), 'main.js must query #corpus-browser-tag')
console.log('✓ main.js: corpusBrowserTag ref declared')

// ── main.js: _corpusParams includes tag ──────────────────────────────────────

const paramsIdx  = mainJs.indexOf('function _corpusParams()')
const paramsBody = mainJs.slice(paramsIdx, paramsIdx + 500)

assert.ok(paramsBody.includes('corpusBrowserTag'),  '_corpusParams must read corpusBrowserTag')
assert.ok(paramsBody.includes("p.set('tag'"),       "_corpusParams must set 'tag' param")
console.log('✓ main.js: _corpusParams includes tag filter')

// ── main.js: _buildCorpusItem — tags and study ───────────────────────────────

const buildIdx  = mainJs.indexOf('function _buildCorpusItem(')
const buildBody = mainJs.slice(buildIdx, buildIdx + 9000)

assert.ok(buildBody.includes('corpus-browser-list__tags'),       '_buildCorpusItem must create tags row')
assert.ok(buildBody.includes('corpus-browser-list__tag-chip'),   '_buildCorpusItem must create tag chips')
assert.ok(buildBody.includes('corpus-browser-list__tag-add'),    '_buildCorpusItem must create add-tag button')
assert.ok(buildBody.includes('corpus-browser-list__tag-input'),  '_buildCorpusItem must create tag input')
assert.ok(buildBody.includes('corpus-browser-list__study'),      '_buildCorpusItem must create study button')
assert.ok(buildBody.includes('corpus_tag_add_aria'),             'add-tag button must use i18n aria key')
assert.ok(buildBody.includes('corpus_tag_remove_aria'),          'tag remove must use i18n aria key')
assert.ok(buildBody.includes('corpus_study_btn'),                'study button must use i18n label key')
assert.ok(buildBody.includes('corpus_study_aria'),               'study button must use i18n aria key')
assert.ok(buildBody.includes('_addCorpusTag'),                   '_buildCorpusItem must call _addCorpusTag')
assert.ok(buildBody.includes('_removeCorpusTag'),                '_buildCorpusItem must call _removeCorpusTag')
assert.ok(buildBody.includes('_studyCorpusDocument'),            '_buildCorpusItem must call _studyCorpusDocument')
console.log('✓ main.js: _buildCorpusItem has tags, add/remove, and study button')

// ── main.js: helper functions ─────────────────────────────────────────────────

assert.ok(mainJs.includes('function _addCorpusTag('),       'main.js must define _addCorpusTag')
assert.ok(mainJs.includes('function _removeCorpusTag('),    'main.js must define _removeCorpusTag')
assert.ok(mainJs.includes('function _studyCorpusDocument('),'main.js must define _studyCorpusDocument')
assert.ok(mainJs.includes('function _populateTagFilter('),  'main.js must define _populateTagFilter')

const addIdx  = mainJs.indexOf('function _addCorpusTag(')
const addBody = mainJs.slice(addIdx, addIdx + 300)
assert.ok(addBody.includes("method: 'POST'"),   '_addCorpusTag must use POST')
assert.ok(addBody.includes('/tags'),            '_addCorpusTag must hit /tags endpoint')

const removeIdx  = mainJs.indexOf('function _removeCorpusTag(')
const removeBody = mainJs.slice(removeIdx, removeIdx + 300)
assert.ok(removeBody.includes("method: 'DELETE'"), '_removeCorpusTag must use DELETE')

const studyIdx  = mainJs.indexOf('function _studyCorpusDocument(')
const studyBody = mainJs.slice(studyIdx, studyIdx + 400)
assert.ok(studyBody.includes("method: 'POST'"),        '_studyCorpusDocument must use POST')
assert.ok(studyBody.includes('/study'),                '_studyCorpusDocument must hit /study endpoint')
assert.ok(studyBody.includes('corpus_study_mined'),    '_studyCorpusDocument must show mined count')

const tagFilterIdx  = mainJs.indexOf('function _populateTagFilter(')
const tagFilterBody = mainJs.slice(tagFilterIdx, tagFilterIdx + 400)
assert.ok(tagFilterBody.includes('/corpus/all-tags'), '_populateTagFilter must fetch /corpus/all-tags')
assert.ok(tagFilterBody.includes('corpus_tag_all'),   '_populateTagFilter must use corpus_tag_all i18n key')

console.log('✓ main.js: _addCorpusTag, _removeCorpusTag, _studyCorpusDocument, _populateTagFilter defined')

// ── main.js: tag filter change event ─────────────────────────────────────────

assert.ok(
  mainJs.includes("corpusBrowserTag?.addEventListener('change'"),
  'main.js must wire change event on corpusBrowserTag'
)
console.log('✓ main.js: corpusBrowserTag change event wired')

// ── i18n: all keys in all 11 language blocks ─────────────────────────────────

const newKeys = [
  'corpus_tag_all',
  'corpus_tag_add_aria',
  'corpus_tag_add_placeholder',
  'corpus_tag_remove_aria',
  'corpus_tag_filter_aria',
  'corpus_study_btn',
  'corpus_study_aria',
  'corpus_study_mined',
]

for (const key of newKeys) {
  const count = (i18n.match(new RegExp(key, 'g')) ?? []).length
  assert.ok(count >= 11, `${key} must appear in all 11 language blocks (found ${count})`)
}
console.log('✓ i18n: all 8 new corpus tag/study keys in all 11 language blocks')

console.log('\nAll corpus-tags-study tests passed.')
