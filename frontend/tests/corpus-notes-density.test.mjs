/**
 * corpus-notes-density.test.mjs — structural tests for corpus notes, vocab
 * density heatmap, and duplicate-URL detection.
 *
 * Run with: node frontend/tests/corpus-notes-density.test.mjs
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT      = path.resolve(__dirname, '..')

// Corpus browser lives entirely in js/modes/library.js after the main.js
// split (Session 1 of the frontend refactor).
const mainJs = readFileSync(path.join(ROOT, 'js', 'modes', 'library.js'), 'utf8')
const i18n   = readFileSync(path.join(ROOT, 'js', 'i18n.js'), 'utf8')

// ── _saveCorpusNote / _deleteCorpusNote ───────────────────────────────────────

assert.ok(mainJs.includes('function _saveCorpusNote('),  'main.js must define _saveCorpusNote')
assert.ok(mainJs.includes('function _deleteCorpusNote('), 'main.js must define _deleteCorpusNote')

const saveIdx  = mainJs.indexOf('function _saveCorpusNote(')
const saveBody = mainJs.slice(saveIdx, saveIdx + 300)
assert.ok(saveBody.includes("method: 'PUT'"),       '_saveCorpusNote must use PUT')
assert.ok(saveBody.includes('/note'),               '_saveCorpusNote must hit /note endpoint')

const delIdx  = mainJs.indexOf('function _deleteCorpusNote(')
const delBody = mainJs.slice(delIdx, delIdx + 200)
assert.ok(delBody.includes("method: 'DELETE'"),     '_deleteCorpusNote must use DELETE')
console.log('✓ main.js: _saveCorpusNote and _deleteCorpusNote defined')

// ── _buildCorpusItem — notes ──────────────────────────────────────────────────

const buildIdx  = mainJs.indexOf('function _buildCorpusItem(')
const buildBody = mainJs.slice(buildIdx, buildIdx + 12000)

assert.ok(buildBody.includes('corpus-browser-list__note-toggle'),  '_buildCorpusItem must create note toggle')
assert.ok(buildBody.includes('corpus-browser-list__note-area'),    '_buildCorpusItem must create note area')
assert.ok(buildBody.includes('corpus-browser-list__note-textarea'), '_buildCorpusItem must create note textarea')
assert.ok(buildBody.includes('corpus_note_add'),                   '_buildCorpusItem must use corpus_note_add i18n key')
assert.ok(buildBody.includes('corpus_note_placeholder'),           '_buildCorpusItem must use corpus_note_placeholder')
assert.ok(buildBody.includes('_saveCorpusNote'),                   '_buildCorpusItem must call _saveCorpusNote')
assert.ok(buildBody.includes('_deleteCorpusNote'),                 '_buildCorpusItem must call _deleteCorpusNote')
console.log('✓ main.js: _buildCorpusItem has note toggle, area, textarea, save/delete wiring')

// ── _buildCorpusItem — vocab density ─────────────────────────────────────────

assert.ok(buildBody.includes('vocab_density'),                     '_buildCorpusItem must read item.vocab_density')
assert.ok(buildBody.includes('corpus-browser-list__density'),      '_buildCorpusItem must create density element')
assert.ok(buildBody.includes('corpus_vocab_density_label'),        '_buildCorpusItem must use corpus_vocab_density_label')
assert.ok(buildBody.includes("vocabLevel"),                        '_buildCorpusItem must set vocabLevel dataset')
console.log('✓ main.js: _buildCorpusItem renders vocab density indicator')

// ── _importCorpusUrl — 409 dedup handling ────────────────────────────────────

const impIdx  = mainJs.indexOf('function _importCorpusUrl(')
const impBody = mainJs.slice(impIdx, impIdx + 1500)
assert.ok(impBody.includes('status === 409'),                      '_importCorpusUrl must handle 409 response')
assert.ok(impBody.includes('corpus_import_url_duplicate'),         '_importCorpusUrl must use corpus_import_url_duplicate key')
console.log('✓ main.js: _importCorpusUrl handles 409 duplicate response')

// ── i18n: all new keys in all 11 blocks ──────────────────────────────────────

const newKeys = [
  'corpus_import_url_duplicate',
  'corpus_note_add',
  'corpus_note_placeholder',
  'corpus_vocab_density_label',
]

for (const key of newKeys) {
  const count = (i18n.match(new RegExp(key, 'g')) ?? []).length
  assert.ok(count >= 11, `${key} must appear in all 11 language blocks (found ${count})`)
}
console.log('✓ i18n: all 4 new keys in all 11 language blocks')

console.log('\nAll corpus-notes-density tests passed.')
