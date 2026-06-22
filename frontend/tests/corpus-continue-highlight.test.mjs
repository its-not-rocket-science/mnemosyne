/**
 * corpus-continue-highlight.test.mjs — structural tests for "Continue reading"
 * shortcut and corpus search highlight feature.
 *
 * Run with: node frontend/tests/corpus-continue-highlight.test.mjs
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

// ── _applyQueryHighlight ──────────────────────────────────────────────────────

assert.ok(mainJs.includes('function _applyQueryHighlight('), 'main.js must define _applyQueryHighlight')

const highlightIdx  = mainJs.indexOf('function _applyQueryHighlight(')
const highlightBody = mainJs.slice(highlightIdx, highlightIdx + 400)

assert.ok(highlightBody.includes('corpus-browser-list__match'), '_applyQueryHighlight must create .corpus-browser-list__match mark')
assert.ok(highlightBody.includes("createElement('mark')"),     '_applyQueryHighlight must use <mark> element')
assert.ok(highlightBody.includes('.toLowerCase()'),            '_applyQueryHighlight must do case-insensitive match')
console.log('✓ main.js: _applyQueryHighlight defined with mark element and case-insensitive match')

// ── _buildCorpusItem — highlight and continue ─────────────────────────────────

const buildIdx  = mainJs.indexOf('function _buildCorpusItem(')
const buildBody = mainJs.slice(buildIdx, buildIdx + 10000)

assert.ok(buildBody.includes('_applyQueryHighlight'),  '_buildCorpusItem must call _applyQueryHighlight on title')
assert.ok(buildBody.includes('resumeAt'),              '_buildCorpusItem must compute resumeAt')
assert.ok(buildBody.includes('corpus_continue_btn'),   '_buildCorpusItem must use corpus_continue_btn key for in-progress')
assert.ok(
  buildBody.includes('_loadSource(item.id, item.language, resumeAt)'),
  '_buildCorpusItem open/card clicks must pass resumeAt to _loadSource'
)
console.log('✓ main.js: _buildCorpusItem calls _applyQueryHighlight, uses resumeAt, shows Continue label')

// ── i18n: corpus_continue_btn in all 11 language blocks ──────────────────────

const count = (i18n.match(/corpus_continue_btn/g) ?? []).length
assert.ok(count >= 11, `corpus_continue_btn must appear in all 11 language blocks (found ${count})`)
console.log('✓ i18n: corpus_continue_btn in all 11 language blocks')

console.log('\nAll corpus-continue-highlight tests passed.')
