import '../components/mnemosyne-pill.js'
import '../components/mnemosyne-modal.js'

const API_BASE = 'http://localhost:8000'

// ── DOM references ────────────────────────────────────────────────────────────

const form           = document.querySelector('#parse-form')
const languageSelect = document.querySelector('#language')
const sourceUrlInput = document.querySelector('#source-url')
const textarea       = document.querySelector('#source-text')
const submitButton   = document.querySelector('#parse-submit')
const results        = document.querySelector('#results')
const resultsEmpty   = document.querySelector('.results-empty')
const status         = document.querySelector('#status')
const modal          = document.querySelector('#lesson-modal')
const resultsToolbar = document.querySelector('#results-toolbar')

// Carries FSRS state across multiple ratings of the same object in one session.
const reviewStateByObject = new Map()

// ── Language capabilities ─────────────────────────────────────────────────────
// Populated from GET /languages on page load.
// Maps language code → LanguageCapabilities object from the backend schema.
const languageCapabilities = new Map()

// Currently selected language capabilities — updated whenever the select changes.
let currentCaps = null

// Script view state for the results panel.
// 'native'    — show source script only (default)
// 'romanized' — show romanized/transliterated form only
// 'both'      — show both layers side by side
// Only active when currentCaps.transliteration_scheme is set.
let scriptView = 'native'

async function loadLanguages() {
  try {
    const response = await fetch(`${API_BASE}/languages`)
    if (!response.ok) throw new Error(`GET /languages failed (${response.status})`)
    const languages = await response.json()

    for (const caps of languages) {
      languageCapabilities.set(caps.code, caps)
    }

    // Replace the loading placeholder with real options.
    // Preserve any prior selection; otherwise default to the first in the list.
    const current = languageSelect.value
    let firstSet  = false
    languageSelect.removeAttribute('aria-busy')
    languageSelect.replaceChildren(
      ...languages.map((caps) => {
        const opt = document.createElement('option')
        opt.value = caps.code
        opt.textContent = caps.display_name
        if (caps.code === current || (!firstSet && current === '')) {
          opt.selected = true
          firstSet = true
        }
        return opt
      })
    )
  } catch {
    // On error, show a minimal static fallback so the form stays usable.
    languageSelect.removeAttribute('aria-busy')
    languageSelect.replaceChildren()
    ;[['es', 'Spanish'], ['en', 'English (stub)'], ['fr', 'French (stub)']].forEach(([code, name]) => {
      const opt = document.createElement('option')
      opt.value = code
      opt.textContent = name
      languageSelect.appendChild(opt)
    })
  }

  // Sync currentCaps after options are settled.
  syncCurrentCaps()
}

loadLanguages()

// Re-sync whenever the user changes the language.
languageSelect.addEventListener('change', () => {
  scriptView = 'native'  // reset view for the new language
  syncCurrentCaps()
})

function syncCurrentCaps() {
  currentCaps = languageCapabilities.get(languageSelect.value) ?? null
  updateScriptViewToolbar()
}


// ── Script view toolbar ───────────────────────────────────────────────────────
// Only shown for languages that declare a transliteration_scheme, since that
// is the prerequisite for romanized output existing in the lesson data.

function updateScriptViewToolbar() {
  if (!resultsToolbar) return
  const supported = Boolean(currentCaps?.transliteration_scheme)
  resultsToolbar.hidden = !supported
  if (!supported) return

  // Build toggle group on first show; re-use on subsequent calls.
  let group = resultsToolbar.querySelector('.script-toggle')
  if (!group) {
    group = buildScriptToggleGroup()
    resultsToolbar.appendChild(group)
  }
  syncScriptToggleUI(group)
}

function buildScriptToggleGroup() {
  const group = document.createElement('div')
  group.className = 'script-toggle'
  group.setAttribute('role', 'group')
  group.setAttribute('aria-label', 'Script view')

  const label = document.createElement('span')
  label.className = 'script-toggle__label'
  label.textContent = 'View:'
  label.setAttribute('aria-hidden', 'true')
  group.appendChild(label)

  for (const { value, text } of [
    { value: 'native',    text: 'Script' },
    { value: 'romanized', text: 'Romanized' },
    { value: 'both',      text: 'Both' },
  ]) {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'script-toggle__btn'
    btn.dataset.view = value
    btn.textContent = text
    btn.addEventListener('click', () => {
      scriptView = value
      syncScriptToggleUI(group)
      applyScriptViewToResults()
    })
    group.appendChild(btn)
  }

  return group
}

function syncScriptToggleUI(group) {
  group.querySelectorAll('.script-toggle__btn').forEach((btn) => {
    const active = btn.dataset.view === scriptView
    btn.setAttribute('aria-pressed', String(active))
    btn.classList.toggle('script-toggle__btn--active', active)
  })
}

function applyScriptViewToResults() {
  results.dataset.scriptView = scriptView
}


// ── Status helper ─────────────────────────────────────────────────────────────
// Clear-then-set ensures screen readers re-announce even identical messages.

function setStatus(message, state = 'idle') {
  status.textContent = ''
  queueMicrotask(() => {
    status.textContent = message
    status.dataset.state = state   // 'idle' | 'busy' | 'error'
  })
}


// ── Results empty state ───────────────────────────────────────────────────────
// resultsEmpty is a persistent orphan node moved in/out of #results.

function showResultsMessage(message) {
  resultsEmpty.textContent = message
  results.replaceChildren(resultsEmpty)
}

function hideResultsMessage() {
  resultsEmpty.remove()
}


// ── Parse form ────────────────────────────────────────────────────────────────

form.addEventListener('submit', async (event) => {
  event.preventDefault()

  textarea.removeAttribute('aria-invalid')

  const text = textarea.value.trim()
  if (!text) {
    textarea.setAttribute('aria-invalid', 'true')
    setStatus('Please enter some text to parse.', 'error')
    textarea.focus()
    return
  }

  reviewStateByObject.clear()
  showResultsMessage('Loading\u2026')
  setStatus('Parsing text\u2026', 'busy')

  submitButton.disabled = true
  submitButton.setAttribute('aria-busy', 'true')
  const originalLabel = submitButton.textContent.trim()
  submitButton.textContent = 'Parsing\u2026'

  try {
    const payload = {
      language:   languageSelect.value,
      text,
      source_url: sourceUrlInput?.value.trim() || null,
    }

    const response = await fetch(`${API_BASE}/parse`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify(payload),
    })

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail ?? `Parse failed (${response.status})`)
    }

    const data = await response.json()

    if (data.sentences.length === 0) {
      showResultsMessage('No learnable items found \u2014 try pasting a longer passage.')
      setStatus('No sentences found.')
      return
    }

    renderResults(data.sentences, payload.language)
    const n = data.sentences.length
    setStatus(`${n} sentence${n !== 1 ? 's' : ''} parsed. Use Tab to navigate the items.`)
  } catch (error) {
    showResultsMessage('An error occurred. Please try again.')
    setStatus(error instanceof Error ? error.message : 'Parsing failed.', 'error')
  } finally {
    submitButton.disabled = false
    submitButton.removeAttribute('aria-busy')
    submitButton.textContent = originalLabel
  }
})


// ── Lesson open ───────────────────────────────────────────────────────────────
// Delegated to #results; lesson-open is dispatched with composed:true so it
// crosses the shadow-DOM boundary and reaches the light DOM.

results.addEventListener('lesson-open', async (event) => {
  const { objectId, language } = event.detail
  const caps   = languageCapabilities.get(language)
  const ttsTag = caps?.tts_lang_tag ?? language

  setStatus('Loading lesson\u2026', 'busy')

  try {
    const url = `${API_BASE}/lesson/${encodeURIComponent(objectId)}?language=${encodeURIComponent(language)}`
    const response = await fetch(url)

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail ?? `Lesson not available (${response.status})`)
    }

    const lesson = await response.json()

    modal.open({
      lesson,
      objectId: lesson.id,
      caps,
      language,
      onRate:  submitReview,
      onSpeak: (text) => speakText(text, ttsTag),
    })

    setStatus(`Lesson open: ${lesson.title}.`)
  } catch (error) {
    setStatus(error instanceof Error ? error.message : 'Failed to load lesson.', 'error')
  }
})


// ── Render sentence cards ─────────────────────────────────────────────────────

function renderResults(sentences, language) {
  const fragment = document.createDocumentFragment()
  const caps      = languageCapabilities.get(language)
  const dir       = caps?.direction ?? 'ltr'
  const tokenMode = caps?.tokenization_mode ?? 'whitespace'

  for (const sentence of sentences) {
    const article = document.createElement('article')
    article.className = 'sentence-card'

    const textEl = document.createElement('p')
    textEl.className = 'sentence-card__text'
    textEl.textContent = sentence.text   // textContent — never innerHTML
    // lang + dir: correct AT announcement, font shaping, and line-breaking.
    textEl.setAttribute('lang', language)
    textEl.setAttribute('dir',  dir)
    // data-tokenization: drives word-break CSS for segmented / character scripts.
    textEl.dataset.tokenization = tokenMode
    // data-layer: consumed by script-view CSS when transliteration is toggled.
    textEl.dataset.layer = 'native'

    const list = document.createElement('ul')
    list.className = 'sentence-card__pills'
    // Pill labels are target-language text; match text direction.
    list.setAttribute('dir', dir)

    for (const item of sentence.learnable_objects) {
      const li   = document.createElement('li')
      const pill = document.createElement('mnemosyne-pill')
      pill.setAttribute('type',      item.type)
      pill.setAttribute('label',     item.label)
      pill.setAttribute('object-id', item.id)
      pill.setAttribute('language',  language)
      li.appendChild(pill)
      list.appendChild(li)
    }

    article.append(textEl, list)
    fragment.appendChild(article)
  }

  results.replaceChildren(fragment)

  // Apply current script-view and toolbar state to the new cards.
  applyScriptViewToResults()
  updateScriptViewToolbar()
}


// ── Review submission ─────────────────────────────────────────────────────────

async function submitReview(objectId, quality) {
  const response = await fetch(`${API_BASE}/review`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({
      object_id:    objectId,
      quality,
      review_state: reviewStateByObject.get(objectId) ?? null,
    }),
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new Error(body?.detail ?? `Review failed (${response.status})`)
  }

  const payload = await response.json()
  reviewStateByObject.set(objectId, payload.review_state)
  return payload
}


// ── Text-to-speech ────────────────────────────────────────────────────────────
// langTag should be caps.tts_lang_tag ?? language — callers are responsible
// for resolving the right BCP-47 tag before calling here.

function speakText(text, langTag) {
  if (!text || !('speechSynthesis' in window)) return
  const utterance = new SpeechSynthesisUtterance(text)
  if (langTag) utterance.lang = langTag
  window.speechSynthesis.cancel()   // stop any ongoing speech first
  window.speechSynthesis.speak(utterance)
}


// ── HTML escaping ─────────────────────────────────────────────────────────────

function escapeHtml(value) {
  return String(value)
    .replaceAll('&',  '&amp;')
    .replaceAll('<',  '&lt;')
    .replaceAll('>',  '&gt;')
    .replaceAll('"',  '&quot;')
    .replaceAll("'", '&#39;')
}
