/*
  Autonomous Learning Mode

  Integrates:
  - difficulty modulation (what to load)
  - cognitive pacing (when to load)
*/

import { getAuthHeaders } from './auth.js'
import { t } from './i18n.js'

const API = 'http://localhost:8000'

let enabled = false
let loading = false
let languageSelect, pickerTextarea, pickerUseBtn, resultsSection, liveRegion

function announce(msg) {
  if (liveRegion) liveRegion.textContent = msg
}

function createToggle() {
  // Add autonomous toggle to the adaptive bar (created by difficulty-modulation.js).
  // If bar isn't ready yet, wait for it.
  function insertToggle() {
    const bar = document.querySelector('#results-adaptive-bar')
    if (!bar || document.querySelector('#autonomous-mode-toggle')) return

    const row = document.createElement('div')
    row.className = 'results-adaptive-bar__autonomous'

    const btn = document.createElement('button')
    btn.id = 'autonomous-mode-toggle'
    btn.type = 'button'
    btn.className = 'ghost-button ghost-button--small'
    btn.setAttribute('data-i18n', 'autonomous_label')
    btn.setAttribute('aria-pressed', 'false')
    btn.textContent = t('autonomous_label')

    const hint = document.createElement('span')
    hint.className = 'results-adaptive-bar__autonomous-hint'
    hint.setAttribute('data-i18n', 'autonomous_hint')
    hint.textContent = t('autonomous_hint')

    btn.addEventListener('click', () => {
      enabled = !enabled
      btn.setAttribute('aria-pressed', String(enabled))
      // Override data-i18n key based on state so language switch picks correct key.
      btn.setAttribute('data-i18n', enabled ? 'autonomous_on' : 'autonomous_label')
      btn.textContent = enabled ? t('autonomous_on') : t('autonomous_label')
      announce(enabled ? t('autonomous_on') : t('autonomous_label'))
      if (enabled) preloadNext()
    })

    row.append(btn, hint)
    bar.appendChild(row)
  }

  insertToggle()
  if (!document.querySelector('#autonomous-mode-toggle')) {
    const obs = new MutationObserver(() => {
      if (document.querySelector('#results-adaptive-bar')) {
        insertToggle()
        obs.disconnect()
      }
    })
    obs.observe(document.body, { childList: true, subtree: true })
  }
}

async function fetchNext() {
  const lang = languageSelect?.value
  if (!lang) return null

  const res = await fetch(`${API}/recommend?language=${lang}&limit=12`, {
    headers: getAuthHeaders(),
  })

  if (!res.ok) return null
  const data = await res.json()

  return window.mnemosyneDifficulty?.chooseRecommendation?.(data) || data.sentences?.[0] || null
}

function passageText(item) {
  if (!item) return ''
  if (Array.isArray(item.passage)) {
    return item.passage.map(s => s.text).join(' ')
  }
  return item.text
}

async function loadNext() {
  if (!enabled || loading) return
  loading = true
  announce('Loading next passage…')

  try {
    const next = await fetchNext()
    if (!next || !pickerTextarea || !pickerUseBtn) return

    const text = passageText(next)
    if (!text) return

    document.body.classList.add('mnemosyne-transitioning-passage')

    pickerTextarea.value = text
    pickerTextarea.dispatchEvent(new Event('input', { bubbles: true }))
    pickerUseBtn.click()

    if (next.source_document_id) {
      fetch(`${API}/reading/${next.source_document_id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ sentences_read: 1 }),
      }).catch(() => {})
    }

    setTimeout(() => {
      document.body.classList.remove('mnemosyne-transitioning-passage')
    }, 900)
  } catch {
    announce('Could not load next passage')
  } finally {
    loading = false
  }
}

function observeEnd() {
  if (!resultsSection) return
  const sentinel = document.createElement('div')
  sentinel.style.height = '1px'
  resultsSection.appendChild(sentinel)

  const observer = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting && enabled) {
      const delay = window.mnemosynePacing?.getNextDelayMs?.() || 1800
      setTimeout(loadNext, delay)
    }
  }, { threshold: 1 })

  observer.observe(sentinel)
}

function preloadNext() {
  fetchNext().catch(() => {})
}

function init() {
  languageSelect  = document.querySelector('#language')
  pickerTextarea  = document.querySelector('#picker-text')
  pickerUseBtn    = document.querySelector('#picker-use-btn')
  resultsSection  = document.querySelector('#results-section')
  liveRegion      = document.querySelector('#a11y-live')

  createToggle()
  observeEnd()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
