/**
 * main.js — Thin entry point.
 *
 * Loads the Web Component definitions, wires authentication, then hands off
 * to the five mode coordinators under js/modes/. Each coordinator owns its
 * own DOM queries and event listeners (see js/modes/*.js doc comments for
 * what each one owns) and exposes a single init function that this file
 * calls in order.
 */
import '../components/mnemosyne-pill.js'
import '../components/mnemosyne-modal.js'
import '../components/mnemosyne-filter-bar.js'
import '../components/mnemosyne-detail-pane.js'
import '../components/mnemosyne-player.js'
import '../components/mnemosyne-now-playing-bar.js'

import { initAuth, fetchAppConfig } from './auth.js'
import { initUiLanguage } from './i18n.js'
import './shared.js'

import { initExplorer } from './modes/explorer.js'
import { initLesson } from './modes/lesson.js'
import { initReview, initReviewSession } from './modes/review.js'
import { initLibrary } from './modes/library.js'
import { initCreate } from './modes/create.js'
import { _fetchReadingHistory } from './modes/library.js'
import { navigate, parseRoute } from './router.js'

initUiLanguage()

// ── Home route redirect ──────────────────────────────────────────────────────
// #/ redirects to #/library once the user has navigated anywhere before (a
// simple "has history" signal that doesn't require a backend round-trip
// before the route resolves). First-ever visit lands on #/explore via
// js/modes/explorer.js's own route handler, which treats '' the same as
// 'explore' until results exist.
const HISTORY_FLAG = 'mnemosyne_has_navigated'
if (parseRoute().path === 'home' && localStorage.getItem(HISTORY_FLAG)) {
  navigate('#/library')
}
try { localStorage.setItem(HISTORY_FLAG, '1') } catch { /* storage unavailable — non-fatal */ }

/**
 * init() — runs each mode coordinator's init in dependency order:
 * explorer first (it loads the language list and kicks off the deep-link
 * flow other coordinators rely on), then the reading surface, then the
 * remaining surfaces which only wire their own listeners.
 */
function init() {
  initExplorer()
  initLesson()
  initReview()
  initLibrary()
  initCreate()
}

init()

// ── App config + auth init ────────────────────────────────────────────────────

fetchAppConfig()
initAuth()

// ── Review session + reading history init (runs once #main-content becomes visible)
;(function () {
  const mc = document.querySelector('#main-content')
  if (!mc) return
  let _initialized = false
  function _maybeInit() {
    if (mc.hidden) return
    initReviewSession()
    if (!_initialized) { _initialized = true; _fetchReadingHistory() }
  }
  _maybeInit()
  new MutationObserver(_maybeInit).observe(mc, { attributes: true, attributeFilter: ['hidden'] })
})()
