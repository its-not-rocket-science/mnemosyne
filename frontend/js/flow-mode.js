/*
  Flow mode — cinematic sentence-by-sentence reading experience.

  When active:
  - Inactive sentences fade during playback; the active one is at full opacity.
  - Active sentence is centered in the viewport as playback advances.
  - TTS rate adjusts automatically from the cognitive-pacing model.

  Exports consumed by reading-experience.js:
    toggleFlowMode()   — flip on/off, persist, fire event
    isFlowMode()       — current state
    syncFlowBtn()      — update button appearance
*/

import { playbackEngine } from './playback.js'
import { t } from './i18n.js'

const STORAGE_KEY = 'mnemosyne.reader.flowMode'
const results = document.querySelector('#results')

let flowMode = localStorage.getItem(STORAGE_KEY) === 'true'
let _pacingMode = 'steady'

// TTS rate mapped from cognitive-pacing mode.
const PACING_RATE = { flow: 1.15, steady: 1.0, fatigue: 0.85, overload: 0.7 }

function reducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

function setActiveCard(sentenceIndex) {
  results?.querySelectorAll('.sentence-card').forEach(card => {
    card.toggleAttribute('data-flow-active', card.dataset.sentenceIndex === String(sentenceIndex))
  })

  if (sentenceIndex < 0) return
  const card = results?.querySelector(`[data-sentence-index="${sentenceIndex}"]`)
  card?.scrollIntoView({
    behavior: reducedMotion() ? 'instant' : 'smooth',
    block: 'center',
    inline: 'nearest',
  })
}

function applyPacingRate() {
  if (!flowMode || playbackEngine.state === 'idle') return
  playbackEngine.rate = PACING_RATE[_pacingMode] ?? 1.0
}

function applyFlowMode() {
  document.body.classList.toggle('reader-flow-mode', flowMode)
  if (!flowMode) {
    document.body.classList.remove('reader-flow-playing')
    results?.querySelectorAll('[data-flow-active]').forEach(el => el.removeAttribute('data-flow-active'))
    playbackEngine.rate = 1.0
  } else {
    applyPacingRate()
  }
}

export function isFlowMode() { return flowMode }

export function toggleFlowMode() {
  flowMode = !flowMode
  localStorage.setItem(STORAGE_KEY, String(flowMode))
  applyFlowMode()
  document.dispatchEvent(new CustomEvent('mnemosyne:flow-mode-changed', { detail: { active: flowMode } }))
}

export function syncFlowBtn() {
  const btn = document.querySelector('#reader-flow-mode-btn')
  if (!btn) return
  btn.setAttribute('aria-pressed', String(flowMode))
  btn.classList.toggle('reader-focus-btn--active', flowMode)
  const key = flowMode ? 'reader_flow_on' : 'reader_flow_mode'
  btn.textContent = t(key)
  btn.dataset.i18n = key
}

function installListeners() {
  playbackEngine.addEventListener('state-change', ({ detail: { state, current } }) => {
    if (!flowMode) return
    const playing = state !== 'idle'
    document.body.classList.toggle('reader-flow-playing', playing)
    setActiveCard(playing && current != null ? current.index : -1)
  })

  document.addEventListener('mnemosyne:pacing-updated', ({ detail }) => {
    _pacingMode = detail.mode
    applyPacingRate()
  })

  document.addEventListener('mnemosyne:language-changed', syncFlowBtn)
}

function init() {
  applyFlowMode()
  installListeners()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
