/**
 * route-shell.test.mjs — index.html shell structure for Session 3 of the
 * frontend refactor (hash router, dialog → route conversion).
 *
 * Acceptance criteria covered here:
 *   · Exactly 4 <dialog> elements remain (GDPR, shortcuts, about, offline-explain).
 *   · The five route sections exist and start hidden (except #route-explore,
 *     which is the default landing surface and visible on first load).
 *   · #main hosts the explore/lesson routes; #app-shell hosts review/library/create.
 */
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { loadDocument, readSource } from './lib/dom.mjs'

const document = loadDocument()

describe('route shell — dialog count', () => {
  it('exactly 4 <dialog> elements remain in index.html', () => {
    const dialogs = [...document.querySelectorAll('dialog')]
    assert.equal(dialogs.length, 4, `expected 4 dialogs, found ${dialogs.length}: ${dialogs.map(d => d.id).join(', ')}`)
  })

  it('the 4 remaining dialogs are exactly GDPR, shortcuts, about, offline-explain', () => {
    const ids = [...document.querySelectorAll('dialog')].map(d => d.id).sort()
    assert.deepEqual(ids, ['about-dialog', 'gdpr-dialog', 'offline-explain-dialog', 'shortcuts-dialog'])
  })

  it('retired dialog ids no longer exist anywhere in index.html', () => {
    const retiredIds = [
      'text-picker',
      'corpus-browser-dialog',
      'vocab-browser-dialog',
      'save-lesson-dialog',
      'load-lesson-dialog',
      'picker-sample-dialog',
      'review-panel',
      'save-unsupported-dialog',
      'parse-dialog',
    ]
    for (const id of retiredIds) {
      assert.equal(document.getElementById(id), null, `#${id} must not exist — it was converted to a route`)
    }
  })
})

describe('route shell — route sections', () => {
  const ROUTE_SECTIONS = [
    'route-explore',
    'route-explore-picker',
    'route-review',
    'route-library',
    'route-library-vocab',
    'route-create',
  ]

  for (const id of ROUTE_SECTIONS) {
    it(`#${id} exists and is a <section>`, () => {
      const el = document.getElementById(id)
      assert.ok(el, `#${id} must exist`)
      assert.equal(el.tagName, 'SECTION', `#${id} must be a <section>, not ${el?.tagName}`)
    })
  }

  it('#route-review, #route-library, #route-library-vocab, #route-create start hidden', () => {
    for (const id of ['route-review', 'route-library', 'route-library-vocab', 'route-create', 'route-explore-picker']) {
      const el = document.getElementById(id)
      assert.ok(el.hasAttribute('hidden'), `#${id} must start hidden`)
    }
  })

  it('#main hosts #route-explore and #results-section (the #/lesson route)', () => {
    const main = document.querySelector('#main')
    assert.ok(main, '#main must exist')
    assert.ok(main.querySelector('#route-explore'), '#main must contain #route-explore')
    assert.ok(main.querySelector('#results-section'), '#main must contain #results-section')
  })

  it('#results-section is tagged data-route="lesson"', () => {
    const section = document.querySelector('#results-section')
    assert.equal(section?.getAttribute('data-route'), 'lesson')
  })

  it('only one <main> landmark exists', () => {
    assert.equal(document.querySelectorAll('main').length, 1)
  })
})

describe('route shell — router wiring', () => {
  const ROUTE_AWARE_MODULES = [
    'js/router.js',
    'js/modes/explorer.js',
    'js/modes/lesson.js',
    'js/modes/library.js',
    'js/modes/create.js',
    'js/review-session.js',
  ]

  for (const path of ROUTE_AWARE_MODULES) {
    it(`${path} references router.js`, () => {
      const src = readSource(path)
      const isRouterItself = path === 'js/router.js'
      assert.ok(
        isRouterItself || src.includes("router.js'"),
        `${path} must import navigate/onRoute from router.js`
      )
    })
  }

  it('mnemosyne-top-nav.js renders route links and imports the router', () => {
    const src = readSource('components/mnemosyne-top-nav.js')
    assert.ok(src.includes("router.js'"), 'top-nav must import the router')
    assert.ok(src.includes('NAV_ROUTES'), 'top-nav must define the route link model')
    assert.ok(src.includes('--accent-fill'), 'active route indicator must use --accent-fill per CLAUDE.md')
  })
})
