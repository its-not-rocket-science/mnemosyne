/*
  Cognitive pacing model

  Local, privacy-preserving pacing layer for Autonomous Learning Mode.
  It infers broad reading state from behaviour only:
  - flow: steady scrolling, low interaction, normal dwell time
  - fatigue: long dwell, rapid backtracking, many interactions
  - overload: repeated annotation opens / very slow progress

  The module exposes a window-level pacing API consumed by autonomous-learning.js:
    window.mnemosynePacing.getNextDelayMs()
    window.mnemosynePacing.snapshot()
*/

const STORAGE_KEY = 'mnemosyne.reader.pacing.v1'

const results = document.querySelector('#results')
const resultsSection = document.querySelector('#results-section')
const a11yLive = document.querySelector('#a11y-live')

const state = {
  sessionStartedAt: Date.now(),
  lastScrollY: window.scrollY,
  lastScrollAt: Date.now(),
  scrollEvents: 0,
  reverseScrolls: 0,
  annotationOpens: 0,
  pointerInteractions: 0,
  keyInteractions: 0,
  passageStartedAt: Date.now(),
  currentMode: 'steady',
  score: 0.5,
}

function announce(message) {
  if (!a11yLive) return
  a11yLive.textContent = ''
  queueMicrotask(() => { a11yLive.textContent = message })
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value))
}

function computeScore() {
  const now = Date.now()
  const passageMinutes = Math.max((now - state.passageStartedAt) / 60_000, 0.1)
  const interactions = state.annotationOpens + state.pointerInteractions * 0.4 + state.keyInteractions * 0.25
  const interactionRate = interactions / passageMinutes
  const backtrackRate = state.reverseScrolls / Math.max(state.scrollEvents, 1)

  // Higher score = more cognitive load.
  const dwellLoad = passageMinutes > 4 ? clamp((passageMinutes - 4) / 8, 0, 0.35) : 0
  const interactionLoad = clamp(interactionRate / 16, 0, 0.35)
  const backtrackLoad = clamp(backtrackRate, 0, 0.25)
  const flowCredit = state.scrollEvents > 8 && interactionRate < 4 && backtrackRate < 0.12 ? 0.18 : 0

  state.score = clamp(0.38 + dwellLoad + interactionLoad + backtrackLoad - flowCredit, 0, 1)

  if (state.score >= 0.78) state.currentMode = 'overload'
  else if (state.score >= 0.62) state.currentMode = 'fatigue'
  else if (state.score <= 0.35) state.currentMode = 'flow'
  else state.currentMode = 'steady'

  return state.score
}

function getNextDelayMs() {
  computeScore()
  switch (state.currentMode) {
    case 'flow': return 900
    case 'steady': return 1800
    case 'fatigue': return 4500
    case 'overload': return 9000
    default: return 1800
  }
}

function snapshot() {
  computeScore()
  return {
    mode: state.currentMode,
    score: Number(state.score.toFixed(2)),
    nextDelayMs: getNextDelayMs(),
    annotationOpens: state.annotationOpens,
    reverseScrolls: state.reverseScrolls,
  }
}

function resetPassageWindow() {
  state.passageStartedAt = Date.now()
  state.scrollEvents = 0
  state.reverseScrolls = 0
  state.annotationOpens = 0
  state.pointerInteractions = 0
  state.keyInteractions = 0
  renderIndicator()
}

function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    lastMode: state.currentMode,
    lastScore: state.score,
    updatedAt: new Date().toISOString(),
  }))
}

function ensureIndicator() {
  if (!resultsSection) return null
  let indicator = document.querySelector('#cognitive-pacing-indicator')
  if (indicator) return indicator

  indicator = document.createElement('aside')
  indicator.id = 'cognitive-pacing-indicator'
  indicator.className = 'cognitive-pacing-indicator'
  indicator.setAttribute('aria-label', 'Cognitive pacing status')
  indicator.innerHTML = `
    <span class="cognitive-pacing-indicator__dot" aria-hidden="true"></span>
    <span class="cognitive-pacing-indicator__text">Pacing: steady</span>
  `

  const anchor = document.querySelector('#reader-intelligence-summary') ||
                 document.querySelector('#reader-adaptive-toolbar') ||
                 document.querySelector('#reader-experience-toolbar')
  if (anchor) anchor.insertAdjacentElement('afterend', indicator)
  else resultsSection.prepend(indicator)

  return indicator
}

function renderIndicator() {
  const indicator = ensureIndicator()
  if (!indicator) return

  const snap = snapshot()
  indicator.dataset.pacingMode = snap.mode
  const text = indicator.querySelector('.cognitive-pacing-indicator__text')
  if (text) {
    const delaySeconds = Math.round(snap.nextDelayMs / 1000)
    text.textContent = `Pacing: ${snap.mode} · next pause ${delaySeconds}s`
  }
}

function installObservers() {
  window.addEventListener('scroll', () => {
    const now = Date.now()
    const currentY = window.scrollY
    if (currentY < state.lastScrollY - 24) state.reverseScrolls += 1
    state.scrollEvents += 1
    state.lastScrollY = currentY
    state.lastScrollAt = now
  }, { passive: true })

  document.addEventListener('pointerdown', event => {
    if (event.target.closest?.('.reader-annotation')) state.annotationOpens += 1
    else state.pointerInteractions += 1
  }, { passive: true })

  document.addEventListener('keydown', event => {
    if (event.key === 'Tab') return
    state.keyInteractions += 1
  })

  if (results) {
    const observer = new MutationObserver(mutations => {
      if (mutations.some(m => m.addedNodes.length)) {
        resetPassageWindow()
        announce('Pacing reset for new passage')
      }
    })
    observer.observe(results, { childList: true, subtree: false })
  }

  setInterval(() => {
    computeScore()
    renderIndicator()
    persist()
  }, 10_000)
}

window.mnemosynePacing = {
  getNextDelayMs,
  snapshot,
  resetPassageWindow,
}

function init() {
  ensureIndicator()
  installObservers()
  renderIndicator()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
