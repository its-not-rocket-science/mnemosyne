/* (trimmed header unchanged) */

const STORAGE_KEY = 'mnemosyne.reader.pacing.v1'

const results = document.querySelector('#results')
const resultsSection = document.querySelector('#results-section')
const a11yLive = document.querySelector('#a11y-live')

let overloadCount = 0

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

  const dwellLoad = passageMinutes > 4 ? clamp((passageMinutes - 4) / 8, 0, 0.35) : 0
  const interactionLoad = clamp(interactionRate / 16, 0, 0.35)
  const backtrackLoad = clamp(backtrackRate, 0, 0.25)
  const flowCredit = state.scrollEvents > 8 && interactionRate < 4 && backtrackRate < 0.12 ? 0.18 : 0

  state.score = clamp(0.38 + dwellLoad + interactionLoad + backtrackLoad - flowCredit, 0, 1)

  if (state.score >= 0.78) state.currentMode = 'overload'
  else if (state.score >= 0.62) state.currentMode = 'fatigue'
  else if (state.score <= 0.35) state.currentMode = 'flow'
  else state.currentMode = 'steady'

  if (state.currentMode === 'overload') overloadCount++
  else overloadCount = 0

  document.dispatchEvent(new CustomEvent('mnemosyne:pacing-updated', { detail: snapshot() }))

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
  return {
    mode: state.currentMode,
    score: Number(state.score.toFixed(2)),
    nextDelayMs: getNextDelayMs(),
    overloadCount,
  }
}

function renderIndicator() {
  const indicator = ensureIndicator()
  if (!indicator) return

  const snap = snapshot()
  indicator.dataset.pacingMode = snap.mode

  document.body.classList.toggle('mnemosyne-flow-mode', snap.mode === 'flow')

  const text = indicator.querySelector('.cognitive-pacing-indicator__text')
  if (text) {
    const delaySeconds = Math.round(snap.nextDelayMs / 1000)
    text.textContent = `Pacing: ${snap.mode} · next pause ${delaySeconds}s`
  }
}

window.mnemosynePacing = {
  getNextDelayMs,
  snapshot,
  resetPassageWindow,
  isOverloaded: () => overloadCount > 2,
}

/* rest unchanged */