/**
 * corpus-import-url.test.mjs
 *
 * DOM-aware tests for the "Import from URL" feature.
 * HTML checks use linkedom DOM queries. i18n checks use key-count.
 * No function-body slice inspection.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { loadDocument, readSource } from './lib/dom.mjs'
import { assertLocaleKeys } from './lib/i18n.mjs'

const document = loadDocument()
// Corpus browser lives entirely in js/modes/library.js after the main.js
// split (Session 1 of the frontend refactor).
const mainJs   = readSource('js/modes/library.js')
const i18n     = ['core','annotations','lesson','library','review'].map(f => readSource(`js/i18n/${f}.js`)).join('\n')

// ── DOM structure ─────────────────────────────────────────────────────────────

describe('corpus import URL — DOM structure', () => {
  const REQUIRED_IDS = [
    'corpus-import-url-toggle',
    'corpus-import-url-form',
    'corpus-import-url-input',
    'corpus-import-url-lang',
    'corpus-import-url-submit',
    'corpus-import-url-status',
  ]

  for (const id of REQUIRED_IDS) {
    it(`#${id} present in index.html`, () => {
      assert.ok(document.querySelector(`#${id}`), `#${id} must exist`)
    })
  }

  it('toggle has aria-expanded=false initially', () => {
    const toggle = document.querySelector('#corpus-import-url-toggle')
    assert.equal(toggle?.getAttribute('aria-expanded'), 'false')
  })

  it('import form is hidden initially', () => {
    const form = document.querySelector('#corpus-import-url-form')
    assert.ok(form?.hidden, 'import form starts hidden')
  })

  it('URL input type is "url"', () => {
    const input = document.querySelector('#corpus-import-url-input')
    assert.equal(input?.getAttribute('type'), 'url')
  })

  it('type filter includes "article" option', () => {
    const opt = document.querySelector('#corpus-browser-type option[value="article"]')
    assert.ok(opt, 'type filter must include article option')
  })
})

// ── JS wiring ─────────────────────────────────────────────────────────────────

describe('corpus import URL — main.js', () => {
  it('defines _importCorpusUrl', () => {
    assert.ok(mainJs.includes('_importCorpusUrl'))
  })

  it('defines _populateImportLangSelect', () => {
    assert.ok(mainJs.includes('_populateImportLangSelect'))
  })

  it('POSTs to /corpus/import-url', () => {
    assert.ok(mainJs.includes('/corpus/import-url'))
  })

  it('handles 409 with duplicate message', () => {
    assert.ok(mainJs.includes('status === 409'))
    assert.ok(mainJs.includes('corpus_import_url_duplicate'))
  })

  it('wires toggle, submit, and Enter keydown events', () => {
    assert.ok(mainJs.includes("corpusImportToggle?.addEventListener('click'"))
    assert.ok(mainJs.includes("corpusImportSubmit?.addEventListener('click'"))
    assert.ok(mainJs.includes("corpusImportInput?.addEventListener('keydown'"))
  })
})

// ── i18n coverage ─────────────────────────────────────────────────────────────

describe('corpus import URL — i18n (all 11 locales)', () => {
  const KEYS = [
    'corpus_type_article',
    'corpus_import_url_btn',
    'corpus_import_url_placeholder',
    'corpus_import_url_lang_aria',
    'corpus_import_url_submit',
    'corpus_import_url_success',
    'corpus_import_url_error',
    'corpus_import_url_duplicate',
  ]

  it('all import-URL keys present in every locale', () => {
    assertLocaleKeys(i18n, KEYS)
  })
})
