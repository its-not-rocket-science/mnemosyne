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

// Carries FSRS state across multiple ratings of the same object in one session.
const reviewStateByObject = new Map()

// ── Language capabilities ─────────────────────────────────────────────────────
// Populated from GET /languages on page load.
// Maps language code → { code, display_name, direction, script_family, … }
const languageCapabilities = new Map()

async function loadLanguages() {
  try {
    const response = await fetch(`${API_BASE}/languages`)
    if (!response.ok) throw new Error(`GET /languages failed (${response.status})`)
    const languages = await response.json()

    // Populate the capabilities map.
    for (const caps of languages) {
      languageCapabilities.set(caps.code, caps)
    }

    // Replace the loading placeholder with real options.
    // Preserve the currently selected value if it happens to be in the list.
    const current = languageSelect.value
    languageSelect.removeAttribute('aria-busy')
    languageSelect.replaceChildren(
      ...languages.map((caps) => {
        const opt = document.createElement('option')
        opt.value = caps.code
        opt.textContent = caps.display_name
        if (caps.code === current || (current === '' && caps.code === 'es')) {
          opt.selected = true
        }
        return opt
      })
    )
  } catch {
    // On error, fall back to a static minimal list so the form stays usable.
    languageSelect.removeAttribute('aria-busy')
    languageSelect.replaceChildren()
    ;[['es', 'Spanish'], ['en', 'English (stub)']].forEach(([code, name]) => {
      const opt = document.createElement('option')
      opt.value = code
      opt.textContent = name
      languageSelect.appendChild(opt)
    })
  }
}

// Load language list as soon as the module executes.
loadLanguages()


// ── Status helper ─────────────────────────────────────────────────────────────
// Writes to the role="status" live region.  The clear-then-set pattern ensures
// screen readers announce the new message even when the text is unchanged.

function setStatus(message, state = 'idle') {
  status.textContent = ''
  queueMicrotask(() => {
    status.textContent = message
    status.dataset.state = state  // 'idle' | 'busy' | 'error'
  })
}


// ── Results empty state ───────────────────────────────────────────────────────
// resultsEmpty is always an orphaned node that is moved in/out of #results
// by the helpers below.  It is never cloned, so one reference suffices.

function showResultsMessage(message) {
  resultsEmpty.textContent = message
  // replaceChildren re-parents the node if it was detached; no-op if already there.
  results.replaceChildren(resultsEmpty)
}

function hideResultsMessage() {
  // Remove from DOM without destroying the reference.
  resultsEmpty.remove()
}


// ── Parse form ────────────────────────────────────────────────────────────────

form.addEventListener('submit', async (event) => {
  event.preventDefault()

  // Clear any previous validation state on every submission attempt.
  textarea.removeAttribute('aria-invalid')

  const text = textarea.value.trim()
  if (!text) {
    // aria-invalid="true" tells AT the field is in an error state.
    // aria-describedby="status" (set in HTML) then surfaces the message
    // when focus lands on the textarea.
    textarea.setAttribute('aria-invalid', 'true')
    setStatus('Please enter some text to parse.', 'error')
    textarea.focus()
    return
  }

  // Reset previous session.
  reviewStateByObject.clear()
  showResultsMessage('Loading…')
  setStatus('Parsing text…', 'busy')

  submitButton.disabled = true
  submitButton.setAttribute('aria-busy', 'true')
  const originalLabel = submitButton.textContent.trim()
  submitButton.textContent = 'Parsing…'

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
      showResultsMessage('No learnable items found — try pasting a longer passage.')
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
// Delegated to #results so it catches events from all pill descendants.
// lesson-open is dispatched with composed:true so it crosses the shadow-DOM
// boundary and reaches the light DOM.

results.addEventListener('lesson-open', async (event) => {
  const { objectId, language } = event.detail

  setStatus('Loading lesson…', 'busy')

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
      onRate:   submitReview,
      onSpeak:  (text) => speakText(text, language),
    })

    setStatus(`Lesson open: ${lesson.title}.`)
  } catch (error) {
    setStatus(error instanceof Error ? error.message : 'Failed to load lesson.', 'error')
  }
})


// ── Render sentence cards ─────────────────────────────────────────────────────

function renderResults(sentences, language) {
  const fragment = document.createDocumentFragment()
  const caps = languageCapabilities.get(language)
  // direction and lang tag for target-language text.  Fall back to "ltr" if
  // capabilities haven't loaded yet (e.g. /languages failed).
  const dir  = caps?.direction ?? 'ltr'

  for (const sentence of sentences) {
    const article = document.createElement('article')
    article.className = 'sentence-card'

    const textEl = document.createElement('p')
    textEl.className = 'sentence-card__text'
    textEl.textContent = sentence.text  // textContent — never innerHTML
    // Apply language and direction so AT announces the text correctly and
    // the browser applies script-appropriate shaping and line-breaking.
    textEl.setAttribute('lang', language)
    textEl.setAttribute('dir',  dir)

    // Use <ul>/<li> for semantic list semantics; AT announces item count.
    const list = document.createElement('ul')
    list.className = 'sentence-card__pills'
    // Pill labels are target-language text too; match direction of the text.
    list.setAttribute('dir', dir)

    for (const item of sentence.learnable_objects) {
      const li = document.createElement('li')
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

  // Replace everything in #results (detaches resultsEmpty if present).
  results.replaceChildren(fragment)
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

function speakText(text, language) {
  if (!text || !('speechSynthesis' in window)) return
  const utterance = new SpeechSynthesisUtterance(text)
  if (language) utterance.lang = language
  window.speechSynthesis.cancel()  // stop any ongoing speech first
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
