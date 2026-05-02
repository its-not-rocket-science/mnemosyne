/*
  Recommended reading panel — compact, scroll-triggered.

  Hidden until the reader reaches 70% of the results section.
  Prefetches recommendations at 50% so data is ready by trigger time.

  Layout: "Next up" eyebrow → pacing rationale → featured card →
  [Continue reading] [Show alternatives] → if Autonomous: 4s countdown →
  [Show more] expands alternative cards.
*/

import { getAuthHeaders } from './auth.js'
import { t } from './i18n.js'

const API_BASE = 'http://localhost:8000'
const COUNTDOWN_MS = 4000
const TRIGGER_PROGRESS = 0.7
const PREFETCH_PROGRESS = 0.5

const languageSelect = document.querySelector('#language')
const resultsSection = document.querySelector('#results-section')
const results = document.querySelector('#results')
const pickerTextarea = document.querySelector('#picker-text')
const pickerUseBtn = document.querySelector('#picker-use-btn')
const a11yLive = document.querySelector('#a11y-live')
const scrollArea = document.querySelector('.app-shell__scroll-area')

let currentRecommendations = []
let lastRecommendationData = null
let progressShown = false
let prefetchStarted = false
let panel = null
let countdownTimer = null
let altExpanded = false

function announce(msg) {
  if (!a11yLive) return
  a11yLive.textContent = ''
  queueMicrotask(() => { a11yLive.textContent = msg })
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

function passageText(item) {
  if (Array.isArray(item.passage) && item.passage.length) return item.passage.map(s => s.text).join(' ')
  return item.text || ''
}

function reasonFor(item) {
  const unknownPct = Math.round((item.unknown_ratio || 0) * 100)
  const parts = []
  if (item.is_continuation) parts.push(t('rec_continues'))
  if (unknownPct > 0) parts.push(t('rec_unfamiliar').replace('{n}', unknownPct))
  if ((item.grammar_score || 0) > 0.35) parts.push(t('rec_grammar_density'))
  if (item.modulation_mode) parts.push(window.mnemosyneDifficulty?.describeModulation?.(item) || '')
  if (!parts.filter(Boolean).length) parts.push(t('rec_near_level'))
  return parts.filter(Boolean).join(' · ')
}

function orderRecommendations(data) {
  const sentences = data?.sentences || []
  const chosen = window.mnemosyneDifficulty?.chooseRecommendation?.(data)
  if (!chosen) return sentences
  const chosenKey = chosen.sentence_id || chosen.text
  const rest = sentences.filter(item => (item.sentence_id || item.text) !== chosenKey)
  return [chosen, ...rest]
}

function pacingRationale() {
  const mode = window.mnemosynePacing?.snapshot?.().mode || 'steady'
  return t(`passage_end_${mode}`) || t('passage_end_steady')
}

function readingProgress() {
  if (!resultsSection) return 0
  const rect = resultsSection.getBoundingClientRect()
  const resultsTop = rect.top + window.scrollY
  const resultsHeight = resultsSection.scrollHeight
  const viewportBottom = window.scrollY + window.innerHeight
  return Math.min(1, Math.max(0, (viewportBottom - resultsTop) / resultsHeight))
}

function studyRecommendation(item) {
  const text = passageText(item)
  if (!text || !pickerTextarea || !pickerUseBtn) return
  document.body.classList.add('mnemosyne-transitioning-passage')
  pickerTextarea.value = text
  pickerTextarea.dispatchEvent(new Event('input', { bubbles: true }))
  pickerUseBtn.click()
  setTimeout(() => document.body.classList.remove('mnemosyne-transitioning-passage'), 900)
  announce('Recommended passage loaded')
}

function stopCountdown() {
  clearInterval(countdownTimer)
  countdownTimer = null
}

function ensurePanel() {
  if (panel) return panel
  if (!resultsSection) return null
  panel = document.createElement('aside')
  panel.id = 'recommended-reading-panel'
  panel.className = 'recommended-reading-panel rec-panel'
  panel.setAttribute('aria-labelledby', 'rec-panel-eyebrow')
  panel.hidden = true
  resultsSection.insertAdjacentElement('afterend', panel)
  return panel
}

function renderAlternatives(listEl, alternatives) {
  const frag = document.createDocumentFragment()
  alternatives.slice(0, 4).forEach(item => {
    const card = document.createElement('article')
    card.className = 'recommended-reading-card'
    card.setAttribute('role', 'listitem')
    const title = item.source_title || (item.is_continuation ? t('rec_continue_reading') : t('rec_suggested'))
    const focusSentence = item.text || passageText(item)
    card.innerHTML = `
      <div class="recommended-reading-card__meta">
        <span>${escapeHtml(item.is_continuation ? t('rec_continue') : t('rec_option'))}</span>
        <span>${escapeHtml(item.difficulty_label || t('rec_matched'))}</span>
        <span>${Number(item.difficulty || 0).toFixed(2)}</span>
      </div>
      <h4>${escapeHtml(title)}</h4>
      <p class="recommended-reading-card__text">${escapeHtml(focusSentence)}</p>
      <p class="recommended-reading-card__reason">${escapeHtml(reasonFor(item))}</p>
      <div class="recommended-reading-card__actions">
        <button type="button" class="button-primary recommended-reading-card__study">
          ${escapeHtml(t('rec_study'))}
        </button>
      </div>
    `
    card.querySelector('.recommended-reading-card__study')?.addEventListener('click', () => {
      dismiss()
      studyRecommendation(item)
    })
    frag.appendChild(card)
  })
  listEl.appendChild(frag)
}

function renderPanel() {
  const p = ensurePanel()
  if (!p || !currentRecommendations.length) return

  const chosen = currentRecommendations[0]
  const alternatives = currentRecommendations.slice(1)
  const autonomousEnabled = window.mnemosyneAutonomous?.isEnabled?.() || false
  const title = chosen.source_title || (chosen.is_continuation ? t('rec_continue_reading') : t('rec_suggested'))
  const focusSentence = chosen.text || passageText(chosen)

  p.innerHTML = `
    <p class="recommended-reading-panel__eyebrow rec-panel__eyebrow" id="rec-panel-eyebrow">${escapeHtml(t('rec_next_up'))}</p>
    <p class="rec-panel__rationale">${escapeHtml(pacingRationale())}</p>
    <div class="rec-panel__featured recommended-reading-card recommended-reading-card--chosen">
      <div class="recommended-reading-card__meta">
        <span>${escapeHtml(chosen.difficulty_label || t('rec_matched'))}</span>
        <span>${Number(chosen.difficulty || 0).toFixed(2)}</span>
      </div>
      <h4>${escapeHtml(title)}</h4>
      <p class="recommended-reading-card__text">${escapeHtml(focusSentence)}</p>
      <p class="recommended-reading-card__reason">${escapeHtml(reasonFor(chosen))}</p>
    </div>
    <div class="rec-panel__actions passage-transition__actions">
      <button type="button" class="button-primary rec-panel__continue">
        ${escapeHtml(t('passage_end_continue'))}
      </button>
      <button type="button" class="ghost-button rec-panel__toggle-alt">
        ${escapeHtml(t('passage_end_alternatives'))}
      </button>
    </div>
    ${autonomousEnabled ? `
    <div class="rec-panel__auto passage-transition__auto">
      <span class="passage-transition__countdown rec-panel__countdown" aria-live="polite" aria-atomic="true"></span>
      <div class="passage-transition__progress" aria-hidden="true">
        <span class="passage-transition__progress-fill rec-panel__fill"></span>
      </div>
      <button type="button" class="ghost-button ghost-button--small rec-panel__pause">
        ${escapeHtml(t('passage_end_pause'))}
      </button>
    </div>
    ` : ''}
    ${alternatives.length ? `
    <div class="rec-panel__expand-row">
      <button type="button" class="ghost-button ghost-button--small rec-panel__expand">
        ${escapeHtml(t('rec_show_more'))}
      </button>
    </div>
    <div class="rec-panel__alternatives recommended-reading-list" hidden role="list"></div>
    ` : ''}
  `

  p.querySelector('.rec-panel__continue')?.addEventListener('click', () => {
    dismiss()
    studyRecommendation(chosen)
  })

  // "Show alternatives" — expands the alternatives list inside the panel
  p.querySelector('.rec-panel__toggle-alt')?.addEventListener('click', () => {
    const altList = p.querySelector('.rec-panel__alternatives')
    const expandBtn = p.querySelector('.rec-panel__expand')
    if (!altList) return
    altExpanded = !altExpanded
    altList.hidden = !altExpanded
    if (expandBtn) expandBtn.textContent = altExpanded ? t('rec_show_less') : t('rec_show_more')
    if (altExpanded && !altList.children.length) renderAlternatives(altList, alternatives)
  })

  p.querySelector('.rec-panel__expand')?.addEventListener('click', () => {
    const altList = p.querySelector('.rec-panel__alternatives')
    if (!altList) return
    altExpanded = !altExpanded
    altList.hidden = !altExpanded
    const expandBtn = p.querySelector('.rec-panel__expand')
    if (expandBtn) expandBtn.textContent = altExpanded ? t('rec_show_less') : t('rec_show_more')
    if (altExpanded && !altList.children.length) renderAlternatives(altList, alternatives)
  })

  if (autonomousEnabled) {
    const countdownEl = p.querySelector('.rec-panel__countdown')
    const fillEl = p.querySelector('.rec-panel__fill')
    const pauseBtn = p.querySelector('.rec-panel__pause')
    let paused = false
    let remaining = COUNTDOWN_MS

    function tick() {
      remaining -= 1000
      const secs = Math.max(0, Math.ceil(remaining / 1000))
      if (countdownEl) countdownEl.textContent = t('passage_end_loading').replace('{n}', secs)
      if (remaining <= 0) { stopCountdown(); dismiss(); window.mnemosyneAutonomous?.loadNext?.() }
    }

    function beginCountdown() {
      remaining = COUNTDOWN_MS
      if (countdownEl) countdownEl.textContent = t('passage_end_loading').replace('{n}', COUNTDOWN_MS / 1000)
      fillEl?.classList.remove('passage-transition__progress-fill--running')
      void fillEl?.offsetWidth
      fillEl?.classList.add('passage-transition__progress-fill--running')
      countdownTimer = setInterval(tick, 1000)
      if (countdownEl) announce(countdownEl.textContent)
    }

    pauseBtn?.addEventListener('click', () => {
      paused = !paused
      if (paused) {
        stopCountdown()
        fillEl?.classList.add('passage-transition__progress-fill--paused')
        if (pauseBtn) pauseBtn.textContent = t('passage_end_resume')
        announce(t('passage_end_paused'))
      } else {
        fillEl?.classList.remove('passage-transition__progress-fill--paused')
        beginCountdown()
        if (pauseBtn) pauseBtn.textContent = t('passage_end_pause')
      }
    })

    beginCountdown()
  }
}

function showPanel() {
  const p = ensurePanel()
  if (!p || !currentRecommendations.length) return
  altExpanded = false
  stopCountdown()
  renderPanel()
  p.hidden = false
  announce(t('rec_next_up'))
}

function dismiss() {
  stopCountdown()
  if (panel) panel.hidden = true
}

function resetProgress() {
  progressShown = false
  prefetchStarted = false
  altExpanded = false
  stopCountdown()
  if (panel) {
    panel.hidden = true
    panel.innerHTML = ''
  }
}

function onScroll() {
  if (!results || results.children.length === 0) return
  const progress = readingProgress()
  if (!prefetchStarted && progress >= PREFETCH_PROGRESS) {
    prefetchStarted = true
    loadRecommendations()
  }
  if (!progressShown && progress >= TRIGGER_PROGRESS) {
    progressShown = true
    showPanel()
  }
}

async function loadRecommendations() {
  const language = languageSelect?.value
  if (!language) return
  try {
    const response = await fetch(
      `${API_BASE}/recommend?language=${encodeURIComponent(language)}&limit=12`,
      { headers: getAuthHeaders() },
    )
    if (!response.ok) return
    const data = await response.json()
    lastRecommendationData = data
    currentRecommendations = orderRecommendations(data)
    // If progress already triggered but panel was empty, render now
    if (progressShown && panel?.hidden !== false) showPanel()
  } catch {
    // silent — panel stays hidden
  }
}

// Public API — lets passage-transition.js trigger the panel
window.mnemosyneRecommended = {
  show() {
    progressShown = true
    if (!prefetchStarted) {
      prefetchStarted = true
      loadRecommendations()
    } else {
      showPanel()
    }
  },
}

function init() {
  ensurePanel()
  ;(scrollArea ?? window).addEventListener('scroll', onScroll, { passive: true })

  languageSelect?.addEventListener('change', () => {
    resetProgress()
    lastRecommendationData = null
    currentRecommendations = []
  })
  document.addEventListener('mnemosyne:language-changed', () => {
    resetProgress()
    lastRecommendationData = null
    currentRecommendations = []
  })

  // Reset and re-check when new results load
  if (results) {
    new MutationObserver(mutations => {
      if (mutations.some(m => m.addedNodes.length)) {
        resetProgress()
        // Re-evaluate after DOM settles (handles short passages fully in viewport)
        queueMicrotask(onScroll)
      }
    }).observe(results, { childList: true })
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
