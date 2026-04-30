/*
  Adaptive recommended reading panel.

  Uses /recommend and applies client-side difficulty modulation when available.
  The result is transparent: users see why a passage was chosen and how the
  system is adjusting challenge.
*/

import { getAuthHeaders } from './auth.js'
import { t } from './i18n.js'

const API_BASE = 'http://localhost:8000'

const languageSelect = document.querySelector('#language')
const resultsSection = document.querySelector('#results-section')
const pickerTextarea = document.querySelector('#picker-text')
const pickerUseBtn = document.querySelector('#picker-use-btn')
const a11yLive = document.querySelector('#a11y-live')

let currentRecommendations = []
let lastRecommendationData = null

function announce(message) {
  if (!a11yLive) return
  a11yLive.textContent = ''
  queueMicrotask(() => { a11yLive.textContent = message })
}

function ensurePanel() {
  if (!resultsSection) return null
  let panel = document.querySelector('#recommended-reading-panel')
  if (panel) return panel

  panel = document.createElement('aside')
  panel.id = 'recommended-reading-panel'
  panel.className = 'recommended-reading-panel'
  panel.setAttribute('aria-labelledby', 'recommended-reading-heading')
  panel.hidden = true

  panel.innerHTML = `
    <div class="recommended-reading-panel__header">
      <div>
        <p class="recommended-reading-panel__eyebrow" data-i18n="adaptive_path_label">${t('adaptive_path_label')}</p>
        <h3 id="recommended-reading-heading" data-i18n="rec_heading">${t('rec_heading')}</h3>
      </div>
      <button type="button" class="ghost-button ghost-button--small" id="recommended-reading-refresh"
              data-i18n="rec_refresh">${t('rec_refresh')}</button>
    </div>
    <p class="recommended-reading-panel__summary"></p>
    <p class="recommended-reading-panel__hint" aria-live="polite"></p>
    <div class="recommended-reading-list" role="list"></div>
  `

  const adaptiveToolbar = document.querySelector('#reader-adaptive-toolbar')
  const experienceToolbar = document.querySelector('#reader-experience-toolbar')
  const anchor = adaptiveToolbar || experienceToolbar
  if (anchor) anchor.insertAdjacentElement('afterend', panel)
  else resultsSection.prepend(panel)

  panel.querySelector('#recommended-reading-refresh')?.addEventListener('click', loadRecommendations)
  return panel
}

function passageText(item) {
  if (Array.isArray(item.passage) && item.passage.length) {
    return item.passage.map(s => s.text).join(' ')
  }
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

function magicalHint(data, chosen) {
  const pacing = window.mnemosynePacing?.snapshot?.()
  const modulation = window.mnemosyneDifficulty?.describeModulation?.(chosen)
  const difficulty = Number(chosen?.difficulty ?? 0).toFixed(2)
  const range = `${Number(data?.target_difficulty_min || 0).toFixed(2)}–${Number(data?.target_difficulty_max || 0).toFixed(2)}`
  const mode = pacing?.mode ? (t(`pacing_${pacing.mode}`) || pacing.mode) : ''

  if (modulation && pacing) {
    return t('rec_hint_both')
      .replace('{modulation}', modulation)
      .replace('{difficulty}', difficulty)
      .replace('{range}', range)
  }
  if (modulation) return modulation
  if (pacing) return t('rec_hint_pacing').replace('{mode}', mode)
  return t('rec_hint_default')
}

function renderRecommendations(data) {
  const panel = ensurePanel()
  if (!panel) return

  const list = panel.querySelector('.recommended-reading-list')
  const summary = panel.querySelector('.recommended-reading-panel__summary')
  const hint = panel.querySelector('.recommended-reading-panel__hint')
  lastRecommendationData = data
  currentRecommendations = orderRecommendations(data)

  if (!currentRecommendations.length) {
    panel.hidden = true
    return
  }

  const chosen = currentRecommendations[0]
  panel.hidden = false
  const userLevel = data.user_level || t('rec_current_level')
  const minD = Number(data.target_difficulty_min || 0).toFixed(2)
  const maxD = Number(data.target_difficulty_max || 0).toFixed(2)
  summary.textContent = `${userLevel} · ${t('rec_target_difficulty')} ${minD}–${maxD} · ${data.total_mastered || 0} ${t('rec_mastered')}`
  if (hint) hint.textContent = magicalHint(data, chosen)

  const frag = document.createDocumentFragment()
  currentRecommendations.slice(0, 5).forEach((item, index) => {
    const card = document.createElement('article')
    card.className = 'recommended-reading-card'
    if (index === 0) card.classList.add('recommended-reading-card--chosen')
    card.setAttribute('role', 'listitem')

    const title = item.source_title || (item.is_continuation ? t('rec_continue_reading') : t('rec_suggested'))
    const text = passageText(item)
    const focusSentence = item.text || text
    const badge = index === 0
      ? t('rec_next_best')
      : (item.is_continuation ? t('rec_continue') : t('rec_option'))

    card.innerHTML = `
      <div class="recommended-reading-card__meta">
        <span>${escapeHtml(badge)}</span>
        <span>${escapeHtml(item.difficulty_label || t('rec_matched'))}</span>
        <span>${Number(item.difficulty || 0).toFixed(2)}</span>
      </div>
      <h4>${escapeHtml(title)}</h4>
      <p class="recommended-reading-card__text">${escapeHtml(focusSentence)}</p>
      <p class="recommended-reading-card__reason">${escapeHtml(reasonFor(item))}</p>
      <div class="recommended-reading-card__actions">
        <button type="button" class="button-primary recommended-reading-card__study" data-index="${index}">
          ${escapeHtml(t('rec_study'))}
        </button>
      </div>
    `

    frag.appendChild(card)
  })

  list.replaceChildren(frag)
  list.querySelectorAll('.recommended-reading-card__study').forEach(button => {
    button.addEventListener('click', () => {
      const item = currentRecommendations[Number(button.dataset.index)]
      studyRecommendation(item)
    })
  })
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
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

async function loadRecommendations() {
  const language = languageSelect?.value
  const panel = ensurePanel()
  if (!language || !panel) return

  try {
    const response = await fetch(`${API_BASE}/recommend?language=${encodeURIComponent(language)}&limit=12`, {
      headers: getAuthHeaders(),
    })
    if (!response.ok) {
      panel.hidden = true
      return
    }
    const data = await response.json()
    renderRecommendations(data)
  } catch {
    panel.hidden = true
  }
}

function rerenderIfPossible() {
  if (lastRecommendationData) renderRecommendations(lastRecommendationData)
  else loadRecommendations()
}

function init() {
  ensurePanel()
  languageSelect?.addEventListener('change', loadRecommendations)
  document.addEventListener('mnemosyne:memory-updated', loadRecommendations)
  document.addEventListener('mnemosyne:difficulty-modulation-changed', rerenderIfPossible)
  document.addEventListener('mnemosyne:pacing-updated', rerenderIfPossible)
  document.addEventListener('mnemosyne:language-changed', rerenderIfPossible)
  loadRecommendations()
  setInterval(loadRecommendations, 5 * 60_000)
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
