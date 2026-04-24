import '../components/mnemosyne-pill.js'
import '../components/mnemosyne-modal.js'
import '../components/mnemosyne-detail-pane.js'
import '../components/mnemosyne-player.js'
import { initAuth, getAuthHeaders } from './auth.js'
import { playbackEngine } from './playback.js'
import {
  queueReview,
  getPendingReviews,
  deleteReview,
  countPendingReviews,
} from './offline.js'
import { initUiLanguage, t, ti } from './i18n.js'
import { openDetail, closeDetail } from './layout.js'

initUiLanguage()

const API_BASE = 'http://localhost:8000'

// ── DOM references ────────────────────────────────────────────────────────────

const languageSelect    = document.querySelector('#language')
const chooseTextBtn     = document.querySelector('#choose-text-btn')
const changeTextBtn     = document.querySelector('#change-text-btn')
const chosenTextDisplay = document.querySelector('#chosen-text-display')
const saveLessonBtn     = document.querySelector('#save-lesson-btn')
const results           = document.querySelector('#results')
const resultsEmpty      = document.querySelector('.results-empty')
const status            = document.querySelector('#status')
const modal             = document.querySelector('#lesson-modal')
const detailPane        = document.querySelector('#detail-pane')
const paneBackdrop      = document.querySelector('#pane-backdrop')
const playAllBtn        = document.querySelector('#play-all-btn')
const mainPlayer        = document.querySelector('#main-player')
const resultsToolbar    = document.querySelector('#results-toolbar')
const jobProgressPanel  = document.querySelector('#job-progress')
const jobProgressFill   = document.querySelector('#job-progress-fill')
const jobProgressLabel  = document.querySelector('#job-progress-label')

// Text-picker dialog
const textPickerDialog  = document.querySelector('#text-picker')
const pickerUrlInput    = document.querySelector('#picker-url')
const pickerFetchUrlBtn = document.querySelector('#picker-fetch-url-btn')
const pickerTextarea    = document.querySelector('#picker-text')
const pickerFileInput   = document.querySelector('#picker-file-input')
const pickerUseBtn      = document.querySelector('#picker-use-btn')
const pickerStatus      = document.querySelector('#picker-status')
const pickerCloseBtn    = document.querySelector('#picker-close-btn')

// Save-lesson dialog
const saveLessonDialog     = document.querySelector('#save-lesson-dialog')
const saveTitleInput       = document.querySelector('#save-title')
const saveLessonStatus     = document.querySelector('#save-lesson-status')
const saveLessonCloseBtn   = document.querySelector('#save-lesson-close-btn')
const saveLessonConfirmBtn = document.querySelector('#save-lesson-confirm-btn')

// Reader UI
const readerFilters    = document.querySelector('#reader-filters')
const readerNowPlaying = document.querySelector('#reader-nowplaying')
const rnpToggle        = document.querySelector('#rnp-toggle')
const rnpStop          = document.querySelector('#rnp-stop')
const rnpPrev          = document.querySelector('#rnp-prev')
const rnpNext          = document.querySelector('#rnp-next')
const rnpText          = document.querySelector('#reader-nowplaying .reader-nowplaying__text')
const rnpCounter       = document.querySelector('#reader-nowplaying .reader-nowplaying__counter')


const reviewStateByObject = new Map()
const canSpeak = 'speechSynthesis' in window

// Stores the last-rendered sentences and their TTS tag for playback controls.
let currentSentences = []
let currentTtsTag    = ''

let currentContentType   = 'pasted_text'
let currentFilename      = null
let currentSourceUrl     = null
let languageUserSelected = false
let currentText          = ''   // committed text from picker
let activeFilterTypes    = null // Set<string> when filtered, null = show all

const languageCapabilities = new Map()
let currentCaps = null
let scriptView  = 'native'

const MAX_FILE_BYTES = 1_048_576  // 1 MiB


// ── Defocus on pointer interaction ────────────────────────────────────────────
// Blurs buttons/links after mouse/touch click so focus rings don't linger.
// pointerup never fires for keyboard events, so keyboard nav is unaffected.
document.addEventListener('pointerup', () => {
  setTimeout(() => {
    const el  = document.activeElement
    if (!el || el === document.body) return
    const tag = el.tagName.toLowerCase()
    if (tag === 'button' || tag === 'a') el.blur()
  }, 0)
}, { passive: true })

// Blur select after pointer-driven option selection.
// change fires on every arrow-key press too, so we only blur when the
// interaction was initiated by a pointer (tracked via pointerdown).
const _selectsWithPointerDown = new WeakSet()
document.addEventListener('pointerdown', e => {
  if (e.target.tagName.toLowerCase() === 'select') _selectsWithPointerDown.add(e.target)
}, { passive: true })
document.addEventListener('change', e => {
  const el = e.target
  if (el.tagName.toLowerCase() === 'select' && _selectsWithPointerDown.has(el)) {
    _selectsWithPointerDown.delete(el)
    el.blur()
  }
})


// ── Language capabilities ─────────────────────────────────────────────────────

async function loadLanguages() {
  try {
    const response = await fetch(`${API_BASE}/languages`)
    if (!response.ok) throw new Error(`GET /languages failed (${response.status})`)
    const languages = await response.json()

    for (const caps of languages) {
      languageCapabilities.set(caps.code, caps)
    }

    const current = languageSelect.value
    let firstSet  = false
    languageSelect.removeAttribute('aria-busy')
    languageSelect.replaceChildren(
      ...languages.map((caps) => {
        const opt = document.createElement('option')
        opt.value = caps.code
        opt.dataset.lessonLang = caps.code
        const translated = t('lesson_lang_' + caps.code)
        opt.textContent = (translated && translated !== 'lesson_lang_' + caps.code)
          ? translated
          : caps.display_name
        if (caps.code === current || (!firstSet && current === '')) {
          opt.selected = true
          firstSet = true
        }
        return opt
      })
    )
  } catch {
    languageSelect.removeAttribute('aria-busy')
    languageSelect.replaceChildren()
    ;[['es', 'Spanish'], ['en', 'English (stub)'], ['fr', 'French (stub)']].forEach(([code, fallback]) => {
      const opt = document.createElement('option')
      opt.value = code
      opt.dataset.lessonLang = code
      const translated = t('lesson_lang_' + code)
      opt.textContent = (translated && translated !== 'lesson_lang_' + code) ? translated : fallback
      languageSelect.appendChild(opt)
    })
  }

  syncCurrentCaps()
}

loadLanguages()

languageSelect.addEventListener('change', () => {
  languageUserSelected = true
  scriptView = 'native'
  syncCurrentCaps()
})

function syncCurrentCaps() {
  currentCaps = languageCapabilities.get(languageSelect.value) ?? null
  updateScriptViewToolbar()
}


// ── Script view toolbar ───────────────────────────────────────────────────────

function updateScriptViewToolbar() {
  if (!resultsToolbar) return
  const supported = Boolean(currentCaps?.transliteration_scheme)
  resultsToolbar.hidden = !supported
  if (!supported) return

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
  label.dataset.i18n = 'script_view_label'
  label.textContent = t('script_view_label')
  label.setAttribute('aria-hidden', 'true')
  group.appendChild(label)

  for (const value of ['native', 'romanized', 'both']) {
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'script-toggle__btn'
    btn.dataset.view = value
    btn.dataset.i18n = 'script_' + value
    btn.textContent = t('script_' + value)
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


// ── Text-picker dialog ────────────────────────────────────────────────────────

function openPicker() {
  if (currentText && pickerTextarea) pickerTextarea.value = currentText
  textPickerDialog?.showModal()
  pickerTextarea?.focus()
}

chooseTextBtn?.addEventListener('click', openPicker)
changeTextBtn?.addEventListener('click', openPicker)
pickerCloseBtn?.addEventListener('click', () => textPickerDialog?.close())

// File input inside picker
pickerFileInput?.addEventListener('change', () => {
  const file = pickerFileInput.files?.[0]
  if (!file) return

  const isPlainText = file.type === 'text/plain' || file.name.endsWith('.txt')
  if (!isPlainText) {
    setPickerStatus(t('file_type_error'), 'error')
    pickerFileInput.value = ''
    return
  }
  if (file.size > MAX_FILE_BYTES) {
    setPickerStatus(ti('file_too_large', { kb: (file.size / 1024).toFixed(0) }), 'error')
    pickerFileInput.value = ''
    return
  }

  const reader = new FileReader()
  reader.onload = evt => {
    pickerTextarea.value = evt.target.result
    currentContentType   = 'uploaded_file'
    currentFilename      = file.name
    languageUserSelected = false
    setPickerStatus(`Loaded: ${escapeHtml(file.name)} (${(file.size / 1024).toFixed(1)} KB)`)
    scheduleLanguageDetection()
  }
  reader.onerror = () => {
    setPickerStatus(t('file_read_error'), 'error')
    currentContentType = 'pasted_text'
    currentFilename    = null
  }
  reader.readAsText(file, 'utf-8')
})

// URL fetch inside picker
pickerFetchUrlBtn?.addEventListener('click', async () => {
  const url = pickerUrlInput?.value.trim()
  if (!url) {
    pickerUrlInput?.focus()
    setPickerStatus(t('url_empty_error'), 'error')
    return
  }

  pickerFetchUrlBtn.disabled = true
  pickerFetchUrlBtn.setAttribute('aria-busy', 'true')
  const originalLabel = pickerFetchUrlBtn.textContent.trim()
  pickerFetchUrlBtn.textContent = t('fetching')
  setPickerStatus(t('fetch_page_busy'), 'busy')

  try {
    const response = await fetch(`${API_BASE}/fetch-url`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body:    JSON.stringify({ source_url: url }),
    })
    handleStartupWarningHeader(response)
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      if (response.status === 503) checkBackendHealth()
      throw new Error(body?.detail ?? `${t('fetch_failed')} (${response.status})`)
    }

    const data = await response.json()
    pickerTextarea.value = data.text
    currentContentType   = 'article'
    currentFilename      = null
    languageUserSelected = false

    const chars = data.char_count.toLocaleString()
    if (data.detected_language) {
      const option = [...languageSelect.options].find(o => o.value === data.detected_language)
      if (option) {
        languageSelect.value = data.detected_language
        syncCurrentCaps()
        setPickerStatus(ti('fetched_chars_lang', { n: chars, name: option.text }))
      } else {
        setPickerStatus(ti('fetched_chars_no_plugin', { n: chars, lang: data.detected_language }))
      }
    } else {
      setPickerStatus(ti('fetched_chars', { n: chars }))
    }
  } catch (error) {
    const msg = error instanceof Error ? error.message : t('fetch_failed')
    setPickerStatus(msg, 'error')
  } finally {
    pickerFetchUrlBtn.disabled = false
    pickerFetchUrlBtn.removeAttribute('aria-busy')
    pickerFetchUrlBtn.textContent = originalLabel
  }
})

// Textarea edits inside picker
pickerTextarea?.addEventListener('input', () => {
  if (currentContentType === 'uploaded_file') {
    currentContentType = 'pasted_text'
    currentFilename    = null
  }
  setPickerStatus('')
  scheduleLanguageDetection()
})

// Confirm: "Use this text"
pickerUseBtn?.addEventListener('click', () => {
  const text = pickerTextarea?.value.trim() ?? ''
  if (!text) {
    setPickerStatus(t('text_empty_error'), 'error')
    pickerTextarea?.focus()
    return
  }
  currentText      = text
  currentSourceUrl = pickerUrlInput?.value.trim() || null
  textPickerDialog?.close()
  showChosenText(text)
  doParseText(text)
})

function setPickerStatus(message, state = 'idle') {
  if (!pickerStatus) return
  pickerStatus.textContent = message
  pickerStatus.dataset.state = state
}

function showChosenText(text) {
  if (!chosenTextDisplay) return
  const preview = text.length > 300 ? text.slice(0, 300) + '\u2026' : text
  chosenTextDisplay.textContent = preview
  chosenTextDisplay.hidden = false
  if (chooseTextBtn) chooseTextBtn.hidden = true
  if (changeTextBtn) changeTextBtn.hidden = false
}


// ── Save-lesson dialog ────────────────────────────────────────────────────────

saveLessonBtn?.addEventListener('click', () => {
  saveLessonDialog?.showModal()
  saveTitleInput?.focus()
})

saveLessonCloseBtn?.addEventListener('click', () => saveLessonDialog?.close())

saveLessonConfirmBtn?.addEventListener('click', () => {
  const title = saveTitleInput?.value.trim() ?? ''
  if (!title) {
    if (saveLessonStatus) {
      saveLessonStatus.textContent = t('text_empty_error')
      saveLessonStatus.dataset.state = 'error'
    }
    saveTitleInput?.focus()
    return
  }
  // TODO: implement lesson saving
  saveLessonDialog?.close()
})


// ── Language auto-detection ───────────────────────────────────────────────────

const _DETECT_DEBOUNCE_MS = 600
const _DETECT_MIN_CHARS   = 50
let   _detectTimer        = null

function scheduleLanguageDetection() {
  clearTimeout(_detectTimer)
  _detectTimer = setTimeout(_runLanguageDetection, _DETECT_DEBOUNCE_MS)
}

async function _runLanguageDetection() {
  const text = pickerTextarea?.value.trim() ?? ''
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
    if (data.language === currentCode) return

    if (data.supported) {
      languageSelect.value = data.language
      syncCurrentCaps()
      const name = languageSelect.options[languageSelect.selectedIndex]?.text ?? data.language
      setPickerStatus(ti('lang_detected', { name }))
    } else {
      setPickerStatus(ti('lang_no_plugin', { lang: data.language }))
    }
  } catch {
    // Detection failure is silent — always best-effort.
  }
}


// ── Status helper ─────────────────────────────────────────────────────────────

function setStatus(message, state = 'idle') {
  status.textContent = ''
  queueMicrotask(() => {
    status.textContent = message
    status.dataset.state = state
  })
}


// ── Results empty state ───────────────────────────────────────────────────────

function showResultsMessage(message) {
  resultsEmpty.textContent = message
  results.replaceChildren(resultsEmpty)
}

function hideResultsMessage() {
  resultsEmpty.remove()
}


// ── Parse text ────────────────────────────────────────────────────────────────

async function doParseText(text) {
  reviewStateByObject.clear()
  showResultsMessage(t('loading'))
  setStatus(t('parsing_status'), 'busy')
  setJobProgress(2, t('parsing_status'))

  try {
    const language = languageSelect.value
    const data = await parseWithJob(text, language)

    if (data.sentences.length === 0) {
      showResultsMessage(t('no_items_found'))
      setStatus(t('no_sentences_found'))
      if (saveLessonBtn) saveLessonBtn.hidden = true
      return
    }

    renderResults(data.sentences, language)
    const n = data.sentences.length
    const parsedMsg = n === 1 ? t('sentence_parsed_1') : ti('sentences_parsed', { n })
    if (data.warnings?.length) {
      setStatus(data.warnings[0], 'error')
      setTimeout(() => setStatus(parsedMsg), 4000)
    } else {
      setStatus(parsedMsg)
    }
    if (saveLessonBtn) saveLessonBtn.hidden = false
  } catch (error) {
    showResultsMessage(t('parse_error_generic'))
    setStatus(error instanceof Error ? error.message : t('parsing_failed'), 'error')
  } finally {
    setJobProgress(null)
  }
}


// ── Lesson open ───────────────────────────────────────────────────────────────

results.addEventListener('lesson-open', async (event) => {
  const { objectId, language } = event.detail
  const caps   = languageCapabilities.get(language)
  const ttsTag = caps?.tts_lang_tag ?? language
  const dir    = caps?.direction ?? 'ltr'

  // Grab the sentence text for the "In Context" tab before blurring.
  // event.target is the <mnemosyne-pill> host element; traverse light DOM.
  const sentenceCard = event.target?.closest?.('article.sentence-card')
  const sentenceText = sentenceCard?.querySelector('.sentence-card__text')?.textContent ?? ''

  setStatus(t('loading_lesson'), 'busy')

  try {
    const url = `${API_BASE}/lesson/${encodeURIComponent(objectId)}?language=${encodeURIComponent(language)}`
    const response = await fetch(url)

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail ?? `Lesson not available (${response.status})`)
    }

    const lesson = await response.json()

    // Open the detail pane as the primary view.
    // "Study drills" inside the pane delegates to the existing modal.
    if (detailPane) {
      detailPane.show({
        lesson,
        sentenceText,
        language,
        dir,
        ttsTag,
        caps,
        onSpeak:  (text, lang) => speakText(text, lang ?? ttsTag),
        onStudy:  () => modal.open({
          lesson,
          objectId: lesson.id,
          caps,
          language,
          onRate:  submitReview,
          onSpeak: (text) => speakText(text, ttsTag),
        }),
      })
      openDetail()
      paneBackdrop?.classList.add('is-visible')
    } else {
      // Fallback: no detail pane in DOM — open modal directly.
      modal.open({
        lesson,
        objectId: lesson.id,
        caps,
        language,
        onRate:  submitReview,
        onSpeak: (text) => speakText(text, ttsTag),
      })
    }

    setStatus(ti('lesson_open', { title: lesson.title }))
  } catch (error) {
    setStatus(error instanceof Error ? error.message : t('load_lesson_failed'), 'error')
  }
})

// Close handler: collapse the split-pane grid when the pane is dismissed.
detailPane?.addEventListener('pane-close', () => {
  closeDetail()
  paneBackdrop?.classList.remove('is-visible')
})

paneBackdrop?.addEventListener('click', () => detailPane?.hide())


// ── Playback controls ─────────────────────────────────────────────────────────

rnpPrev?.addEventListener('click',   () => playbackEngine.prev())
rnpToggle?.addEventListener('click', () => playbackEngine.togglePause())
rnpStop?.addEventListener('click',   () => playbackEngine.stop())
rnpNext?.addEventListener('click',   () => playbackEngine.next())

playAllBtn?.addEventListener('click', () => {
  if (playbackEngine.state === 'idle') {
    playbackEngine.playAll(
      currentSentences.map(s => ({ text: s.text, langTag: currentTtsTag }))
    )
  } else {
    playbackEngine.stop()
  }
})

playbackEngine.addEventListener('state-change', ({ detail: { state, current, index, total } }) => {
  // Active sentence highlight + per-card button icons
  results?.querySelectorAll('.sentence-card').forEach((card) => {
    const cardIdx = parseInt(card.dataset.sentenceIndex ?? '-1', 10)
    const isActive = state !== 'idle' && current?.index === cardIdx
    card.classList.toggle('sentence-card--playing', isActive)

    const btn  = card.querySelector('.sentence-card__play-btn')
    const icon = btn?.querySelector('.play-icon')
    if (!btn || !icon) return
    const isPlaying = isActive && state === 'playing'
    icon.textContent = isPlaying ? '\u23F8' : '\u25B6'
    btn.setAttribute('aria-label',   isPlaying ? 'Pause' : 'Play sentence')
    btn.setAttribute('aria-pressed', String(isActive))
  })

  // Play-all button label
  if (playAllBtn) {
    playAllBtn.textContent = state === 'idle' ? '\u25B6 Play all' : '\u23F9 Stop'
  }

  // Reader now-playing card
  if (readerNowPlaying) {
    const idle = state === 'idle'
    readerNowPlaying.hidden = idle
    if (!idle && current) {
      if (rnpText)    rnpText.textContent    = current.text
      if (rnpCounter) rnpCounter.textContent = `${index + 1}\u2009/\u2009${total}`
    }
    if (rnpToggle) {
      const isPaused = state === 'paused'
      rnpToggle.textContent = isPaused ? '\u25B6' : '\u23F8'
      rnpToggle.setAttribute('aria-label', isPaused ? 'Resume' : 'Pause')
    }
  }
})


// ── Render sentence cards ─────────────────────────────────────────────────────

function renderResults(sentences, language) {
  const fragment  = document.createDocumentFragment()
  const caps      = languageCapabilities.get(language)
  const dir       = caps?.direction         ?? 'ltr'
  const tokenMode = caps?.tokenization_mode ?? 'whitespace'
  const scriptFam = caps?.script_family     ?? 'latin'
  const ttsTag    = caps?.tts_lang_tag ?? language

  currentSentences = sentences
  currentTtsTag    = ttsTag

  for (const [sentenceIdx, sentence] of sentences.entries()) {
    const article = document.createElement('article')
    article.className = 'sentence-card reader-sentence'
    article.dataset.tokenization  = tokenMode
    article.dataset.sentenceIndex = sentenceIdx

    const layout = document.createElement('div')
    layout.className = 'reader-sentence__layout'

    const gutter = document.createElement('div')
    gutter.className = 'reader-sentence__gutter'

    if (canSpeak) {
      const playBtn = document.createElement('button')
      playBtn.type      = 'button'
      playBtn.className = 'reader-gutter-btn sentence-card__play-btn'
      playBtn.setAttribute('aria-label',   'Play sentence')
      playBtn.setAttribute('aria-pressed', 'false')
      const icon = document.createElement('span')
      icon.className   = 'play-icon'
      icon.setAttribute('aria-hidden', 'true')
      icon.textContent = '\u25B6'
      playBtn.appendChild(icon)
      playBtn.addEventListener('click', () => {
        if (playbackEngine.state !== 'idle' && playbackEngine.current?.index === sentenceIdx) {
          playbackEngine.togglePause()
        } else {
          playbackEngine.speak(sentence.text, ttsTag, 'sentence', sentenceIdx)
        }
      })
      gutter.appendChild(playBtn)
    }

    const content = document.createElement('div')
    content.className = 'reader-sentence__content'
    content.appendChild(buildAnnotatedText(sentence.text, sentence.learnable_objects, language, dir, tokenMode, scriptFam))

    if (sentence.learnable_objects.length > 0) {
      const list = document.createElement('ul')
      list.className = 'sentence-card__pills'
      list.setAttribute('role', 'list')
      list.setAttribute('dir', dir)

      for (const item of sentence.learnable_objects) {
        const li   = document.createElement('li')
        const pill = document.createElement('mnemosyne-pill')
        pill.setAttribute('type',       item.type)
        pill.setAttribute('label',      item.label)
        pill.setAttribute('object-id',  item.id)
        pill.setAttribute('language',   language)
        pill.setAttribute('dir',        dir)
        if (item.confidence != null) {
          pill.setAttribute('confidence', String(item.confidence))
        }
        li.appendChild(pill)
        list.appendChild(li)
      }

      content.appendChild(list)
    }

    layout.append(gutter, content)
    article.appendChild(layout)
    fragment.appendChild(article)
  }

  results.replaceChildren(fragment)
  applyScriptViewToResults()
  updateScriptViewToolbar()
  renderFilterChips(sentences)

  if (playAllBtn) playAllBtn.hidden = !(canSpeak && sentences.length > 0)
}


// ── Inline annotation builder ─────────────────────────────────────────────────

function buildAnnotatedText(text, items, language, dir, tokenMode, scriptFam) {
  const p = document.createElement('p')
  p.className = 'sentence-card__text reader-sentence__text'
  p.setAttribute('lang', language)
  p.setAttribute('dir',  dir)
  p.dataset.tokenization = tokenMode
  p.dataset.scriptFamily = scriptFam
  p.dataset.layer = 'native'

  if (!items.length) {
    p.textContent = text
    return p
  }

  const lower  = text.toLowerCase()
  const ranges = []

  for (const item of items) {
    if (!item.label) continue
    const needle = item.label.toLowerCase()
    let pos = 0
    while (pos < lower.length) {
      const idx = lower.indexOf(needle, pos)
      if (idx === -1) break
      ranges.push({ start: idx, end: idx + item.label.length, item })
      pos = idx + 1
    }
  }

  // Sort by start; prefer longer match at same start
  ranges.sort((a, b) => a.start - b.start || (b.end - b.start) - (a.end - a.start))

  // Greedy non-overlapping selection
  const selected = []
  let lastEnd = 0
  for (const r of ranges) {
    if (r.start < lastEnd) continue
    selected.push(r)
    lastEnd = r.end
  }

  let cursor = 0
  for (const { start, end, item } of selected) {
    if (cursor < start) p.appendChild(document.createTextNode(text.slice(cursor, start)))

    const mark = document.createElement('mark')
    mark.className = 'reader-annotation'
    mark.dataset.type = item.type
    mark.setAttribute('role', 'button')
    mark.setAttribute('tabindex', '0')
    mark.setAttribute('aria-label', item.label)
    mark.textContent = text.slice(start, end)
    mark.addEventListener('click', () => {
      mark.dispatchEvent(new CustomEvent('lesson-open', {
        bubbles: true,
        detail:  { objectId: item.id, language },
      }))
    })
    mark.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); mark.click() }
    })
    p.appendChild(mark)
    cursor = end
  }

  if (cursor < text.length) p.appendChild(document.createTextNode(text.slice(cursor)))

  return p
}


// ── Annotation filter chips ───────────────────────────────────────────────────

function renderFilterChips(sentences) {
  if (!readerFilters) return

  const types = new Set()
  for (const s of sentences) {
    for (const item of s.learnable_objects) {
      if (item.type) types.add(item.type)
    }
  }

  if (types.size === 0) {
    readerFilters.hidden = true
    return
  }

  activeFilterTypes = null
  readerFilters.replaceChildren()

  const allChip = document.createElement('button')
  allChip.type = 'button'
  allChip.className = 'reader-chip reader-chip--active'
  allChip.dataset.filterType = ''
  allChip.setAttribute('aria-pressed', 'true')
  allChip.textContent = t('filter_all') || 'All'
  allChip.addEventListener('click', () => {
    activeFilterTypes = null
    applyAnnotationFilter()
    syncFilterChipUI()
  })
  readerFilters.appendChild(allChip)

  for (const type of [...types].sort()) {
    const chip = document.createElement('button')
    chip.type = 'button'
    chip.className = 'reader-chip'
    chip.dataset.filterType = type
    chip.setAttribute('aria-pressed', 'false')
    chip.textContent = type.replace(/_/g, '\u00A0')
    chip.addEventListener('click', () => {
      if (activeFilterTypes === null) {
        activeFilterTypes = new Set([type])
      } else if (activeFilterTypes.has(type)) {
        activeFilterTypes.delete(type)
        if (activeFilterTypes.size === 0) activeFilterTypes = null
      } else {
        activeFilterTypes.add(type)
      }
      applyAnnotationFilter()
      syncFilterChipUI()
    })
    readerFilters.appendChild(chip)
  }

  readerFilters.hidden = false
}

function syncFilterChipUI() {
  if (!readerFilters) return
  readerFilters.querySelectorAll('.reader-chip').forEach(chip => {
    const type   = chip.dataset.filterType
    const active = type === '' ? activeFilterTypes === null : (activeFilterTypes?.has(type) ?? false)
    chip.classList.toggle('reader-chip--active', active)
    chip.setAttribute('aria-pressed', String(active))
  })
}

function applyAnnotationFilter() {
  results?.querySelectorAll('.reader-annotation').forEach(mark => {
    mark.toggleAttribute('data-filtered', activeFilterTypes !== null && !activeFilterTypes.has(mark.dataset.type))
  })
  results?.querySelectorAll('.sentence-card__pills li').forEach(li => {
    const pill = li.querySelector('mnemosyne-pill')
    if (!pill) return
    li.hidden = activeFilterTypes !== null && !activeFilterTypes.has(pill.getAttribute('type'))
  })
}


// ── Large-text async parse (job API + SSE) ────────────────────────────────────

async function parseWithJob(text, language) {
  const jobResp = await fetch(`${API_BASE}/parse/jobs`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body:    JSON.stringify({
      language,
      text,
      source_url: currentSourceUrl || null,
    }),
  })
  if (!jobResp.ok) {
    const body = await jobResp.json().catch(() => null)
    throw new Error(body?.detail ?? `${t('parsing_failed')} (${jobResp.status})`)
  }
  const { job_id: jobId } = await jobResp.json()

  setJobProgress(0, t('job_queued'))

  const eventsResp = await fetch(`${API_BASE}/parse/jobs/${jobId}/events`, {
    headers: getAuthHeaders(),
  })
  if (!eventsResp.ok) {
    throw new Error(`SSE stream unavailable (${eventsResp.status})`)
  }

  for await (const event of readSseEvents(eventsResp)) {
    if (event.status === 'running' || event.status === 'pending') {
      const pct   = Math.round((event.progress ?? 0) * 100)
      const total = event.sentences_total
      const done  = event.sentences_done
      const label = total
        ? ti('job_analysing', { done, total })
        : _stageLabel(event.stage)
      setJobProgress(pct, label)
    }

    if (event.status === 'done') {
      setJobProgress(100, t('job_done'))
      return event.result
    }
    if (event.status === 'failed') throw new Error(event.error ?? t('job_failed'))
  }

  const poll = await fetch(`${API_BASE}/parse/jobs/${jobId}`, { headers: getAuthHeaders() })
  const finalJob = await poll.json()
  if (finalJob.status === 'done') {
    setJobProgress(100, t('job_done'))
    return finalJob.result
  }
  if (finalJob.status === 'failed') throw new Error(finalJob.error ?? t('job_failed'))
  throw new Error(t('job_timeout'))
}

function _stageLabel(stage) {
  return {
    nlp:     t('job_analysing_text'),
    persist: t('job_saving'),
    pending: t('job_queued'),
  }[stage] ?? t('job_processing')
}

function setJobProgress(percent, label) {
  if (!jobProgressPanel) return
  if (percent === null) {
    jobProgressPanel.hidden = true
    return
  }
  jobProgressPanel.hidden = false
  if (jobProgressFill) {
    const indeterminate = percent === 'indeterminate'
    jobProgressFill.classList.toggle('job-progress__bar--indeterminate', indeterminate)
    if (indeterminate) {
      jobProgressFill.removeAttribute('aria-valuenow')
      jobProgressFill.style.removeProperty('--progress')
    } else {
      jobProgressFill.classList.remove('job-progress__bar--indeterminate')
      jobProgressFill.style.setProperty('--progress', `${percent}%`)
      jobProgressFill.setAttribute('aria-valuenow', String(percent))
    }
  }
  if (jobProgressLabel) jobProgressLabel.textContent = label ?? ''
}

async function* readSseEvents(response) {
  const reader  = response.body.getReader()
  const decoder = new TextDecoder()
  let   buffer  = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop()
    for (const block of blocks) {
      for (const line of block.split('\n')) {
        if (line.startsWith('data: ')) {
          try { yield JSON.parse(line.slice(6)) } catch { /* skip malformed */ }
        }
      }
    }
  }
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

const offlineBadge    = document.querySelector('#offline-badge')
const offlineCountEl  = document.querySelector('#offline-count')
const offlinePluralEl = document.querySelector('#offline-plural')

async function updateOfflineBadge() {
  if (!offlineBadge) return
  const n = await countPendingReviews()
  if (n === 0) {
    offlineBadge.hidden = true
    return
  }
  offlineCountEl.textContent  = String(n)
  offlinePluralEl.textContent = (document.documentElement.lang === 'en' && n !== 1) ? 's' : ''
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
      } else if (response.status === 401) {
        // JWT expired while offline — stop drain and notify; keep queue intact.
        setStatus(t('session_expired_queue'), 'error')
        break
      } else {
        // Server error — stop and retry silently on next online event.
        break
      }
    } catch {
      break
    }
  }

  if (synced > 0) updateOfflineBadge()
}

window.addEventListener('online', drainReviewQueue)
updateOfflineBadge()


// ── Text-to-speech ────────────────────────────────────────────────────────────

function speakText(text, langTag) {
  if (!text || !canSpeak) return
  playbackEngine.speak(text, langTag, 'phrase')
}


// ── Startup-warning header helper ─────────────────────────────────────────────

function handleStartupWarningHeader(response) {
  const warning = response.headers.get('X-Startup-Warning')
  if (warning) showBackendBanner(warning)
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


// ── Backend health check ──────────────────────────────────────────────────────

const startupBanner    = document.querySelector('#startup-banner')
const startupBannerMsg = document.querySelector('#startup-banner-msg')

function showBackendBanner(message) {
  if (!startupBanner || !startupBannerMsg) return
  startupBannerMsg.textContent = message
  startupBanner.hidden = false
}

function hideBackendBanner() {
  if (!startupBanner) return
  startupBanner.hidden = true
}

async function checkBackendHealth() {
  try {
    const response = await fetch(`${API_BASE}/ready`)
    const data = await response.json().catch(() => null)

    if (!response.ok || data?.status !== 'ready') {
      const startupErrors = Array.isArray(data?.startup) ? data.startup : []
      const msg = startupErrors[0]
        ?? data?.detail
        ?? `Backend is degraded (${response.status}). Some features may not work. Reload after the issue is resolved.`
      showBackendBanner(msg)
    } else {
      hideBackendBanner()
    }
  } catch {
    showBackendBanner(
      'Cannot reach the backend server. Ensure it is running and reload the page.'
    )
  }
}

checkBackendHealth()
window.__checkBackendHealth = checkBackendHealth


// ── Auth init ─────────────────────────────────────────────────────────────────

initAuth()
