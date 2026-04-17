import '../components/mnemosyne-pill.js'
import '../components/mnemosyne-modal.js'
import { initAuth, getAuthHeaders } from './auth.js'
import {
  queueReview,
  getPendingReviews,
  deleteReview,
  countPendingReviews,
} from './offline.js'

const API_BASE = 'http://localhost:8000'

// ── DOM references ────────────────────────────────────────────────────────────

const form           = document.querySelector('#parse-form')
const languageSelect = document.querySelector('#language')
const sourceTitleInput = document.querySelector('#source-title')
const sourceUrlInput = document.querySelector('#source-url')
const fetchUrlBtn    = document.querySelector('#fetch-url-btn')
const fetchUrlHint   = document.querySelector('#fetch-url-hint')
const fileInput      = document.querySelector('#file-input')
const fileInfo       = document.querySelector('#file-info')
const textarea       = document.querySelector('#source-text')
const submitButton   = document.querySelector('#parse-submit')
const results        = document.querySelector('#results')
const resultsEmpty   = document.querySelector('.results-empty')
const status         = document.querySelector('#status')
const modal          = document.querySelector('#lesson-modal')
const resultsToolbar = document.querySelector('#results-toolbar')

// Carries FSRS state across multiple ratings of the same object in one session.
const reviewStateByObject = new Map()

// Tracks whether the current textarea content came from a file upload.
// Reset to 'pasted_text' whenever the user edits the textarea directly.
let currentContentType = 'pasted_text'
let currentFilename    = null

// True once the user has manually changed the language select; prevents
// auto-detection from overriding an explicit user choice.
// Reset when new text is imported from a URL or file.
let languageUserSelected = false

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

// ── File input ────────────────────────────────────────────────────────────────
// Reads a .txt file into the textarea and records the filename for the
// ingest payload.  The textarea remains the editing surface — the user can
// review and edit the loaded text before submitting.

const MAX_FILE_BYTES = 1_048_576  // 1 MiB

if (fileInput) {
  fileInput.addEventListener('change', () => {
    const file = fileInput.files?.[0]
    if (!file) return

    // Validate type and size client-side before reading.
    const isPlainText = file.type === 'text/plain' || file.name.endsWith('.txt')
    if (!isPlainText) {
      setFileInfo('Only .txt files are supported.', 'error')
      fileInput.value = ''
      return
    }
    if (file.size > MAX_FILE_BYTES) {
      setFileInfo(`File is too large (${(file.size / 1024).toFixed(0)} KB). Maximum is 1 MB.`, 'error')
      fileInput.value = ''
      return
    }

    const reader = new FileReader()
    reader.onload = (evt) => {
      const text = evt.target.result
      textarea.value = text
      textarea.removeAttribute('aria-invalid')
      currentContentType  = 'uploaded_file'
      currentFilename     = file.name
      languageUserSelected = false  // fresh import: allow auto-detection

      // Pre-fill the title with the filename (minus extension) if the user
      // hasn't already typed a title.
      if (sourceTitleInput && !sourceTitleInput.value.trim()) {
        sourceTitleInput.value = file.name.replace(/\.[^.]+$/, '')
      }

      setFileInfo(`Loaded: ${escapeHtml(file.name)} (${(file.size / 1024).toFixed(1)} KB)`)
      scheduleLanguageDetection()
    }
    reader.onerror = () => {
      setFileInfo('Could not read the file. Try copying the text manually.', 'error')
      currentContentType = 'pasted_text'
      currentFilename    = null
    }
    reader.readAsText(file, 'utf-8')
  })
}

// Reset content_type when user edits the textarea directly, then schedule
// a debounced language-detection call.
if (textarea) {
  textarea.addEventListener('input', () => {
    if (currentContentType === 'uploaded_file') {
      currentContentType = 'pasted_text'
      currentFilename    = null
      setFileInfo('')
    }
    scheduleLanguageDetection()
  })
}

function setFileInfo(message, state = 'idle') {
  if (!fileInfo) return
  fileInfo.textContent = message
  fileInfo.dataset.state = state  // 'idle' | 'error'
}


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
// Mark languageUserSelected so auto-detection respects the manual choice.
languageSelect.addEventListener('change', () => {
  languageUserSelected = true
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


// ── URL fetch ─────────────────────────────────────────────────────────────────
// Calls POST /fetch-url to retrieve a page server-side and populate the
// textarea.  The browser makes no cross-origin request to the remote URL.

function setFetchUrlHint(message, state = 'idle') {
  if (!fetchUrlHint) return
  fetchUrlHint.textContent = message
  fetchUrlHint.dataset.state = state   // 'idle' | 'busy' | 'error'
}

if (fetchUrlBtn) {
  fetchUrlBtn.addEventListener('click', async () => {
    const url = sourceUrlInput?.value.trim()
    if (!url) {
      sourceUrlInput?.focus()
      setFetchUrlHint('Enter a URL first.', 'error')
      return
    }

    fetchUrlBtn.disabled = true
    fetchUrlBtn.setAttribute('aria-busy', 'true')
    const originalLabel = fetchUrlBtn.textContent.trim()
    fetchUrlBtn.textContent = 'Fetching\u2026'
    setFetchUrlHint('Fetching page\u2026', 'busy')
    setStatus('Fetching text from URL\u2026', 'busy')

    try {
      const response = await fetch(`${API_BASE}/fetch-url`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body:    JSON.stringify({ source_url: url }),
      })

      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(body?.detail ?? `Fetch failed (${response.status})`)
      }

      const data = await response.json()

      textarea.value = data.text
      textarea.removeAttribute('aria-invalid')
      currentContentType   = 'article'
      currentFilename      = null
      languageUserSelected = false   // fresh import: allow auto-detection
      setFileInfo('')

      // Pre-fill the title if the user hasn't typed one and the page has one.
      if (sourceTitleInput && !sourceTitleInput.value.trim() && data.title) {
        sourceTitleInput.value = data.title
      }

      const chars = data.char_count.toLocaleString()

      // Apply the language detection bundled with the fetch result.
      if (data.detected_language) {
        const option = [...languageSelect.options].find(o => o.value === data.detected_language)
        if (option) {
          languageSelect.value = data.detected_language
          syncCurrentCaps()
          setStatus(
            `Fetched ${chars} characters. Language detected: ${option.text}.`
          )
        } else {
          // Language detected but no plugin — report without changing select.
          setStatus(
            `Fetched ${chars} characters. ` +
            `Detected language '${data.detected_language}' has no plugin.`
          )
        }
      } else {
        setStatus(`Fetched ${chars} characters.`)
      }

      setFetchUrlHint(`${chars} characters extracted.`)
      textarea.focus()
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Fetch failed.'
      setFetchUrlHint(msg, 'error')
      setStatus(msg, 'error')
    } finally {
      fetchUrlBtn.disabled = false
      fetchUrlBtn.removeAttribute('aria-busy')
      fetchUrlBtn.textContent = originalLabel
    }
  })
}


// ── Language auto-detection ───────────────────────────────────────────────────
// Debounced: fires 600 ms after the last textarea change.
// Skipped when the user has manually set the language select.
// Calls POST /detect-language; updates the select only when confidence is
// high enough and the detected language has a registered plugin.

const _DETECT_DEBOUNCE_MS = 600
const _DETECT_MIN_CHARS   = 50
let   _detectTimer        = null

function scheduleLanguageDetection() {
  clearTimeout(_detectTimer)
  _detectTimer = setTimeout(_runLanguageDetection, _DETECT_DEBOUNCE_MS)
}

async function _runLanguageDetection() {
  const text = textarea?.value.trim() ?? ''
  if (text.length < _DETECT_MIN_CHARS) return
  if (languageUserSelected) return

  try {
    const response = await fetch(`${API_BASE}/detect-language`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ text }),
    })
    if (!response.ok) return

    const data = await response.json()
    if (!data.language) return

    const currentCode = languageSelect.value
    if (data.language === currentCode) return  // already correct — no-op

    if (data.supported) {
      // Update the select and announce the change.
      languageSelect.value = data.language
      syncCurrentCaps()
      const name = languageSelect.options[languageSelect.selectedIndex]?.text ?? data.language
      setStatus(`Language detected: ${name}.`)
    } else {
      // Detected but unsupported — announce without touching the select.
      setStatus(`Detected language '${data.language}' has no plugin in this deployment.`)
    }
  } catch {
    // Detection failure is silent — it is always best-effort.
  }
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
    const language = languageSelect.value
    const payload = {
      language,
      text,
      content_type: currentContentType,
      title:        sourceTitleInput?.value.trim() || null,
      source_url:   sourceUrlInput?.value.trim() || null,
      filename:     currentFilename || null,
    }

    const response = await fetch(`${API_BASE}/ingest`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
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

    renderResults(data.sentences, language)
    const n = data.sentences.length

    // Surface any non-fatal validation warnings (e.g. script mismatch) in
    // the status region before the success count so they don't get buried.
    if (data.warnings?.length) {
      setStatus(data.warnings[0], 'error')
      // Delay the success message so the warning is announced first.
      setTimeout(() => {
        setStatus(`${n} sentence${n !== 1 ? 's' : ''} parsed. Use Tab to navigate the items.`)
      }, 4000)
    } else {
      setStatus(`${n} sentence${n !== 1 ? 's' : ''} parsed. Use Tab to navigate the items.`)
    }
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
  const fragment   = document.createDocumentFragment()
  const caps       = languageCapabilities.get(language)
  const dir        = caps?.direction       ?? 'ltr'
  const tokenMode  = caps?.tokenization_mode ?? 'whitespace'
  const scriptFam  = caps?.script_family   ?? 'latin'

  for (const sentence of sentences) {
    const article = document.createElement('article')
    article.className = 'sentence-card'
    // Expose tokenization mode on the card so CSS can adjust pill layout for
    // segmented scripts (CJK, Thai) where tokens have no natural whitespace.
    article.dataset.tokenization = tokenMode

    const textEl = document.createElement('p')
    textEl.className = 'sentence-card__text'
    textEl.textContent = sentence.text   // textContent — never innerHTML
    // lang + dir: correct AT announcement, font shaping, and line-breaking.
    textEl.setAttribute('lang', language)
    textEl.setAttribute('dir',  dir)
    // data-tokenization: drives word-break CSS for segmented / character scripts.
    textEl.dataset.tokenization = tokenMode
    // data-script-family: CSS hook for font/layout rules when lang selectors
    // do not match (e.g. private-use codes like x-rtl-test, x-cjk-test).
    textEl.dataset.scriptFamily = scriptFam
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
      // dir forwarded so the pill can apply correct lang/dir to its button.
      pill.setAttribute('dir',       dir)
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
  const body = {
    object_id:    objectId,
    quality,
    review_state: reviewStateByObject.get(objectId) ?? null,
  }

  let response
  try {
    response = await fetch(`${API_BASE}/review`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body:    JSON.stringify(body),
    })
  } catch {
    // Network unreachable — queue locally and return null so the modal shows
    // "Review saved." rather than an error.
    await queueReview({ ...body, queued_at: Date.now() })
    updateOfflineBadge()
    return null
  }

  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new Error(detail?.detail ?? `Review failed (${response.status})`)
  }

  const payload = await response.json()
  reviewStateByObject.set(objectId, payload.review_state)
  return payload
}


// ── Offline review queue ──────────────────────────────────────────────────────

const offlineBadge      = document.querySelector('#offline-badge')
const offlineCountEl    = document.querySelector('#offline-count')
const offlinePluralEl   = document.querySelector('#offline-plural')

async function updateOfflineBadge() {
  if (!offlineBadge) return
  const n = await countPendingReviews()
  if (n === 0) {
    offlineBadge.hidden = true
    return
  }
  offlineCountEl.textContent  = String(n)
  offlinePluralEl.textContent = n === 1 ? '' : 's'
  offlineBadge.hidden = false
}

async function drainReviewQueue() {
  const pending = await getPendingReviews()
  if (!pending.length) return

  let synced = 0
  for (const { key, value } of pending) {
    try {
      const response = await fetch(`${API_BASE}/review`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body:    JSON.stringify({
          object_id:    value.object_id,
          quality:      value.quality,
          review_state: value.review_state ?? null,
        }),
      })
      if (response.ok) {
        await deleteReview(key)
        synced++
      } else {
        break  // server error — stop and retry later
      }
    } catch {
      break  // still offline
    }
  }

  if (synced > 0) updateOfflineBadge()
}

// Attempt to drain whenever the device goes back online.
window.addEventListener('online', drainReviewQueue)

// Show badge for any reviews queued in a previous session.
updateOfflineBadge()


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


// ── Auth init ─────────────────────────────────────────────────────────────────
// Must run after all DOM references above are established.
// Shows the auth panel or the app depending on sessionStorage state.

initAuth()
