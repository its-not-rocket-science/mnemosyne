import '../components/mnemosyne-pill.js'
import '../components/mnemosyne-modal.js'
import '../components/mnemosyne-filter-bar.js'
import '../components/mnemosyne-detail-pane.js'
import '../components/mnemosyne-player.js'
import '../components/mnemosyne-now-playing-bar.js'
import { initAuth, getAuthHeaders, getUser } from './auth.js'
import { playbackEngine } from './playback.js'
import {
  queueReview,
  getPendingReviews,
  deleteReview,
  countPendingReviews,
} from './offline.js'
import { initUiLanguage, t, ti, currentUiLang, TYPE_LABELS_LONG_I18N } from './i18n.js'
import { openDetail, closeDetail } from './layout.js'
import { API_BASE } from './config.js'

initUiLanguage()

// ── DOM references ────────────────────────────────────────────────────────────

const OWNER_EMAIL = 'paul_schleifer@hotmail.com'

const languageSelect    = document.querySelector('#language')
const chooseTextBtn     = document.querySelector('#choose-text-btn')
const changeTextBtn     = document.querySelector('#change-text-btn')
const loadLessonBtn     = document.querySelector('#load-lesson-btn')
const chosenTextDisplay = document.querySelector('#chosen-text-display')
const saveLessonBtn     = document.querySelector('#save-lesson-btn')
const results           = document.querySelector('#results')
const resultsEmpty      = document.querySelector('.results-empty')
const status            = document.querySelector('#status')
const modal             = document.querySelector('#lesson-modal')
const detailPane        = document.querySelector('#detail-pane')
const paneBackdrop      = document.querySelector('#pane-backdrop')
const resultsTransport  = document.querySelector('#results-transport')
const resultsPlayBtn    = document.querySelector('#results-play-btn')
const resultsScrubber   = document.querySelector('#results-scrubber')
const resultsTimeLabel  = document.querySelector('#results-time-label')
const mainPlayer        = document.querySelector('#main-player')
const resultsToolbar    = document.querySelector('#results-toolbar')
const langNuanceBar     = document.querySelector('#lang-nuance-bar')
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
const pickerSampleBtn   = document.querySelector('#picker-sample-btn')
const pickerSampleLanguageSelect = document.querySelector('#picker-sample-language')
const pickerCharCount   = document.querySelector('#picker-char-count')

// Save-lesson dialog
const saveLessonDialog     = document.querySelector('#save-lesson-dialog')
const saveTitleInput       = document.querySelector('#save-title')
const saveLessonStatus     = document.querySelector('#save-lesson-status')
const saveLessonCloseBtn   = document.querySelector('#save-lesson-close-btn')
const saveLessonConfirmBtn = document.querySelector('#save-lesson-confirm-btn')

// About dialog
const aboutDialog    = document.querySelector('#about-dialog')
const aboutCloseBtn  = document.querySelector('#about-close-btn')
const aboutBtn       = document.querySelector('#about-btn')

// GDPR dialog
const gdprDialog       = document.querySelector('#gdpr-dialog')
const gdprCloseBtn     = document.querySelector('#gdpr-close-btn')
const gdprOkBtn        = document.querySelector('#gdpr-ok-btn')
const privacyLink      = document.querySelector('#privacy-link')

// Save unsupported dialog
const saveUnsupportedDialog   = document.querySelector('#save-unsupported-dialog')
const saveUnsupportedCloseBtn = document.querySelector('#save-unsupported-close-btn')
const saveUnsupportedOkBtn    = document.querySelector('#save-unsupported-ok-btn')

// Load lesson dialog
const loadLessonDialog    = document.querySelector('#load-lesson-dialog')
const loadLessonCloseBtn  = document.querySelector('#load-lesson-close-btn')
const loadLessonList      = document.querySelector('#load-lesson-list')

// Reader UI
const siteHero           = document.querySelector('#site-hero')
const resultsSection     = document.querySelector('#results-section')
const resultsTitle       = document.querySelector('#results-heading')
const resultsEyebrow     = document.querySelector('#results-source-eyebrow')
const parseDialog        = document.querySelector('#parse-dialog')
const parseDialogClose   = document.querySelector('#parse-dialog-close')
const changeLessonBtn    = document.querySelector('#change-lesson-btn')
const filterBar          = document.querySelector('#filter-bar')
const appFilterBar       = document.querySelector('#app-filter-bar')

const nowPlayingBar      = document.querySelector('#now-playing-bar')
const readingProgress    = document.querySelector('#reading-progress')
const annotationMinimap  = document.querySelector('#annotation-minimap')

// Accessibility
const a11yLive         = document.querySelector('#a11y-live')
const shortcutsDialog  = document.querySelector('#shortcuts-dialog')
const shortcutsCloseBtn = document.querySelector('#shortcuts-close-btn')
const readerNowPlaying = document.querySelector('#reader-nowplaying')
const rnpToggle        = document.querySelector('#rnp-toggle')
const rnpStop          = document.querySelector('#rnp-stop')
const rnpPrev          = document.querySelector('#rnp-prev')
const rnpNext          = document.querySelector('#rnp-next')
const rnpText          = document.querySelector('#reader-nowplaying .reader-nowplaying__text')
const rnpCounter       = document.querySelector('#reader-nowplaying .reader-nowplaying__counter')


const reviewStateByObject = new Map()
const canSpeak = 'speechSynthesis' in window

// Transport timer state
let _transportTimerId   = null
let _transportWallStart = null
let _transportPauseOff  = 0
let _transportEstDur    = 0

function _transportFmt(s) {
  const t = Math.max(0, Math.floor(s))
  return `${String(Math.floor(t / 60)).padStart(2, '0')}:${String(t % 60).padStart(2, '0')}`
}

function _transportTick() {
  if (!_transportWallStart) return
  const elapsed = (Date.now() - _transportWallStart) / 1000
  const pct = _transportEstDur > 0 ? Math.min((elapsed / _transportEstDur) * 100, 100) : 0
  if (resultsScrubber) resultsScrubber.value = String(pct)
  if (resultsTimeLabel) resultsTimeLabel.textContent =
    `${_transportFmt(elapsed)}\u2009/\u2009${_transportFmt(_transportEstDur)}`
}

function _transportStart() {
  if (_transportTimerId) clearInterval(_transportTimerId)
  _transportEstDur    = Math.max(playbackEngine.totalChars / 14, 2)
  _transportWallStart = Date.now() - _transportPauseOff
  _transportTimerId   = setInterval(_transportTick, 500)
}

function _transportPause() {
  _transportPauseOff = Date.now() - (_transportWallStart ?? Date.now())
  if (_transportTimerId) { clearInterval(_transportTimerId); _transportTimerId = null }
}

function _transportReset() {
  if (_transportTimerId) { clearInterval(_transportTimerId); _transportTimerId = null }
  _transportWallStart = null
  _transportPauseOff  = 0
  _transportEstDur    = 0
  if (resultsScrubber)  resultsScrubber.value = '0'
  if (resultsTimeLabel) resultsTimeLabel.textContent = '--:--'
}

// Stores the last-rendered sentences and their TTS tag for playback controls.
let currentSentences = []
let currentTtsTag    = ''

let currentContentType    = 'pasted_text'
let currentFilename       = null
let currentSourceUrl      = null
let currentFetchedTitle   = null
let currentDocumentTitle  = null
let currentDocumentEyebrow = null
let languageUserSelected  = false
let currentText          = ''   // committed text from picker
let activeFilterTypes    = null // Set<string> when filtered, null = show all

let isFollowAlongEnabled = false
let currentDepth         = 'scholar'

const languageCapabilities = new Map()
let currentCaps = null
let scriptView  = 'native'

const MAX_FILE_BYTES = 1_048_576  // 1 MiB
const DEFAULT_MAX_JOB_CHARS = 100_000
let maxJobChars = DEFAULT_MAX_JOB_CHARS

// ── Annotation type metadata ───────────────────────────────────────────────────
// TYPE_LABEL_KEYS : tooltip text shown in the ::before pseudo-element.
// TYPE_LEVEL : 1=vocabulary, 2=grammar/script, 3=idiom/nuance/literary
const TYPE_LABEL_KEYS = {
  vocabulary: 'type_vocabulary_short',
  conjugation: 'type_conjugation_short',
  agreement: 'type_agreement_short',
  idiom: 'type_idiom_short',
  grammar: 'type_grammar_short',
  nuance: 'type_nuance_short',
  script: 'type_script_short',
  transliteration: 'type_script_short',
  phrase_family: 'type_phrase_family_short',
}

const TYPE_LEVEL = {
  vocabulary:      1,
  conjugation:     2,
  agreement:       2,
  grammar:         2,
  script:          2,
  transliteration: 2,
  idiom:           3,
  nuance:          3,
  phrase_family:   3,
}


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

    // Hide QA/dev-only fake locales from the initial picker.
    // They remain available via direct QA flows/API usage.
    const initialPickerLanguages = languages.filter((caps) => !['x-cjk-test', 'x-rtl-test'].includes(caps.code))

    const current = languageSelect.value
    languageSelect.removeAttribute('aria-busy')
    const placeholder = document.createElement('option')
    placeholder.value = ''
    placeholder.textContent = t('choose_language')
    languageSelect.replaceChildren(
      placeholder,
      ...initialPickerLanguages.map((caps) => {
        const opt = document.createElement('option')
        opt.value = caps.code
        opt.dataset.lessonLang = caps.code
        const translated = t('lesson_lang_' + caps.code)
        opt.textContent = (translated && translated !== 'lesson_lang_' + caps.code)
          ? translated
          : caps.display_name
        if (caps.code === current) opt.selected = true
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
  populateSampleLanguageSelect()
  refreshLoadLessonBtn()
  if (_dlAnnotation) _openDeepLink()
}

async function loadParseLimits() {
  try {
    const response = await fetch(`${API_BASE}/parse/limits`, { headers: getAuthHeaders() })
    if (!response.ok) return
    const data = await response.json()
    if (typeof data.max_job_chars === 'number' && data.max_job_chars > 0) {
      maxJobChars = data.max_job_chars
    }
  } catch {
    // Fallback to DEFAULT_MAX_JOB_CHARS.
  } finally {
    updatePickerCharCount()
  }
}

loadParseLimits()
loadLanguages()

languageSelect.addEventListener('change', () => {
  languageUserSelected = true
  scriptView = 'native'
  syncCurrentCaps()
  populateSampleLanguageSelect()
  refreshLoadLessonBtn()
})

function syncCurrentCaps() {
  currentCaps = languageCapabilities.get(languageSelect.value) ?? null
  updateScriptViewToolbar()
  updateNuanceBar()
}

// ── Nuance-coverage indicator ─────────────────────────────────────────────────

const _NUANCE_LABELS = {
  idioms:              'Idioms',
  grammar_nuance:      'Grammar',
  pronunciation_tts:   'Pronunciation',
  transliteration:     'Script',
  formality_register:  'Register',
}

function updateNuanceBar() {
  if (!langNuanceBar) return
  const nc = currentCaps?.nuance_capabilities
  if (!nc) { langNuanceBar.hidden = true; return }

  const dots = Object.entries(_NUANCE_LABELS)
    .filter(([key]) => nc[key] && nc[key] !== 'none')
    .map(([key, label]) => {
      const span = document.createElement('span')
      span.className = 'lang-nuance-bar__dot'
      span.dataset.level = nc[key]
      span.textContent = label
      return span
    })

  if (dots.length === 0) { langNuanceBar.hidden = true; return }
  langNuanceBar.replaceChildren(...dots)
  langNuanceBar.hidden = false
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
  languageUserSelected = false
  textPickerDialog?.showModal()
  updatePickerCharCount()
  pickerTextarea?.focus()
}

chooseTextBtn?.addEventListener('click', openPicker)
changeTextBtn?.addEventListener('click', openPicker)
pickerCloseBtn?.addEventListener('click', () => textPickerDialog?.close())

// Parse dialog — non-modal inline on load, modal when user invokes change-lesson
parseDialog?.addEventListener('cancel', e => {
  // Prevent ESC from dismissing when shown non-modal (no results yet)
  if (!parseDialog.matches(':modal')) e.preventDefault()
})
parseDialogClose?.addEventListener('click', () => parseDialog?.close())
changeLessonBtn?.addEventListener('click', () => parseDialog?.showModal())

// Sample texts — one short natural-language paragraph per supported language
const SAMPLE_TEXTS = {
  ar: 'في الصباح الباكر، استيقظ الطفل على صوت العصافير تغرد خارج النافذة. نهض بحماس ونظر إلى السماء الزرقاء الصافية، وأدرك أن هذا اليوم سيكون جميلاً.',
  de: 'Im Sommer verbrachten wir viele Nachmittage am See. Das Wasser war klar und kühl, und die Kinder spielten am Ufer, während die Erwachsenen im Schatten der alten Bäume saßen.',
  el: 'Την άνοιξη, τα λιβάδια γεμίζουν με αγριολούλουδα κάθε χρώματος. Οι χωρικοί βγαίνουν στα χωράφια πρωί πρωί και εργάζονται μέχρι το ηλιοβασίλεμα, χαίρονται τη φύση γύρω τους.',
  es: 'El sol brillaba sobre las montañas mientras los viajeros descansaban junto al río. El agua fría refrescaba sus pies cansados después de un largo día de camino.',
  fr: 'Le soleil se couchait sur la ville lorsque Marie aperçut un inconnu assis sur le banc du jardin. Elle hésita un moment avant de s\'approcher et de lui adresser la parole.',
  he: 'בבוקר השקט, עלי הסתכל מהחלון על הרחוב הרטוב מגשם הלילה. הוא אהב את השקט הזה שלפני שהעיר מתעוררת, את הרגע הקצר שבו הכל נראה טהור ואפשרי.',
  it: 'Quella mattina d\'autunno, le foglie cadevano lentamente dagli alberi del parco. Marco sedeva sulla panchina preferita e guardava i bambini giocare, pensando ai tempi in cui anche lui correva su quel prato.',
  ja: '春の朝、桜の花びらが風に舞っていた。公園のベンチに座った老人は、静かに目を閉じ、長い人生の思い出に浸っていた。',
  la: 'Antiquis temporibus Roma erat magna urbs et caput mundi. Cives Romani in viis angustis habitabant et multa negotia in foro agebant. Lingua Latina in omnibus partibus imperii audiri poterat.',
  pt: 'Naquela tarde de verão, Ana caminhou até o mercado do bairro para comprar frutas frescas. O vendedor sorriu ao vê-la e separou as melhores laranjas, sabendo que ela sempre escolhia com cuidado.',
  ru: 'Поздним вечером, когда город уже засыпал, она открыла старую книгу и начала читать. Слова на пожелтевших страницах казались живыми и наполненными смыслом.',
  zh: '那个清晨，阳光透过窗帘照进来，照在书桌上那叠厚厚的书上。他拿起最上面的一本，翻到折角的那一页，继续昨晚没有读完的故事。',
}

const EXCLUDED_SAMPLE_LANGUAGES = new Set(['x-cjk-test', 'x-rtl-test'])

function populateSampleLanguageSelect() {
  if (!pickerSampleLanguageSelect) return
  const activeLang = pickerSampleLanguageSelect.value || languageSelect.value || 'es'
  const options = [...languageSelect.options]
    .filter((opt) => opt.value && !EXCLUDED_SAMPLE_LANGUAGES.has(opt.value))

  pickerSampleLanguageSelect.replaceChildren(
    ...options.map((opt) => {
      const sampleOption = document.createElement('option')
      sampleOption.value = opt.value
      sampleOption.textContent = opt.textContent
      return sampleOption
    })
  )

  pickerSampleLanguageSelect.value = options.some((opt) => opt.value === activeLang)
    ? activeLang
    : (options[0]?.value ?? 'es')
}

pickerSampleBtn?.addEventListener('click', () => {
  const selectedSampleLang = pickerSampleLanguageSelect?.value || languageSelect.value
  const fallbackLang = languageSelect.value || 'es'
  const sample = SAMPLE_TEXTS[selectedSampleLang] ?? SAMPLE_TEXTS[fallbackLang] ?? SAMPLE_TEXTS.es

  if (!SAMPLE_TEXTS[selectedSampleLang]) {
    const fallbackLabel = languageSelect?.options[languageSelect.selectedIndex]?.text || fallbackLang
    setPickerStatus(ti('sample_missing_fallback', { language: fallbackLabel }))
  } else {
    setPickerStatus('')
  }

  if (pickerTextarea) {
    pickerTextarea.value = sample
    pickerTextarea.dispatchEvent(new Event('input'))
    pickerTextarea.focus()
  }
  if (languageSelect && selectedSampleLang) {
    languageSelect.value = selectedSampleLang
    languageSelect.dispatchEvent(new Event('change'))
  }
})

pickerSampleLanguageSelect?.addEventListener('change', () => {
  if (pickerSampleLanguageSelect?.value) {
    languageSelect.value = pickerSampleLanguageSelect.value
    languageSelect.dispatchEvent(new Event('change'))
  }
})

// File input inside picker
pickerFileInput?.addEventListener('change', () => {
  const file = pickerFileInput.files?.[0]
  if (!file) return

  pickerFileInput.setAttribute('accept', ACCEPT_ATTRIBUTE)
  if (file.size > MAX_FILE_BYTES) {
    setPickerStatus(ti('file_too_large', { kb: (file.size / 1024).toFixed(0) }), 'error')
    pickerFileInput.value = ''
    return
  }

  extractTextFromFile(file).then(text => {
    pickerTextarea.value = text
    currentContentType   = 'uploaded_file'
    currentFilename      = file.name
    languageUserSelected = false
    setPickerStatus(`Loaded: ${escapeHtml(file.name)} (${(file.size / 1024).toFixed(1)} KB)`)
    scheduleLanguageDetection()
  }).catch(error => {
    const key = error instanceof Error ? error.message : 'file_read_error'
    const translatable = ['unsupported_file_type', 'encrypted_pdf', 'corrupt_file', 'no_extractable_text', 'file_read_error']
    setPickerStatus(t(translatable.includes(key) ? key : 'file_read_error'), 'error')
    currentContentType = 'pasted_text'
    currentFilename    = null
  })
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
    currentFetchedTitle  = data.title || null
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
  updatePickerCharCount()
  scheduleLanguageDetection()
})

function updatePickerCharCount() {
  if (!pickerTextarea || !pickerCharCount || !pickerUseBtn) return
  const textLength = pickerTextarea.value.length
  const overLimit = textLength > maxJobChars
  pickerCharCount.textContent = ti('picker_char_count', {
    count: textLength.toLocaleString(),
    limit: maxJobChars.toLocaleString(),
  })
  pickerCharCount.dataset.state = overLimit ? 'error' : 'idle'
  pickerTextarea.setAttribute('aria-invalid', String(overLimit))
  pickerUseBtn.disabled = overLimit
}

// Confirm: "Use this text"
pickerUseBtn?.addEventListener('click', () => {
  const text = pickerTextarea?.value.trim() ?? ''
  if (text.length > maxJobChars) {
    setPickerStatus(ti('picker_text_too_long', { limit: maxJobChars.toLocaleString() }), 'error')
    pickerTextarea?.focus()
    return
  }
  if (!text) {
    setPickerStatus(t('text_empty_error'), 'error')
    pickerTextarea?.focus()
    return
  }
  currentText      = text
  currentSourceUrl = pickerUrlInput?.value.trim() || null

  if (currentContentType === 'article' && currentSourceUrl) {
    try { currentDocumentEyebrow = new URL(currentSourceUrl).hostname } catch { currentDocumentEyebrow = null }
    currentDocumentTitle = currentFetchedTitle || currentDocumentEyebrow
  } else if (currentContentType === 'uploaded_file' && currentFilename) {
    currentDocumentTitle  = currentFilename.replace(/\.[^.]+$/, '')
    currentDocumentEyebrow = null
  } else {
    currentDocumentTitle  = null
    currentDocumentEyebrow = null
  }

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
  if (getUser()?.email !== OWNER_EMAIL) {
    saveUnsupportedDialog?.showModal()
    return
  }
  saveLessonDialog?.showModal()
  saveTitleInput?.focus()
})

saveLessonCloseBtn?.addEventListener('click', () => saveLessonDialog?.close())

saveLessonConfirmBtn?.addEventListener('click', async () => {
  const title = saveTitleInput?.value.trim() ?? ''
  if (!title) {
    if (saveLessonStatus) {
      saveLessonStatus.textContent = t('text_empty_error')
      saveLessonStatus.dataset.state = 'error'
    }
    saveTitleInput?.focus()
    return
  }
  const language = languageSelect?.value
  if (!currentText || !language) { saveLessonDialog?.close(); return }
  try {
    const resp = await fetch(`${API_BASE}/ingest`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body:    JSON.stringify({ text: currentText, language, title, source_url: currentSourceUrl || null }),
    })
    if (!resp.ok) throw new Error(resp.status)
    saveLessonDialog?.close()
    refreshLoadLessonBtn()
  } catch {
    if (saveLessonStatus) {
      saveLessonStatus.textContent = t('parse_error_generic')
      saveLessonStatus.dataset.state = 'error'
    }
  }
})

// ── Save-unsupported dialog ───────────────────────────────────────────────────

saveUnsupportedCloseBtn?.addEventListener('click', () => saveUnsupportedDialog?.close())
saveUnsupportedOkBtn?.addEventListener('click',    () => saveUnsupportedDialog?.close())

// ── About dialog ─────────────────────────────────────────────────────────────

aboutBtn?.addEventListener('click', () => aboutDialog?.showModal())
aboutCloseBtn?.addEventListener('click', () => aboutDialog?.close())

const aboutTabs   = document.querySelectorAll('.about-dialog__tab')
const aboutPanels = document.querySelectorAll('#about-dialog [role="tabpanel"]')
aboutTabs.forEach(tab => {
  tab.addEventListener('click', () => {
    aboutTabs.forEach(t => {
      t.setAttribute('aria-selected', 'false')
      t.tabIndex = -1
    })
    aboutPanels.forEach(p => { p.hidden = true })
    tab.setAttribute('aria-selected', 'true')
    tab.tabIndex = 0
    const panel = document.getElementById(tab.getAttribute('aria-controls'))
    if (panel) panel.hidden = false
  })
})

// Arrow-key navigation inside the about-dialog tablist (APG tab pattern).
document.querySelector('.about-dialog__tabs')?.addEventListener('keydown', (e) => {
  const tabs = [...aboutTabs]
  const idx  = tabs.indexOf(document.activeElement)
  if (idx === -1) return
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
    e.preventDefault()
    const next = tabs[(idx + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length]
    next.focus()
    next.click()
  }
})

// ── GDPR dialog ───────────────────────────────────────────────────────────────

privacyLink?.addEventListener('click', e => {
  e.preventDefault()
  gdprDialog?.showModal()
})
gdprCloseBtn?.addEventListener('click', () => gdprDialog?.close())
gdprOkBtn?.addEventListener('click',    () => gdprDialog?.close())

// ── Load-lesson dialog ────────────────────────────────────────────────────────

loadLessonBtn?.addEventListener('click', async () => {
  const language = languageSelect?.value || null
  loadLessonList && (loadLessonList.innerHTML = '')
  loadLessonDialog?.showModal()
  try {
    const url = `${API_BASE}/sources` + (language ? `?language=${language}` : '')
    const resp = await fetch(url, { headers: getAuthHeaders() })
    if (!resp.ok) throw new Error(resp.status)
    const { sources } = await resp.json()
    if (!sources.length) {
      const li = document.createElement('li')
      li.className = 'load-lesson-list__empty'
      li.textContent = t(language ? 'load_lesson_empty' : 'load_lesson_all_empty')
      loadLessonList?.appendChild(li)
      return
    }
    for (const src of sources) {
      const li = document.createElement('li')
      li.className = 'load-lesson-list__item'
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.className = 'load-lesson-list__btn ghost-button'
      btn.textContent = src.title || src.language
      btn.dataset.sourceId  = src.id
      btn.dataset.sourceLang = src.language
      btn.addEventListener('click', () => _loadSource(src.id, src.language))
      li.appendChild(btn)
      loadLessonList?.appendChild(li)
    }
  } catch {
    const li = document.createElement('li')
    li.className = 'load-lesson-list__empty'
    li.textContent = t('parse_error_generic')
    loadLessonList?.appendChild(li)
  }
})

loadLessonCloseBtn?.addEventListener('click', () => loadLessonDialog?.close())

async function _loadSource(sourceId, language) {
  loadLessonDialog?.close()
  setStatus(t('loading'))
  try {
    const resp = await fetch(`${API_BASE}/sources/${sourceId}`, { headers: getAuthHeaders() })
    if (!resp.ok) throw new Error(resp.status)
    const data = await resp.json()
    // Set language selector to match
    if (languageSelect && data.language) {
      languageSelect.value = data.language
      languageSelect.dispatchEvent(new Event('change'))
    }
    currentDocumentTitle   = data.title || null
    currentDocumentEyebrow = null
    renderResults(data.sentences, data.language)
    setStatus(ti('sentences_parsed', { n: data.sentences.length }))
    if (saveLessonBtn) saveLessonBtn.hidden = false
  } catch {
    setStatus(t('load_lesson_failed'), 'error')
  }
}

async function refreshLoadLessonBtn() {
  if (!loadLessonBtn) return
  const user = getUser()
  if (!user) { loadLessonBtn.hidden = true; return }
  try {
    const language = languageSelect?.value || null
    const url = `${API_BASE}/sources` + (language ? `?language=${language}` : '')
    const resp = await fetch(url, { headers: getAuthHeaders() })
    if (!resp.ok) throw new Error()
    const { sources } = await resp.json()
    loadLessonBtn.hidden = sources.length === 0
  } catch {
    loadLessonBtn.hidden = true
  }
}


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


// ── Results heading ───────────────────────────────────────────────────────────

function setResultsHeading(title, eyebrow) {
  const langName = languageSelect?.options[languageSelect?.selectedIndex]?.text || ''
  if (resultsTitle) resultsTitle.textContent = title || langName
  if (resultsEyebrow) {
    resultsEyebrow.textContent = eyebrow || ''
    resultsEyebrow.hidden = !eyebrow
  }
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

    if (chosenTextDisplay) chosenTextDisplay.hidden = true
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
  const sentenceCard = event.target?.closest?.('.sentence-card')
  const sentenceText = sentenceCard?.querySelector('.sentence-card__text')?.textContent ?? ''

  const phrase = event.target?.getAttribute?.('aria-label') ?? objectId
  announce(`Loading details: ${phrase}`)
  setStatus(t('loading_lesson'), 'busy')

  try {
    const url = `${API_BASE}/lesson/${encodeURIComponent(objectId)}?language=${encodeURIComponent(language)}&depth=${encodeURIComponent(currentDepth)}`
    const response = await fetch(url)

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail ?? `Lesson not available (${response.status})`)
    }

    const lesson = await response.json()

    // Open the detail pane as the primary view.
    // "Study drills" inside the pane delegates to the existing modal.
    if (detailPane) {
      const uiLang = currentUiLang()
      detailPane.show({
        lesson,
        sentenceText,
        language,
        dir,
        ttsTag,
        caps,
        depth: currentDepth,
        uiLang,
        onTranslate: async (text, sourceLang, targetLang) => {
          if (!text || sourceLang === targetLang) return null
          try {
            // Only cache/retrieve by object_id when translating the lemma itself.
            // Sentence translations must not reuse the cached word translation.
            const lemma = lesson.lesson_data?.lemma || lesson.examples?.[0]
            const isLemma = lesson.type === 'vocabulary' && text === lemma
            const r = await fetch(`${API_BASE}/translate`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
              body: JSON.stringify({
                text,
                source_language: sourceLang,
                target_language: targetLang,
                object_id: isLemma ? lesson.id : undefined,
              }),
            })
            if (!r.ok) return null
            const d = await r.json()
            return d.translation ? { text: d.translation, attribution: d.attribution } : null
          } catch { return null }
        },
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

      // ── Visual anchor: link annotation to detail pane ─────────────────────
      // Mark the source annotation so CSS can accent it and connect it to the
      // pane's left border.  Also compute the vertical clip origin so the pane
      // entry animation feels anchored to where the click happened.
      document.querySelector('[data-detail-source]')?.removeAttribute('data-detail-source')
      const sourceEl = event.target?.closest?.('.reader-annotation') || event.target
      if (sourceEl?.classList?.contains('reader-annotation')) {
        sourceEl.dataset.detailSource = ''
      }

      const detailPanelEl = document.querySelector('#app-detail-panel')
      if (detailPanelEl) {
        const TYPE_ACCENT = {
          vocabulary: 'var(--ann-vocab)',
          grammar: 'var(--ann-grammar)', conjugation: 'var(--ann-grammar)', agreement: 'var(--ann-grammar)',
          idiom: 'var(--ann-idiom)',
          nuance: 'var(--ann-literary)', phrase_family: 'var(--ann-literary)',
          script: 'var(--ann-etymology)', transliteration: 'var(--ann-etymology)',
        }
        const type = sourceEl?.dataset?.type || lesson.type || ''
        detailPanelEl.style.setProperty('--detail-accent', TYPE_ACCENT[type] ?? 'var(--accent)')

        const panelRect = detailPanelEl.getBoundingClientRect()
        const annotRect = sourceEl?.getBoundingClientRect?.() ?? { top: panelRect.top }
        const fromPct = panelRect.height > 0
          ? Math.max(0, Math.min(60, ((annotRect.top - panelRect.top) / panelRect.height) * 100))
          : 0
        detailPanelEl.style.setProperty('--detail-clip-bottom', `${100 - Math.round(fromPct)}%`)
      }

      // Force re-run of entry animation alongside show()'s own rAF.
      detailPane.classList.remove('pane-entry-animate')
      requestAnimationFrame(() => detailPane.classList.add('pane-entry-animate'))

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

// Sync note badges on annotation marks when note is saved/cleared in the pane.
detailPane?.addEventListener('note-updated', ({ detail }) => {
  results.querySelectorAll(`[data-object-id="${CSS.escape(detail.objectId)}"]`).forEach(mark => {
    mark.toggleAttribute('data-has-note', detail.hasNote)
  })
})

// Close handler: collapse the split-pane grid when the pane is dismissed.
detailPane?.addEventListener('pane-close', () => {
  closeDetail()
  paneBackdrop?.classList.remove('is-visible')
  document.querySelector('[data-detail-source]')?.removeAttribute('data-detail-source')
  document.querySelector('#app-detail-panel')?.style.removeProperty('--detail-accent')
  detailPane?.classList.remove('pane-entry-animate')
})

paneBackdrop?.addEventListener('click', () => detailPane?.hide())

// Navigate from a confusable-family link inside the detail pane.
detailPane?.addEventListener('pane-navigate', async (event) => {
  const { objectId, language } = event.detail
  if (!objectId || !language) return
  const caps   = languageCapabilities.get(language)
  const ttsTag = caps?.tts_lang_tag ?? language
  const dir    = caps?.direction ?? 'ltr'
  try {
    const url = `${API_BASE}/lesson/${encodeURIComponent(objectId)}?language=${encodeURIComponent(language)}&depth=${encodeURIComponent(currentDepth)}`
    const response = await fetch(url)
    if (!response.ok) return
    const lesson = await response.json()
    if (!detailPane) return
    const uiLang = currentUiLang()
    detailPane.show({
      lesson,
      sentenceText: '',
      language,
      dir,
      ttsTag,
      caps,
      depth: currentDepth,
      uiLang,
      onSpeak:  (text, l) => speakText(text, l ?? ttsTag),
      onStudy:  () => modal.open({
        lesson,
        objectId: lesson.id,
        caps,
        language,
        onRate:  submitReview,
        onSpeak: (text) => speakText(text, ttsTag),
      }),
    })
  } catch { /* ignore — confusable may not be in store yet */ }
})


// ── TopNav event wiring ───────────────────────────────────────────────────────

const topNav = document.querySelector('mnemosyne-top-nav')


topNav?.addEventListener('depth-change', ({ detail }) => {
  currentDepth = detail.depth
  detailPane?.updateDepth(detail.depth)
})

filterBar?.addEventListener('filter-change', ({ detail }) => {
  activeFilterTypes = detail.types.length ? new Set(detail.types) : null
  applyAnnotationFilter()
})

function applyFilterBarLabels() {
  filterBar?.setLabels?.({
    vocab:        t('filter_vocab'),
    grammar:      t('filter_grammar'),
    idioms:       t('filter_idioms'),
    literary:     t('filter_literary'),
    etymology:    t('filter_etymology'),
    custom:       t('filter_custom'),
    custom_title: t('filter_custom_title'),
    custom_hint:  t('filter_custom_hint'),
    add_btn:      t('filter_add_btn'),
    placeholder:  t('filter_placeholder'),
  })
}

document.addEventListener('mnemosyne:language-changed', applyFilterBarLabels)
// Apply labels now (initUiLanguage ran before filterBar was defined).
applyFilterBarLabels()


// ── NowPlayingBar teleportation ───────────────────────────────────────────────
// Mobile: move bar into detail pane's now-playing slot so it appears at the
// bottom of the bottom sheet. Desktop: return it to .app-shell__left.

const _leftCol = document.querySelector('.app-shell__left')
const _npMq    = window.matchMedia('(max-width: 53.99rem)')

function _relocateNowPlayingBar(mobile) {
  if (!nowPlayingBar) return
  if (mobile) {
    nowPlayingBar.setAttribute('slot', 'now-playing')
    detailPane?.appendChild(nowPlayingBar)
  } else {
    nowPlayingBar.removeAttribute('slot')
    _leftCol?.appendChild(nowPlayingBar)
  }
}

_npMq.addEventListener('change', e => _relocateNowPlayingBar(e.matches))
_relocateNowPlayingBar(_npMq.matches)


// ── Screen-reader announcements ───────────────────────────────────────────────

function announce(msg) {
  if (!a11yLive) return
  // Clear first so the same message re-announces if repeated.
  a11yLive.textContent = ''
  requestAnimationFrame(() => { a11yLive.textContent = msg })
}


// ── Keyboard shortcut legend ──────────────────────────────────────────────────

shortcutsCloseBtn?.addEventListener('click', () => shortcutsDialog?.close())

function openShortcuts() {
  shortcutsDialog?.showModal()
  shortcutsCloseBtn?.focus()
}

topNav?.addEventListener('settings-open', openShortcuts)


// ── Global keyboard shortcuts ─────────────────────────────────────────────────
// Uses e.composedPath()[0] so the innermost shadow-DOM element is checked,
// avoiding false positives when focus is inside a Web Component.

document.addEventListener('keydown', e => {
  // Never intercept when a modal/dialog is open (it handles its own keys).
  if (shortcutsDialog?.open) return

  // Innermost focused element — pierces Shadow DOM.
  const target = /** @type {HTMLElement|null} */ (e.composedPath()[0])
  const tag = target?.tagName?.toLowerCase() ?? ''
  const inText   = tag === 'input' || tag === 'textarea'
  const inSelect = tag === 'select'
  const inButton = tag === 'button' || tag === 'a'

  // Never steal keys from text-entry controls.
  if (inText || inSelect) return

  switch (e.key) {
    case '?':
      if (!inButton) { e.preventDefault(); openShortcuts() }
      break

    case ' ':
      // Space activates the focused button natively; only intercept in dead space.
      if (!inButton && playbackEngine.state !== 'idle') {
        e.preventDefault()
        playbackEngine.togglePause()
        announce(playbackEngine.state === 'playing' ? 'Paused' : 'Resumed')
      }
      break

    case 'ArrowLeft':
      if (!inButton && playbackEngine.state !== 'idle') {
        e.preventDefault()
        playbackEngine.prev()
        announce('Previous sentence')
      }
      break

    case 'ArrowRight':
      if (!inButton && playbackEngine.state !== 'idle') {
        e.preventDefault()
        playbackEngine.next()
        announce('Next sentence')
      }
      break

    case 'f':
    case 'F':
      if (!inButton && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        isFollowAlongEnabled = !isFollowAlongEnabled
        announce(isFollowAlongEnabled ? 'Follow along enabled' : 'Follow along disabled')
      }
      break
  }
})


// ── Playback controls ─────────────────────────────────────────────────────────

rnpPrev?.addEventListener('click',   () => playbackEngine.prev())
rnpToggle?.addEventListener('click', () => playbackEngine.togglePause())
rnpStop?.addEventListener('click',   () => playbackEngine.stop())
rnpNext?.addEventListener('click',   () => playbackEngine.next())

resultsPlayBtn?.addEventListener('click', () => {
  if (playbackEngine.state === 'idle') {
    playbackEngine.playAll(
      currentSentences.map(s => ({ text: s.text, langTag: currentTtsTag }))
    )
  } else {
    playbackEngine.stop()
  }
})

playbackEngine.addEventListener('state-change', ({ detail: { state, current, index, total } }) => {
  // Reading progress bar — show during multi-item playback
  if (readingProgress) {
    if (state === 'idle' || total <= 1) {
      readingProgress.hidden = true
      readingProgress.style.removeProperty('--progress')
    } else {
      const progress = (index + 1) / total
      readingProgress.style.setProperty('--progress', String(progress))
      readingProgress.hidden = false
      readingProgress.setAttribute('aria-valuenow', String(Math.round(progress * 100)))
    }
  }

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

  // Results transport sync
  if (resultsPlayBtn) {
    const idle = state === 'idle'
    resultsPlayBtn.innerHTML        = idle ? '&#x25B6;&thinsp;Play all' : '&#x23F9;&thinsp;Stop'
    resultsPlayBtn.setAttribute('aria-label', idle ? 'Play all sentences' : 'Stop')
  }
  if (state === 'playing' && !_transportWallStart) {
    _transportStart()
  } else if (state === 'paused') {
    _transportPause()
  } else if (state === 'idle') {
    _transportReset()
  } else if (state === 'playing' && _transportWallStart && _transportTimerId === null) {
    _transportStart()
  }

  // Follow-along: scroll active sentence into view
  if (isFollowAlongEnabled && state === 'playing' && current) {
    const activeCard = results?.querySelector(`[data-sentence-index="${current.index}"]`)
    activeCard?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
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

  // Prose container \u2014 all sentences flow inline as one continuous paragraph.
  const prose = document.createElement('div')
  prose.className = 'reader-prose'
  prose.setAttribute('lang', language)
  prose.setAttribute('dir',  dir)

  for (const [sentenceIdx, sentence] of sentences.entries()) {
    if (sentenceIdx > 0) prose.appendChild(document.createTextNode(' '))

    const row = document.createElement('span')
    row.className = 'reader-sentence sentence-card'
    row.dataset.tokenization  = tokenMode
    row.dataset.sentenceIndex = sentenceIdx

    if (canSpeak) {
      const playBtn = document.createElement('button')
      playBtn.type      = 'button'
      playBtn.className = 'reader-gutter-btn sentence-card__play-btn'
      playBtn.setAttribute('aria-label',   `Play sentence ${sentenceIdx + 1}`)
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
      row.appendChild(playBtn)
    }

    row.appendChild(
      buildAnnotatedText(sentence.text, sentence.learnable_objects, language, dir, tokenMode, scriptFam)
    )
    prose.appendChild(row)
  }

  fragment.appendChild(prose)

  results.replaceChildren(fragment)
  applyScriptViewToResults()
  updateScriptViewToolbar()
  requestAnimationFrame(buildMinimap)

  setResultsHeading(currentDocumentTitle, currentDocumentEyebrow)
  if (resultsSection) resultsSection.hidden = false
  if (siteHero) siteHero.hidden = true
  parseDialog?.close()
  if (changeLessonBtn) changeLessonBtn.hidden = false

  if (filterBar) {
    const allTypes = [...new Set(sentences.flatMap(s =>
      s.learnable_objects.map(o => o.type).filter(Boolean)
    ))]
    filterBar.setAvailable(allTypes)
    filterBar.reset()
    filterBar.hidden = allTypes.length === 0
    if (appFilterBar) appFilterBar.hidden = allTypes.length === 0
  }

  if (nowPlayingBar) {
    let trackTitle = ''
    if (currentSourceUrl) {
      try { trackTitle = new URL(currentSourceUrl).hostname } catch { /* noop */ }
    } else if (currentFilename) {
      trackTitle = currentFilename
    }
    nowPlayingBar.setAttribute('track-title', trackTitle)
  }

  if (resultsTransport) {
    const show = canSpeak && sentences.length > 0
    resultsTransport.hidden = !show
    if (show && playbackEngine.state === 'idle') {
      const totalChars = sentences.reduce((s, r) => s + (r.text?.length ?? 0), 0)
      const estDur = Math.max(totalChars / 14, 2)
      if (resultsTimeLabel) resultsTimeLabel.textContent = `00:00\u2009/\u2009${_transportFmt(estDur)}`
      if (resultsScrubber) resultsScrubber.value = '0'
    }
  }
}


// ── Inline annotation builder ─────────────────────────────────────────────────

function buildAnnotatedText(text, items, language, dir, tokenMode, scriptFam) {
  const p = document.createElement('span')
  p.className = 'sentence-card__text reader-sentence__text'
  p.setAttribute('lang', language)
  p.setAttribute('dir',  dir)
  p.dataset.tokenization = tokenMode
  p.dataset.scriptFamily = scriptFam
  p.dataset.layer        = 'native'

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
    mark.className    = 'reader-annotation'
    if (item.type) mark.classList.add('reader-annotation--' + item.type)
    mark.dataset.type      = item.type
    mark.dataset.objectId  = item.id
    mark.dataset.level     = String(TYPE_LEVEL[item.type] ?? 1)
    // mark.dataset.typeLabel = TYPE_LABELS[item.type] ?? item.type
    mark.dataset.typeLabel = t(TYPE_LABEL_KEYS[item.type] ?? 'type_unknown')
    mark.setAttribute('role', 'button')
    mark.setAttribute('tabindex', '0')
    const typeLong  = TYPE_LABELS_LONG_I18N[currentUiLang()]?.[`type_${item.type}_long`] 
               ?? TYPE_LABELS_LONG_I18N.en[`type_${item.type}_long`]
    mark.setAttribute('aria-label', typeLong)
    mark.textContent = text.slice(start, end)
    if (localStorage.getItem(`mn-note-${item.id}`)) mark.setAttribute('data-has-note', '')
    mark.addEventListener('click', () => {
      mark.dispatchEvent(new CustomEvent('lesson-open', {
        bubbles: true,
        detail:  { objectId: item.id, language },
      }))
    })
    mark.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); mark.click() }
    })
    mark.addEventListener('focus', () => announce(`Annotation: ${item.label}`))
    p.appendChild(mark)
    cursor = end
  }

  if (cursor < text.length) p.appendChild(document.createTextNode(text.slice(cursor)))

  return p
}


// ── Annotation density minimap ────────────────────────────────────────────────

const _MINIMAP_COLORS = {
  vocabulary:      'var(--ann-vocab)',
  conjugation:     'var(--ann-grammar)',
  agreement:       'var(--ann-grammar)',
  grammar:         'var(--ann-grammar)',
  idiom:           'var(--ann-idiom)',
  nuance:          'var(--ann-literary)',
  phrase_family:   'var(--ann-literary)',
  script:          'var(--ann-etymology)',
  transliteration: 'var(--ann-etymology)',
}

function buildMinimap() {
  if (!annotationMinimap) return
  annotationMinimap.replaceChildren()

  const marks = Array.from(results.querySelectorAll('.reader-annotation:not([data-filtered])'))
  if (!marks.length) { annotationMinimap.hidden = true; return }

  const region = annotationMinimap.parentElement
  const regionRect = region.getBoundingClientRect()
  const regionTop  = regionRect.top + window.scrollY
  const totalH     = region.offsetHeight
  if (!totalH) return

  const frag = document.createDocumentFragment()
  marks.forEach(mark => {
    const markRect = mark.getBoundingClientRect()
    const markTop  = markRect.top + window.scrollY
    const pct      = Math.max(0, Math.min(99, (markTop - regionTop) / totalH * 100))
    const tick     = document.createElement('div')
    tick.className = 'annotation-minimap__tick'
    tick.style.top        = `${pct.toFixed(2)}%`
    tick.style.background = _MINIMAP_COLORS[mark.dataset.type] ?? 'var(--muted)'
    frag.appendChild(tick)
  })
  annotationMinimap.appendChild(frag)
  annotationMinimap.hidden = false
}


// ── Annotation filters ────────────────────────────────────────────────────────

function applyAnnotationFilter() {
  results?.querySelectorAll('.reader-annotation').forEach(mark => {
    mark.toggleAttribute('data-filtered', activeFilterTypes !== null && !activeFilterTypes.has(mark.dataset.type))
  })
  requestAnimationFrame(buildMinimap)
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

}

window.addEventListener('online', drainReviewQueue)


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


// ── Deep-link: ?annotation=ID&language=CODE ───────────────────────────────────
// Allows sharing a direct URL to a specific annotation.
// Loaded by the share button in the detail pane.  Works without parsed text.

const _dlAnnotation = new URLSearchParams(location.search).get('annotation')
const _dlLanguage   = new URLSearchParams(location.search).get('language')

async function _openDeepLink() {
  if (!_dlAnnotation) return
  const lang   = _dlLanguage || languageSelect.value
  const caps   = languageCapabilities.get(lang)
  const ttsTag = caps?.tts_lang_tag ?? lang
  const dir    = caps?.direction ?? 'ltr'

  try {
    const url = `${API_BASE}/lesson/${encodeURIComponent(_dlAnnotation)}?language=${encodeURIComponent(lang)}&depth=${encodeURIComponent(currentDepth)}`
    const response = await fetch(url, { headers: getAuthHeaders() })
    if (!response.ok) return
    const lesson = await response.json()
    if (detailPane) {
      detailPane.show({
        lesson,
        sentenceText: '',
        language: lang,
        dir,
        ttsTag,
        caps,
        depth: currentDepth,
        onSpeak: (text, l) => speakText(text, l ?? ttsTag),
        onStudy: () => modal.open({
          lesson,
          objectId: lesson.id,
          caps,
          language: lang,
          onRate:   submitReview,
          onSpeak:  (text) => speakText(text, ttsTag),
        }),
      })
      openDetail()
      paneBackdrop?.classList.add('is-visible')
    }
  } catch { /* best-effort — user may not be authed yet */ }
}


// ── Auth init ─────────────────────────────────────────────────────────────────

initAuth()
