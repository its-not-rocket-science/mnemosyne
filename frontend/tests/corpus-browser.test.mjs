/**
 * corpus-browser.test.mjs
 *
 * DOM-aware tests for the corpus browser dialog, filters, sort, and language
 * selector. Consolidates corpus-sort and corpus-lang-filter.
 *
 * HTML checks use linkedom. i18n checks use key-count. No body slices.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { loadDocument, readSource } from './lib/dom.mjs'
import { assertLocaleKeys } from './lib/i18n.mjs'

const document  = loadDocument()
// Corpus browser lives entirely in js/modes/library.js after the main.js
// split (Session 1 of the frontend refactor).
const mainJs    = readSource('js/modes/library.js')
const globalCss = readSource('css/components.css')
const i18n      = ['core','annotations','lesson','library','review'].map(f => readSource(`js/i18n/${f}.js`)).join('\n')

// ── Route structure ───────────────────────────────────────────────────────────
// Session 3 of the frontend refactor: #corpus-browser-dialog became the
// #/library route's #route-library section (dialog → route conversion).

describe('corpus browser — route structure', () => {
  const REQUIRED_IDS = [
    'open-corpus-browser-btn',
    'route-library',
    'corpus-browser-heading',
    'corpus-browser-close-btn',
    'corpus-browser-search',
    'corpus-browser-lang',
    'corpus-browser-type',
    'corpus-browser-sort',
    'corpus-browser-list',
    'corpus-browser-more-btn',
    'corpus-browser-stats',
  ]

  for (const id of REQUIRED_IDS) {
    it(`#${id} present in index.html`, () => {
      assert.ok(document.querySelector(`#${id}`), `#${id} must exist`)
    })
  }

  it('#route-library is a <section>, not a <dialog> (retired in Session 3)', () => {
    const section = document.querySelector('#route-library')
    assert.equal(section?.tagName, 'SECTION')
  })

  it('#route-library starts hidden', () => {
    const section = document.querySelector('#route-library')
    assert.ok(section?.hasAttribute('hidden'), '#route-library must start hidden')
  })

  it('route section has aria-labelledby pointing to corpus-browser-heading', () => {
    const section = document.querySelector('#route-library')
    assert.equal(section?.getAttribute('aria-labelledby'), 'corpus-browser-heading')
  })

  it('close button has aria-label or i18n aria-label', () => {
    const btn = document.querySelector('#corpus-browser-close-btn')
    assert.ok(
      btn?.getAttribute('aria-label') || btn?.getAttribute('data-i18n-aria-label'),
      'close button must have an accessible label'
    )
  })
})

// ── Sort select ───────────────────────────────────────────────────────────────

describe('corpus browser — sort select', () => {
  it('has all four sort options', () => {
    const select  = document.querySelector('#corpus-browser-sort')
    const values  = [...select.querySelectorAll('option')].map(o => o.getAttribute('value'))
    assert.ok(values.includes('recent'),      'sort must have "recent" option')
    assert.ok(values.includes('in_progress'), 'sort must have "in_progress" option')
    assert.ok(values.includes('not_started'), 'sort must have "not_started" option')
    assert.ok(values.includes('complete'),    'sort must have "complete" option')
  })

  it('each sort option carries its i18n key', () => {
    const select = document.querySelector('#corpus-browser-sort')
    const keys   = [...select.querySelectorAll('option')].map(o => o.getAttribute('data-i18n'))
    assert.ok(keys.includes('corpus_sort_recent'))
    assert.ok(keys.includes('corpus_sort_in_progress'))
    assert.ok(keys.includes('corpus_sort_not_started'))
    assert.ok(keys.includes('corpus_sort_complete'))
  })
})

// ── Type filter ───────────────────────────────────────────────────────────────

describe('corpus browser — type filter', () => {
  it('includes pasted_text, uploaded_file, and article options', () => {
    const select = document.querySelector('#corpus-browser-type')
    const values = [...select.querySelectorAll('option')].map(o => o.getAttribute('value'))
    assert.ok(values.includes('pasted_text'),   'type filter must have pasted_text')
    assert.ok(values.includes('uploaded_file'), 'type filter must have uploaded_file')
    assert.ok(values.includes('article'),       'type filter must have article')
  })
})

// ── Language filter ───────────────────────────────────────────────────────────

describe('corpus browser — language filter', () => {
  it('#corpus-browser-lang has a default "all" option', () => {
    const select  = document.querySelector('#corpus-browser-lang')
    const allOpt  = select?.querySelector('option[data-i18n="corpus_lang_all"]')
    assert.ok(allOpt, 'lang filter must have a corpus_lang_all default option')
  })
})

// ── JS wiring ─────────────────────────────────────────────────────────────────

describe('corpus browser — main.js', () => {
  it('defines _loadCorpus, _buildCorpusItem, _corpusParams', () => {
    assert.ok(mainJs.includes('_loadCorpus'))
    assert.ok(mainJs.includes('_buildCorpusItem'))
    assert.ok(mainJs.includes('_corpusParams'))
  })

  it('defines _populateCorpusLangSelect', () => {
    assert.ok(mainJs.includes('_populateCorpusLangSelect'))
  })

  it('fetches /corpus/languages for the lang filter', () => {
    assert.ok(mainJs.includes('/corpus/languages'))
  })

  it('calls /corpus endpoint with filters', () => {
    assert.ok(mainJs.includes('/corpus?'))
  })

  it('debounces search input', () => {
    assert.ok(mainJs.includes('_corpusSearchTimer'))
  })

  it('load-more calls _loadCorpus(true)', () => {
    assert.ok(mainJs.includes('_loadCorpus(true)'))
  })

  it('sort, lang, type, and tag changes trigger reload', () => {
    assert.ok(mainJs.includes("corpusBrowserSort?.addEventListener('change'"))
    assert.ok(mainJs.includes("corpusBrowserLang?.addEventListener('change'"))
    assert.ok(mainJs.includes("corpusBrowserType?.addEventListener('change'"))
    assert.ok(mainJs.includes("corpusBrowserTag?.addEventListener('change'"))
  })
})

// ── CSS ───────────────────────────────────────────────────────────────────────

describe('corpus browser — CSS', () => {
  const CLASSES = [
    '.corpus-browser-dialog',
    '.corpus-browser-filters',
    '.corpus-browser-list',
    '.corpus-browser-list__item',
    '.corpus-browser-list__btn',
    '.corpus-browser-list__title',
    '.corpus-browser-count',
  ]

  for (const cls of CLASSES) {
    it(`global.css defines ${cls}`, () => {
      assert.ok(globalCss.includes(cls))
    })
  }

  it('forced-colors support present', () => {
    assert.ok(
      globalCss.includes('forced-colors') && globalCss.includes('.corpus-browser'),
      'forced-colors block must cover corpus-browser'
    )
  })
})

// ── i18n coverage ─────────────────────────────────────────────────────────────

describe('corpus browser — i18n (all 11 locales)', () => {
  it('core browser keys present in every locale', () => {
    assertLocaleKeys(i18n, [
      'corpus_browser_btn',
      'corpus_browser_heading',
      'corpus_filter_search_placeholder',
      'corpus_type_all',
      'corpus_type_pasted',
      'corpus_type_file',
      'corpus_empty',
      'corpus_load_more',
      'corpus_open_btn',
    ])
  })

  it('sort keys present in every locale', () => {
    assertLocaleKeys(i18n, [
      'corpus_sort_recent',
      'corpus_sort_in_progress',
      'corpus_sort_not_started',
      'corpus_sort_complete',
    ])
  })

  it('lang filter key present in every locale', () => {
    assertLocaleKeys(i18n, ['corpus_lang_all'])
  })
})
