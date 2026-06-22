/**
 * corpus-polish.test.mjs
 *
 * DOM-aware tests for corpus library polish features:
 *   - saved collections/shelves
 *   - bulk tag actions
 *   - import history panel
 *   - "continue reading" first-class strip
 *   - source/provenance display (JS + CSS)
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { loadDocument, readSource } from './lib/dom.mjs'
import { assertLocaleKeys } from './lib/i18n.mjs'

const document  = loadDocument()
// Corpus browser lives entirely in js/modes/library.js after the main.js
// split (Session 1 of the frontend refactor).
const mainJs    = readSource('js/modes/library.js')
const globalCss = readSource('css/global.css')
const i18n      = readSource('js/i18n.js')

// ── Continue reading strip ────────────────────────────────────────────────────

describe('corpus polish — continue reading', () => {
  it('#corpus-in-progress section exists', () => {
    assert.ok(document.querySelector('#corpus-in-progress'), '#corpus-in-progress must exist')
  })

  it('#corpus-in-progress is hidden by default', () => {
    const el = document.querySelector('#corpus-in-progress')
    assert.ok(el?.hasAttribute('hidden'), 'section must start hidden')
  })

  it('#corpus-in-progress-list exists', () => {
    assert.ok(document.querySelector('#corpus-in-progress-list'), '#corpus-in-progress-list must exist')
  })

  it('CSS defines .corpus-in-progress__card', () => {
    assert.ok(globalCss.includes('.corpus-in-progress__card'))
  })

  it('CSS defines .corpus-in-progress__fill', () => {
    assert.ok(globalCss.includes('.corpus-in-progress__fill'))
  })

  it('JS defines _loadInProgress', () => {
    assert.ok(mainJs.includes('_loadInProgress'))
  })

  it('JS defines _buildInProgressCard', () => {
    assert.ok(mainJs.includes('_buildInProgressCard'))
  })

  it('JS fetches /corpus/in-progress', () => {
    assert.ok(mainJs.includes('/corpus/in-progress'))
  })
})

// ── Collections ───────────────────────────────────────────────────────────────

describe('corpus polish — collections', () => {
  it('#corpus-browser-collection select exists', () => {
    assert.ok(document.querySelector('#corpus-browser-collection'), 'collection filter must exist')
  })

  it('#corpus-browser-collection has an "all" default option', () => {
    const sel = document.querySelector('#corpus-browser-collection')
    const allOpt = sel?.querySelector('option[data-i18n="corpus_collection_all"]')
    assert.ok(allOpt, 'collection filter must have corpus_collection_all default option')
  })

  it('JS defines _loadCollections', () => {
    assert.ok(mainJs.includes('_loadCollections'))
  })

  it('JS defines _createCollection', () => {
    assert.ok(mainJs.includes('_createCollection'))
  })

  it('JS defines _addToCollection', () => {
    assert.ok(mainJs.includes('_addToCollection'))
  })

  it('JS calls /collections endpoint', () => {
    assert.ok(mainJs.includes('/collections'))
  })

  it('JS populates collection select on dialog open', () => {
    assert.ok(mainJs.includes('_loadCollections()'))
  })
})

// ── Bulk tag actions ──────────────────────────────────────────────────────────

describe('corpus polish — bulk tags', () => {
  it('#corpus-bulk-select-btn exists', () => {
    assert.ok(document.querySelector('#corpus-bulk-select-btn'), 'bulk select btn must exist')
  })

  it('#corpus-bulk-bar exists and is hidden by default', () => {
    const bar = document.querySelector('#corpus-bulk-bar')
    assert.ok(bar, '#corpus-bulk-bar must exist')
    assert.ok(bar?.hasAttribute('hidden'), 'bulk bar must start hidden')
  })

  it('#corpus-bulk-tag-input exists', () => {
    assert.ok(document.querySelector('#corpus-bulk-tag-input'))
  })

  it('#corpus-bulk-tag-add-btn exists', () => {
    assert.ok(document.querySelector('#corpus-bulk-tag-add-btn'))
  })

  it('#corpus-bulk-tag-remove-btn exists', () => {
    assert.ok(document.querySelector('#corpus-bulk-tag-remove-btn'))
  })

  it('#corpus-bulk-done-btn exists', () => {
    assert.ok(document.querySelector('#corpus-bulk-done-btn'))
  })

  it('JS defines _enterBulkMode', () => {
    assert.ok(mainJs.includes('_enterBulkMode'))
  })

  it('JS defines _exitBulkMode', () => {
    assert.ok(mainJs.includes('_exitBulkMode'))
  })

  it('JS defines _executeBulkTag', () => {
    assert.ok(mainJs.includes('_executeBulkTag'))
  })

  it('JS POSTs to /corpus/bulk/tags', () => {
    assert.ok(mainJs.includes('/corpus/bulk/tags'))
  })

  it('CSS defines .corpus-bulk-bar', () => {
    assert.ok(globalCss.includes('.corpus-bulk-bar'))
  })
})

// ── Import history ────────────────────────────────────────────────────────────

describe('corpus polish — import history', () => {
  it('#corpus-import-log-toggle exists with aria-expanded=false', () => {
    const btn = document.querySelector('#corpus-import-log-toggle')
    assert.ok(btn, '#corpus-import-log-toggle must exist')
    assert.equal(btn?.getAttribute('aria-expanded'), 'false')
  })

  it('#corpus-import-log-list exists and is hidden by default', () => {
    const list = document.querySelector('#corpus-import-log-list')
    assert.ok(list, '#corpus-import-log-list must exist')
    assert.ok(list?.hasAttribute('hidden'), 'list must start hidden')
  })

  it('JS defines _loadImportLog', () => {
    assert.ok(mainJs.includes('_loadImportLog'))
  })

  it('JS fetches /corpus/import-log', () => {
    assert.ok(mainJs.includes('/corpus/import-log'))
  })

  it('CSS defines .corpus-import-log', () => {
    assert.ok(globalCss.includes('.corpus-import-log'))
  })
})

// ── Provenance display ────────────────────────────────────────────────────────

describe('corpus polish — provenance display', () => {
  it('CSS defines .corpus-browser-list__provenance', () => {
    assert.ok(globalCss.includes('.corpus-browser-list__provenance'))
  })

  it('CSS defines .corpus-browser-list__author', () => {
    assert.ok(globalCss.includes('.corpus-browser-list__author'))
  })

  it('CSS defines .corpus-browser-list__source-link', () => {
    assert.ok(globalCss.includes('.corpus-browser-list__source-link'))
  })

  it('CSS defines .corpus-browser-list__type-badge', () => {
    assert.ok(globalCss.includes('.corpus-browser-list__type-badge'))
  })

  it('JS renders provenance div in _buildCorpusItem', () => {
    assert.ok(mainJs.includes('corpus-browser-list__provenance'))
  })

  it('JS renders source_url link in _buildCorpusItem', () => {
    assert.ok(mainJs.includes('item.source_url'))
  })
})

// ── i18n coverage ─────────────────────────────────────────────────────────────

describe('corpus polish — i18n (all 11 locales)', () => {
  it('collection keys present in every locale', () => {
    assertLocaleKeys(i18n, [
      'corpus_collection_all',
      'corpus_collection_new',
      'corpus_collection_add',
    ])
  })

  it('bulk keys present in every locale', () => {
    assertLocaleKeys(i18n, [
      'corpus_bulk_select',
      'corpus_bulk_done',
      'corpus_bulk_tag_add',
      'corpus_bulk_tag_remove',
    ])
  })

  it('import log keys present in every locale', () => {
    assertLocaleKeys(i18n, [
      'corpus_import_log_btn',
      'corpus_import_log_empty',
      'corpus_import_log_ok',
      'corpus_import_log_fail',
      'corpus_import_log_dup',
    ])
  })
})
