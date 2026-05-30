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
import { initUiLanguage, t, ti, currentUiLang, TYPE_LABELS_LONG_I18N, CAPABILITY_LABELS_I18N } from './i18n.js'
import { initReviewSession } from './review-session.js'
import { openDetail, closeDetail } from './layout.js'
import { API_BASE } from './config.js'
import { buildLessonPipelinePayload, validateLessonPipelinePayload } from './lesson-pipeline.js'

initUiLanguage()

// ── OS theme tracking (auto mode) ─────────────────────────────────────────────
// When the user has chosen 'auto', mirror OS preference changes in real time.
;(function () {
  const mq = window.matchMedia('(prefers-color-scheme: dark)')
  mq.addEventListener('change', () => {
    if ((document.documentElement.getAttribute('data-theme') || 'auto') === 'auto') {
      document.dispatchEvent(new CustomEvent('mnemosyne:theme-changed', {
        detail: { theme: 'auto' }, bubbles: false,
      }))
    }
  })
})()

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
const pickerDifficulty  = document.querySelector('#picker-difficulty')
const pickerCloseBtn    = document.querySelector('#picker-close-btn')
const pickerSampleOpenBtn = document.querySelector('#picker-sample-open-btn')
const pickerSampleBtn   = document.querySelector('#picker-sample-btn')
const pickerSampleDialog = document.querySelector('#picker-sample-dialog')
const pickerSampleCloseBtn = document.querySelector('#picker-sample-close-btn')
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
const corpusDrillsBtn    = document.querySelector('#corpus-drills-btn')
const filterBar          = document.querySelector('#filter-bar')
const appFilterBar       = document.querySelector('#app-filter-bar')

const nowPlayingBar      = document.querySelector('#now-playing-bar')
const readingProgress    = document.querySelector('#reading-progress')
const annotationMinimap  = document.querySelector('#annotation-minimap')
const annotationTooltip  = document.querySelector('#annotation-tooltip')
const annotationSearch   = document.querySelector('#annotation-search')
const readingHistoryEl   = document.querySelector('#reading-history')
const readingHistoryList = document.querySelector('#reading-history-list')

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
const termProgressByLanguage = new Map()
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

// ── Reading auto-advance state ─────────────────────────────────────────────────
let _currentSourceDocId   = null  // set by _loadSource; null for pasted/url texts
let _currentSentenceIdx   = -1    // sentence index of the item last opened in the pane
const _sentenceRatedIds   = new Map() // sentenceIdx → Set<objectId> of rated items

// ── Sentence translation state ─────────────────────────────────────────────────
const _sentenceTranslations = new Map() // sentenceIdx → {text, attribution} | null

let currentContentType    = 'pasted_text'
let currentFilename       = null
let currentSourceUrl      = null
let currentFetchedTitle   = null
let currentDocumentTitle  = null
let currentDocumentEyebrow = null
let languageUserSelected  = false
let currentText          = ''   // committed text from picker
let activeFilterTypes    = null  // Set<string> when filtered, null = show all
let activeSearchTerm     = ''   // lowercase string; '' = no search filter
const FILTER_CYCLE       = [null, 'vocab', 'grammar', 'idioms', 'literary', 'etymology']
let _filterCycleIdx      = 0   // index into FILTER_CYCLE; 0 = show all

let isFollowAlongEnabled = false
const ANNOTATION_DEPTH_KEY = 'mn-annotation-depth'
const DEPTH_FALLBACK = 'learning'
let currentDepth = localStorage.getItem(ANNOTATION_DEPTH_KEY) || DEPTH_FALLBACK

const languageCapabilities = new Map()
let currentCaps = null
let scriptView  = 'native'

const MAX_FILE_BYTES = 1_048_576  // 1 MiB
// Fallback used before GET /parse/limits responds.  Must match Settings.max_job_chars default.
const DEFAULT_MAX_JOB_CHARS = 500_000
let maxJobChars = DEFAULT_MAX_JOB_CHARS

// ── Annotation type metadata ───────────────────────────────────────────────────
// TYPE_LABEL_KEYS : tooltip text shown in the ::before pseudo-element.
// TYPE_LEVEL : 1=vocabulary, 2=grammar/script, 3=idiom/nuance/literary
const TYPE_LABEL_KEYS = {
  vocabulary: 'type_vocabulary_short',
  conjugation: 'type_conjugation_short',
  agreement: 'type_agreement_short',
  inflection: 'type_inflection_short',
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
  inflection:      2,
  grammar:         2,
  script:          2,
  transliteration: 2,
  idiom:           3,
  nuance:          3,
  phrase_family:   3,
}

const ANNOTATION_DEPTH_MODEL = {
  subtle: new Set(['vocabulary']),
  learning: new Set(['vocabulary', 'conjugation', 'agreement', 'inflection', 'grammar']),
  deep: new Set([
    'vocabulary',
    'conjugation',
    'agreement',
    'inflection',
    'grammar',
    'script',
    'transliteration',
    'idiom',
    'nuance',
    'phrase_family',
    'etymology',
    'memory_map',
    'cultural_note',
  ]),
}

if (!ANNOTATION_DEPTH_MODEL[currentDepth]) currentDepth = DEPTH_FALLBACK


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
    ;[['en', 'English'], ['es', 'Spanish'], ['fr', 'French (stub)']].forEach(([code, fallback]) => {
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
  scheduleDifficultyEstimate()
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
  group.setAttribute('aria-label', t('aria_script_view_group'))

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
  _clearDifficultyBadge()
  scheduleDifficultyEstimate()
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
  en: 'At dawn, the train finally reached the coast, and everyone stepped onto the platform in silence. The sea smelled of salt and rain, and for a moment the whole station felt brand new.',
  el: 'Την άνοιξη, τα λιβάδια γεμίζουν με αγριολούλουδα κάθε χρώματος. Οι χωρικοί βγαίνουν στα χωράφια πρωί πρωί και εργάζονται μέχρι το ηλιοβασίλεμα, χαίρονται τη φύση γύρω τους.',
  es: 'El sol brillaba sobre las montañas mientras los viajeros descansaban junto al río. El agua fría refrescaba sus pies cansados después de un largo día de camino.',
  fr: 'Le soleil se couchait sur la ville lorsque Marie aperçut un inconnu assis sur le banc du jardin. Elle hésita un moment avant de s\'approcher et de lui adresser la parole.',
  grc: 'Οὕτως γὰρ ἠγάπησεν ὁ θεὸς τὸν κόσμον, ὥστε τὸν υἱὸν τὸν μονογενῆ ἔδωκεν, ἵνα πᾶς ὁ πιστεύων εἰς αὐτὸν μὴ ἀπόληται ἀλλ᾽ ἔχῃ ζωὴν αἰώνιον. οὐ γὰρ ἀπέστειλεν ὁ θεὸς τὸν υἱὸν εἰς τὸν κόσμον ἵνα κρίνῃ τὸν κόσμον, ἀλλ᾽ ἵνα σωθῇ ὁ κόσμος δι᾽ αὐτοῦ.',
  he: 'בבוקר השקט, עלי הסתכל מהחלון על הרחוב הרטוב מגשם הלילה. הוא אהב את השקט הזה שלפני שהעיר מתעוררת, את הרגע הקצר שבו הכל נראה טהור ואפשרי.',
  it: 'Quella mattina d\'autunno, le foglie cadevano lentamente dagli alberi del parco. Marco sedeva sulla panchina preferita e guardava i bambini giocare, pensando ai tempi in cui anche lui correva su quel prato.',
  ja: '春の朝、桜の花びらが風に舞っていた。公園のベンチに座った老人は、静かに目を閉じ、長い人生の思い出に浸っていた。',
  la: 'Antiquis temporibus Roma erat magna urbs et caput mundi. Cives Romani in viis angustis habitabant et multa negotia in foro agebant. Lingua Latina in omnibus partibus imperii audiri poterat.',
  pt: 'Naquela tarde de verão, Ana caminhou até o mercado do bairro para comprar frutas frescas. O vendedor sorriu ao vê-la e separou as melhores laranjas, sabendo que ela sempre escolhia com cuidado.',
  ru: 'Поздним вечером, когда город уже засыпал, она открыла старую книгу и начала читать. Слова на пожелтевших страницах казались живыми и наполненными смыслом.',
  zh: '那个清晨，阳光透过窗帘照进来，照在书桌上那叠厚厚的书上。他拿起最上面的一本，翻到折角的那一页，继续昨晚没有读完的故事。',
}

const EXCLUDED_SAMPLE_LANGUAGES = new Set(['x-cjk-test', 'x-rtl-test'])


function syncSampleLanguagePickerOptions() {
  populateSampleLanguageSelect()
}

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

pickerSampleOpenBtn?.addEventListener('click', () => {
  syncSampleLanguagePickerOptions()
  pickerSampleDialog?.showModal()
})

pickerSampleCloseBtn?.addEventListener('click', () => pickerSampleDialog?.close())

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
  pickerSampleDialog?.close()
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
    scheduleDifficultyEstimate()
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
    updatePickerCharCount()
    scheduleDifficultyEstimate()

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
  scheduleDifficultyEstimate()
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
  currentText      = normalizeParseInput(text)
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
  showChosenText(currentText)
  doParseText(currentText)
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
    const ingestData = await resp.json()
    saveLessonDialog?.close()
    refreshLoadLessonBtn()
    window.mnemosyneRecommended?.reload(ingestData.source_document_id ?? null)
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

// ── Source list item builder ──────────────────────────────────────────────────

function _buildSourceItem(src) {
  const pct       = Math.round((src.completion_fraction ?? 0) * 100)
  const pos       = src.next_position ?? 0
  const total     = src.sentences_total ?? 0
  const started   = pos > 0
  const complete  = src.is_complete ?? false

  const actionKey = complete ? 'source_action_reread'
    : started ? 'source_action_resume'
    : 'source_action_start'

  const li = document.createElement('li')
  li.className = 'load-lesson-list__item'

  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'load-lesson-list__btn'
  btn.dataset.sourceId   = src.id
  btn.dataset.sourceLang = src.language
  btn.addEventListener('click', () => _loadSource(src.id, src.language))

  const titleSpan = document.createElement('span')
  titleSpan.className = 'load-lesson-list__title'
  titleSpan.textContent = src.title || src.language

  const actionSpan = document.createElement('span')
  actionSpan.className = 'load-lesson-list__action'
  actionSpan.textContent = t(actionKey)
  actionSpan.setAttribute('aria-hidden', 'true')

  btn.appendChild(titleSpan)
  btn.appendChild(actionSpan)

  if (total > 0) {
    const progressRow = document.createElement('span')
    progressRow.className = 'load-lesson-list__progress-row'

    const barWrap = document.createElement('span')
    barWrap.className = 'load-lesson-list__progress-bar'
    barWrap.setAttribute('role', 'presentation')

    const fill = document.createElement('span')
    fill.className = 'load-lesson-list__progress-fill'
    fill.style.inlineSize = `${pct}%`
    barWrap.appendChild(fill)

    const label = document.createElement('span')
    label.className = 'load-lesson-list__progress-text'
    label.textContent = complete
      ? t('source_complete')
      : ti('source_progress_text', { pos, total })

    progressRow.appendChild(barWrap)
    progressRow.appendChild(label)
    btn.appendChild(progressRow)
  }

  li.appendChild(btn)

  // Accessible label includes action + title + progress context
  const ariaLabel = `${t(actionKey)}: ${src.title || src.language}`
    + (total > 0 ? ` — ${complete ? t('source_complete') : ti('source_progress_text', { pos, total })}` : '')
  btn.setAttribute('aria-label', ariaLabel)

  return li
}


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
      loadLessonList?.appendChild(_buildSourceItem(src))
    }
  } catch {
    const li = document.createElement('li')
    li.className = 'load-lesson-list__empty'
    li.textContent = t('parse_error_generic')
    loadLessonList?.appendChild(li)
  }
})

loadLessonCloseBtn?.addEventListener('click', () => loadLessonDialog?.close())

// ── Reading history ───────────────────────────────────────────────────────────

function _relativeTime(iso) {
  if (!iso) return ''
  try {
    const diff = Date.now() - new Date(iso).getTime()
    const rtf  = new Intl.RelativeTimeFormat(currentUiLang(), { numeric: 'auto' })
    const min  = Math.floor(diff / 60000)
    if (min < 60) return rtf.format(-Math.max(min, 1), 'minute')
    const hr = Math.floor(min / 60)
    if (hr < 24) return rtf.format(-hr, 'hour')
    return rtf.format(-Math.floor(hr / 24), 'day')
  } catch {
    return ''
  }
}

function _renderReadingHistory(items) {
  if (!readingHistoryList) return
  readingHistoryList.replaceChildren()
  items.forEach(item => {
    const li    = document.createElement('li')
    li.className = 'reading-history__item'
    const pct   = Math.round((item.completion_fraction ?? 0) * 100)
    const rawTitle = item.title ?? item.source_document_id
    const title = rawTitle.length > 55 ? rawTitle.slice(0, 52) + '…' : rawTitle

    const meta = document.createElement('div')
    meta.className = 'reading-history__meta'

    const lang = document.createElement('span')
    lang.className   = 'reading-history__lang'
    lang.textContent = item.language

    const titleEl = document.createElement('span')
    titleEl.className   = 'reading-history__title'
    titleEl.textContent = title
    titleEl.title       = rawTitle

    meta.append(lang, titleEl)

    const barWrap = document.createElement('div')
    barWrap.className     = 'reading-history__bar-wrap'
    barWrap.setAttribute('role', 'progressbar')
    barWrap.setAttribute('aria-valuenow', String(pct))
    barWrap.setAttribute('aria-valuemin', '0')
    barWrap.setAttribute('aria-valuemax', '100')

    const bar = document.createElement('div')
    bar.className = 'reading-history__bar'
    bar.style.setProperty('--_prog', String(item.completion_fraction ?? 0))
    barWrap.appendChild(bar)

    const footer = document.createElement('div')
    footer.className = 'reading-history__footer'

    const pctEl = document.createElement('span')
    pctEl.className   = 'reading-history__pct'
    pctEl.textContent = `${pct}%`

    const dateEl = document.createElement('span')
    dateEl.className   = 'reading-history__date'
    dateEl.textContent = _relativeTime(item.last_read_at)

    const btn = document.createElement('button')
    btn.type      = 'button'
    btn.className = 'ghost-button ghost-button--small reading-history__btn'
    btn.setAttribute('data-i18n', 'reading_resume_btn')
    btn.textContent = t('reading_resume_btn')
    btn.addEventListener('click', () => {
      parseDialog?.close()
      _loadSource(item.source_document_id, item.language, item.next_position)
    })

    footer.append(pctEl, dateEl, btn)
    li.append(meta, barWrap, footer)
    readingHistoryList.appendChild(li)
  })
}

async function _fetchReadingHistory() {
  if (!readingHistoryEl) return
  try {
    const resp = await fetch(`${API_BASE}/reading?limit=3`, { headers: getAuthHeaders() })
    if (!resp.ok) { readingHistoryEl.hidden = true; return }
    const data = await resp.json()
    if (!data.items?.length) { readingHistoryEl.hidden = true; return }
    _renderReadingHistory(data.items)
    readingHistoryEl.hidden = false
  } catch {
    readingHistoryEl.hidden = true
  }
}

async function _loadSource(sourceId, language, resumeAt = 0) {
  loadLessonDialog?.close()
  corpusBrowserDialog?.close()
  _currentSourceDocId = sourceId
  _sentenceRatedIds.clear()
  _sentenceTranslations.clear()
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
    renderResults(buildLessonPipelinePayload({
      sourceText: data.sentences.map(s => s.text).join(" "),
      normalizedText: data.sentences.map(s => s.text).join(" "),
      parseData: data,
      suggestedNextPassage: null,
    }), data.language)
    setStatus(ti('sentences_parsed', { n: data.sentences.length }))
    if (saveLessonBtn) saveLessonBtn.hidden = false
    if (resumeAt > 0) {
      requestAnimationFrame(() => {
        const card = results?.querySelector(`[data-sentence-index="${resumeAt}"]`)
        card?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      })
    }
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


// ── Difficulty estimator ──────────────────────────────────────────────────────

const _DIFF_DEBOUNCE_MS  = 800
const _DIFF_MIN_CHARS    = 40
let   _diffTimer         = null
let   _diffLastText      = ''
let   _diffLastLang      = ''

function scheduleDifficultyEstimate() {
  clearTimeout(_diffTimer)
  _diffTimer = setTimeout(_runDifficultyEstimate, _DIFF_DEBOUNCE_MS)
}

function _clearDifficultyBadge() {
  if (!pickerDifficulty) return
  pickerDifficulty.hidden = true
  pickerDifficulty.replaceChildren()
}

async function _runDifficultyEstimate() {
  if (!pickerDifficulty) return
  const text = pickerTextarea?.value.trim() ?? ''
  const lang = languageSelect?.value ?? ''
  if (!lang || text.length < _DIFF_MIN_CHARS) { _clearDifficultyBadge(); return }
  if (text === _diffLastText && lang === _diffLastLang) return
  _diffLastText = text
  _diffLastLang = lang

  try {
    const resp = await fetch(`${API_BASE}/estimate-difficulty`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body:    JSON.stringify({ text, language: lang }),
    })
    if (!resp.ok) { _clearDifficultyBadge(); return }
    const data = await resp.json()
    if (!data.estimated_cefr) { _clearDifficultyBadge(); return }

    const badge = document.createElement('span')
    badge.className = 'picker-difficulty__badge'
    badge.textContent = data.estimated_cefr

    const label = document.createElement('span')
    label.textContent = t('difficulty_label')

    pickerDifficulty.replaceChildren(label, badge)

    const _CAP_KEY_MAP = {
      full:              'cap_label_full',
      morphology_light:  'cap_label_morphology_light',
      dictionary:        'cap_label_dictionary',
      segmentation_only: 'cap_label_segmentation_only',
    }
    const caps = languageCapabilities.get(lang)
    if (caps) {
      const capKey  = _CAP_KEY_MAP[caps.analysis_depth] ?? null
      const capText = capKey
        ? (CAPABILITY_LABELS_I18N[currentUiLang]?.[capKey] ?? caps.analysis_depth_label)
        : caps.analysis_depth_label
      if (capText) {
        const chip = document.createElement('span')
        chip.className = 'picker-difficulty__cap'
        chip.textContent = capText
        pickerDifficulty.appendChild(chip)
      }
    }

    if (!data.confident) {
      const note = document.createElement('span')
      note.className = 'picker-difficulty__note'
      note.textContent = `(${t('difficulty_indicative')})`
      pickerDifficulty.appendChild(note)
    }

    pickerDifficulty.hidden = false
  } catch {
    _clearDifficultyBadge()
  }
}


// ── Vocabulary browser ────────────────────────────────────────────────────────

const vocabBrowserDialog    = document.querySelector('#vocab-browser-dialog')
const vocabBrowserCloseBtn  = document.querySelector('#vocab-browser-close-btn')
const openVocabBrowserBtn   = document.querySelector('#open-vocab-browser-btn')
const vocabBrowserSearch    = document.querySelector('#vocab-browser-search')
const vocabBrowserLevel     = document.querySelector('#vocab-browser-level')
const vocabBrowserSort      = document.querySelector('#vocab-browser-sort')
const vocabBrowserList      = document.querySelector('#vocab-browser-list')
const vocabBrowserStatus    = document.querySelector('#vocab-browser-status')
const vocabBrowserCount     = document.querySelector('#vocab-browser-count')
const vocabBrowserMoreBtn   = document.querySelector('#vocab-browser-more-btn')
const vocabExportCsvBtn     = document.querySelector('#vocab-export-csv-btn')
const vocabExportAnkiBtn    = document.querySelector('#vocab-export-anki-btn')

const _VOCAB_PAGE_SIZE = 50
let _vocabOffset = 0
let _vocabTotal  = 0
let _vocabSearchTimer = null

function _vocabParams() {
  const p = new URLSearchParams()
  const q = vocabBrowserSearch?.value.trim()
  const lv = vocabBrowserLevel?.value
  const sort = vocabBrowserSort?.value || 'mastery'
  const lang = languageSelect?.value
  if (lang)  p.set('language', lang)
  if (q)     p.set('q', q)
  if (lv)    p.set('level', lv)
  p.set('sort', sort)
  p.set('limit', String(_VOCAB_PAGE_SIZE))
  p.set('offset', String(_vocabOffset))
  return p
}

async function _loadVocab(append = false) {
  if (!vocabBrowserList) return
  if (!append) {
    _vocabOffset = 0
    vocabBrowserList.replaceChildren()
  }
  if (vocabBrowserStatus) vocabBrowserStatus.textContent = t('vocab_loading')
  if (vocabBrowserMoreBtn) vocabBrowserMoreBtn.hidden = true

  try {
    const resp = await fetch(`${API_BASE}/users/me/vocabulary?${_vocabParams()}`, {
      headers: getAuthHeaders(),
    })
    if (!resp.ok) throw new Error(`${resp.status}`)
    const data = await resp.json()
    _vocabTotal = data.total

    if (vocabBrowserStatus) vocabBrowserStatus.textContent = ''

    if (data.items.length === 0 && !append) {
      const li = document.createElement('li')
      li.className = 'vocab-browser-item'
      li.textContent = t('vocab_empty')
      vocabBrowserList.appendChild(li)
    } else {
      for (const item of data.items) {
        const li = document.createElement('li')
        li.className = 'vocab-browser-item'

        const wordSpan = document.createElement('span')
        wordSpan.className = 'vocab-browser-item__word'
        wordSpan.textContent = item.display_label || item.canonical_form

        const meta = document.createElement('span')
        meta.className = 'vocab-browser-item__meta'

        if (item.cefr_level) {
          const cefr = document.createElement('span')
          cefr.className = 'vocab-browser-item__cefr'
          cefr.textContent = item.cefr_level
          meta.appendChild(cefr)
        }

        const mastery = document.createElement('span')
        mastery.className = 'vocab-browser-item__mastery'
        mastery.textContent = `${Math.round(item.mastery_score * 100)}%`
        meta.appendChild(mastery)

        li.appendChild(wordSpan)
        li.appendChild(meta)

        if (item.gloss) {
          const gloss = document.createElement('span')
          gloss.className = 'vocab-browser-item__gloss'
          gloss.textContent = item.gloss
          li.appendChild(gloss)
        }

        vocabBrowserList.appendChild(li)
      }
      _vocabOffset += data.items.length
    }

    const shown = Math.min(_vocabOffset, _vocabTotal)
    if (vocabBrowserCount) {
      vocabBrowserCount.textContent = ti('vocab_count', { shown, total: _vocabTotal })
    }
    if (vocabBrowserMoreBtn) {
      vocabBrowserMoreBtn.hidden = _vocabOffset >= _vocabTotal
    }
  } catch (err) {
    if (vocabBrowserStatus) vocabBrowserStatus.textContent = t('parse_error_generic')
  }
}

function _scheduleVocabSearch() {
  clearTimeout(_vocabSearchTimer)
  _vocabSearchTimer = setTimeout(() => _loadVocab(false), 350)
}

openVocabBrowserBtn?.addEventListener('click', () => {
  vocabBrowserDialog?.showModal()
  _loadVocab(false)
})

vocabBrowserCloseBtn?.addEventListener('click', () => vocabBrowserDialog?.close())
vocabBrowserDialog?.addEventListener('cancel', (e) => {
  if (!vocabBrowserDialog.matches(':modal')) e.preventDefault()
})

vocabBrowserSearch?.addEventListener('input', _scheduleVocabSearch)
vocabBrowserLevel?.addEventListener('change', () => _loadVocab(false))
vocabBrowserSort?.addEventListener('change', () => _loadVocab(false))
vocabBrowserMoreBtn?.addEventListener('click', () => _loadVocab(true))

async function _downloadVocabExport(format) {
  const btn = format === 'csv' ? vocabExportCsvBtn : vocabExportAnkiBtn
  if (!btn) return
  const orig = btn.textContent
  btn.disabled = true
  btn.textContent = t('vocab_export_busy')

  try {
    const p = new URLSearchParams({ format })
    const lang = languageSelect?.value
    const lv   = vocabBrowserLevel?.value
    const q    = vocabBrowserSearch?.value.trim()
    if (lang) p.set('language', lang)
    if (lv)   p.set('level', lv)
    if (q)    p.set('q', q)

    const resp = await fetch(`${API_BASE}/users/me/vocabulary/export?${p}`, {
      headers: getAuthHeaders(),
    })
    if (!resp.ok) throw new Error(resp.status)

    const blob = await resp.blob()
    const cd   = resp.headers.get('content-disposition') ?? ''
    const fnMatch = cd.match(/filename="([^"]+)"/)
    const filename = fnMatch ? fnMatch[1] : `mnemosyne_vocabulary.${format === 'anki' ? 'txt' : 'csv'}`

    const url = URL.createObjectURL(blob)
    const a   = document.createElement('a')
    a.href     = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch {
    // Download failure is silent — user sees no response; no state to roll back.
  } finally {
    btn.disabled = false
    btn.textContent = orig
  }
}

vocabExportCsvBtn?.addEventListener('click', () => _downloadVocabExport('csv'))
vocabExportAnkiBtn?.addEventListener('click', () => _downloadVocabExport('anki'))


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


function normalizeParseInput(rawText) {
  const text = (rawText ?? '').trim()
  if (!text) return ''
  const looksLikeHtml = /<[^>]+>/.test(text) && /<\/(div|span|mark|p|article|section|main)>/i.test(text)
  if (!looksLikeHtml) return text

  const doc = new DOMParser().parseFromString(text, 'text/html')
  doc.querySelectorAll('script, style, noscript').forEach(el => el.remove())
  return (doc.body?.textContent || '').replace(/\s+/g, ' ').trim()
}

async function doParseText(text) {
  const normalizedText = normalizeParseInput(text)
  reviewStateByObject.clear()
  showResultsMessage(t('loading'))
  setStatus(t('parsing_status'), 'busy')
  setJobProgress(2, t('parsing_status'))

  try {
    const language = languageSelect.value
    const data = await parseWithJob(normalizedText, language)
    window.mnemosyneRecommended?.setExcludedParsedText(data.parsed_text_id ?? null)
    const pipelinePayload = buildLessonPipelinePayload({
      sourceText: text,
      normalizedText,
      parseData: data,
      suggestedNextPassage: null,
    })

    if (pipelinePayload.sentences.length === 0) {
      showResultsMessage(t('no_items_found'))
      setStatus(t('no_sentences_found'))
      if (saveLessonBtn) saveLessonBtn.hidden = true
      return
    }

    if (chosenTextDisplay) chosenTextDisplay.hidden = true
    renderResults(pipelinePayload, language)
    const n = pipelinePayload.sentences.length
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


// ── Translation callback factory ─────────────────────────────────────────────

function makeTranslateCallback(lesson) {
  return async (text, sourceLang, targetLang) => {
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
  }
}


// ── Lesson open ───────────────────────────────────────────────────────────────

results.addEventListener('lesson-open', async (event) => {
  const { objectId, language, source } = event.detail
  const caps   = languageCapabilities.get(language)
  const ttsTag = caps?.tts_lang_tag ?? language
  const dir    = caps?.direction ?? 'ltr'

  // Resolve the originating annotation: prefer detail.source (set by the
  // inline preview CTA when dispatching on #results), then event.target's
  // own closest annotation, then event.target itself.
  const originEl = source
    ?? event.target?.closest?.('.reader-annotation')
    ?? event.target
  const sentenceCard = originEl?.closest?.('.sentence-card')
  const sentenceText = sentenceCard?.querySelector('.sentence-card__text')?.textContent ?? ''
  _currentSentenceIdx = parseInt(sentenceCard?.dataset.sentenceIndex ?? '-1', 10)

  const phrase = originEl?.getAttribute?.('aria-label') ?? objectId
  announce(ti('aria_loading_details', { phrase }))
  setStatus(t('loading_lesson'), 'busy')

  try {
    const url = `${API_BASE}/lesson/${encodeURIComponent(objectId)}?language=${encodeURIComponent(language)}&depth=${encodeURIComponent(currentDepth)}`
    const response = await fetch(url, { headers: getAuthHeaders() })

    if (!response.ok) {
      const body = await response.json().catch(() => null)
      throw new Error(body?.detail ?? `Lesson not available (${response.status})`)
    }

    const lesson = await response.json()
    const progressRows = await getTermProgress(language)
    const dueQueue = progressRows
      .filter((row) => row.review_bucket === 'due')
      .sort((a, b) => Date.parse(a.next_review_at || '') - Date.parse(b.next_review_at || ''))
      .slice(0, 8)

    // Open the detail pane as the primary view.
    // "Study drills" inside the pane delegates to the existing modal.
    if (detailPane) {
      const uiLang = currentUiLang()
      const termProgress = progressRows.find(row => row.source_lesson_ids?.includes(lesson.id)) ?? null

      // Open the shell column FIRST so the pane has non-zero width to animate
      // into. Mirrors the ordering used by other call sites (e.g. recommended
      // reading), where show() runs after openDetail().
      openDetail()

      detailPane.show({
        lesson,
        sentenceText,
        language,
        dir,
        ttsTag,
        caps,
        depth: currentDepth,
        uiLang,
        onTranslate: makeTranslateCallback(lesson),
        reviewQueue: dueQueue,
        termProgress,
        onSpeak:  (text, lang) => speakText(text, lang ?? ttsTag),
        onStudy:  () => modal.open({
          lesson,
          objectId: lesson.id,
          caps,
          language,
          onRate:  submitReview,
          onSpeak: (text) => speakText(text, ttsTag),
          onCheckResult: (check) => { void submitLessonCheck(lesson, language, check) },
        }),
      })

      // ── Visual anchor: link annotation to detail pane ─────────────────────
      // Mark the source annotation so CSS can accent it and connect it to the
      // pane's left border.  Also compute the vertical clip origin so the pane
      // entry animation feels anchored to where the click happened.
      document.querySelector('[data-detail-source]')?.removeAttribute('data-detail-source')
      const sourceEl = originEl
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

      }

      // Force re-run of entry animation. Run in the same rAF as show()'s
      // data-open set so the backdrop only becomes pointer-active after the
      // pane already has pointer-events:auto (avoids a click-through window
      // on mobile where the backdrop would intercept and immediately close).
      detailPane.classList.remove('pane-entry-animate')
      requestAnimationFrame(() => {
        paneBackdrop?.classList.add('is-visible')
        detailPane.classList.add('pane-entry-animate')
      })
    } else {
      // Fallback: no detail pane in DOM — open modal directly.
      modal.open({
        lesson,
        objectId: lesson.id,
        caps,
        language,
        onRate:  submitReview,
        onSpeak: (text) => speakText(text, ttsTag),
        onCheckResult: (check) => { void submitLessonCheck(lesson, language, check) },
      })
    }

    setStatus(ti('lesson_open', { title: lesson.title }))
  } catch (error) {
    setStatus(error instanceof Error ? error.message : t('load_lesson_failed'), 'error')
  }
})

// Sync note badges on annotation marks when note is saved/cleared in the pane.
detailPane?.addEventListener('note-updated', ({ detail }) => {
  console.log('pane__note-note-updated', detail);
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

detailPane?.addEventListener('pane-practice-check', ({ detail }) => {
  if (!detail?.lesson || !detail?.language) return
  const objectId = detail.objectId ?? detail.lesson?.id
  if (!objectId) return
  const quality = detail.correct ? ((detail.attempts ?? 1) <= 1 ? 4 : 3) : 1
  const wrongAnswer = !detail.correct && detail.wrongAnswer ? detail.wrongAnswer : null
  void submitReview(objectId, quality, wrongAnswer).then((payload) => {
    if (!payload) return
    termProgressByLanguage.delete(detail.language)

    // Update adaptive-reader memory + minimap immediately using FSRS-derived data.
    if (payload.mastery_score != null) {
      window.dispatchEvent(new CustomEvent('mnemosyne:practice-result', {
        detail: {
          objectId,
          masteryScore:   payload.mastery_score,
          nextReviewAt:   payload.next_review_at,
          reviewCount:    payload.review_count,
          correctCount:   payload.correct_count,
          incorrectCount: payload.incorrect_count,
          reviewBucket:   payload.review_bucket,
        },
      }))
    }

    detailPane.dispatchEvent(new CustomEvent('review-submitted', {
      detail: {
        objectId,
        quality,
        correct:           detail.correct,
        nextIntervalDays:  payload.next_interval_days,
        masteryBefore:     payload.mastery_score_before,
        masteryAfter:      payload.mastery_score,
        reviewBucket:      payload.review_bucket,
      },
    }))

    // Auto-advance when all items in the current sentence have been rated.
    _trackSentenceRating(objectId)
  })
})

function _trackSentenceRating(objectId) {
  const idx = _currentSentenceIdx
  if (idx < 0 || idx >= currentSentences.length) return
  let rated = _sentenceRatedIds.get(idx)
  if (!rated) { rated = new Set(); _sentenceRatedIds.set(idx, rated) }
  rated.add(objectId)
  const sentence  = currentSentences[idx]
  const ratable   = sentence.learnable_objects.map(o => o.id).filter(Boolean)
  if (ratable.length > 0 && ratable.every(id => rated.has(id))) {
    _autoAdvanceSentence(idx)
  }
}

function _autoAdvanceSentence(doneIdx) {
  const nextIdx  = doneIdx + 1
  const nextCard = results?.querySelector(`[data-sentence-index="${nextIdx}"]`)
  if (nextCard) {
    nextCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    nextCard.classList.add('sentence-card--done')
    requestAnimationFrame(() => nextCard.classList.add('sentence-card--done-flash'))
    setTimeout(() => {
      nextCard.classList.remove('sentence-card--done', 'sentence-card--done-flash')
    }, 900)
  }
  if (_currentSourceDocId) {
    void fetch(`${API_BASE}/reading/${encodeURIComponent(_currentSourceDocId)}`, {
      method:  'PATCH',
      headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
      body:    JSON.stringify({ sentences_read: 1 }),
    }).catch(() => { /* non-fatal: progression update best-effort */ })
  }
}

// ── Sentence translation fetch ────────────────────────────────────────────────

async function _fetchSentenceTranslation(sentenceIdx, text, sourceLang, el) {
  const cached = _sentenceTranslations.get(sentenceIdx)
  if (cached !== undefined) {
    _renderSentenceTranslation(el, cached)
    return
  }
  el.textContent = t('sentence_translating')
  try {
    const resp = await fetch(`${API_BASE}/translate`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body:    JSON.stringify({
        text,
        source_language: sourceLang,
        target_language: currentUiLang(),
      }),
    })
    if (!resp.ok) throw new Error(resp.status)
    const data = await resp.json()
    const result = data.translation
      ? { text: data.translation, attribution: data.attribution ?? null }
      : null
    _sentenceTranslations.set(sentenceIdx, result)
    _renderSentenceTranslation(el, result)
  } catch {
    _sentenceTranslations.set(sentenceIdx, null)
    _renderSentenceTranslation(el, null)
  }
}

function _renderSentenceTranslation(el, result) {
  if (!result) {
    el.textContent = t('sentence_translation_na')
    el.dataset.state = 'error'
    return
  }
  el.textContent = result.text
  el.removeAttribute('data-state')
  if (result.attribution) {
    const attr = document.createElement('span')
    attr.className   = 'reader-sentence__translation-attr'
    attr.textContent = result.attribution
    el.appendChild(attr)
  }
}

// ── Corpus confusable drills ──────────────────────────────────────────────────

async function _openCorpusDrills() {
  const language = languageSelect?.value
  if (!language) return

  const nuanceTypes = [
    ...new Set(
      currentSentences.flatMap(s =>
        s.learnable_objects
          .filter(o => o.type === 'nuance' && o.lesson_data?.nuance_type)
          .map(o => o.lesson_data.nuance_type)
      )
    ),
  ]
  if (!nuanceTypes.length) return

  setStatus(t('loading'), 'busy')
  try {
    const params = new URLSearchParams({ language, nuance_types: nuanceTypes.join(','), limit: '8' })
    const resp = await fetch(`${API_BASE}/nuance-drills?${params}`, { headers: getAuthHeaders() })
    if (!resp.ok) throw new Error(resp.status)
    const data = await resp.json()
    if (!data.drills?.length) { setStatus(''); return }

    const caps   = languageCapabilities.get(language)
    const ttsTag = caps?.tts_lang_tag ?? language
    const syntheticLesson = {
      id:          `corpus-drills-${language}`,
      title:       t('corpus_drills_btn'),
      type:        'nuance',
      label:       t('corpus_drills_btn'),
      drills:      data.drills,
      nuance_sets: [],
      examples:    [],
      lesson_data: {},
    }
    setStatus('')
    modal.open({
      lesson:        syntheticLesson,
      objectId:      null,
      caps,
      language,
      onRate:        submitReview,
      onSpeak:       (text) => speakText(text, ttsTag),
      onCheckResult: (check) => { void submitLessonCheck(syntheticLesson, language, check) },
    })
  } catch {
    setStatus(t('load_lesson_failed'), 'error')
  }
}

corpusDrillsBtn?.addEventListener('click', _openCorpusDrills)
changeLessonBtn?.addEventListener('click', _fetchReadingHistory)

// ── Annotation hover tooltip ──────────────────────────────────────────────────

function _showAnnotationTooltip(mark) {
  if (!annotationTooltip) return
  const typeLabel = mark.dataset.typeLabel ?? ''
  const label     = mark.dataset.label ?? ''
  if (!typeLabel && !label) return

  annotationTooltip.innerHTML = ''
  if (typeLabel) {
    const chip = document.createElement('span')
    chip.className   = 'annotation-tooltip__type'
    chip.textContent = typeLabel
    annotationTooltip.appendChild(chip)
  }
  if (label) {
    const el = document.createElement('span')
    el.className   = 'annotation-tooltip__label'
    el.textContent = label
    annotationTooltip.appendChild(el)
  }

  annotationTooltip.removeAttribute('hidden')
  annotationTooltip.removeAttribute('aria-hidden')

  requestAnimationFrame(() => {
    const rect = mark.getBoundingClientRect()
    const tipW  = annotationTooltip.offsetWidth
    const tipH  = annotationTooltip.offsetHeight
    const viewW = window.innerWidth
    const left  = Math.max(8, Math.min(rect.left + rect.width / 2 - tipW / 2, viewW - tipW - 8))
    const top   = rect.top >= tipH + 10 ? rect.top - tipH - 6 : rect.bottom + 6
    annotationTooltip.style.left = `${left}px`
    annotationTooltip.style.top  = `${top}px`
  })
}

function _hideAnnotationTooltip() {
  if (!annotationTooltip) return
  annotationTooltip.setAttribute('hidden', '')
  annotationTooltip.setAttribute('aria-hidden', 'true')
}

results.addEventListener('mouseover', e => {
  const mark = e.target?.closest?.('.reader-annotation')
  if (mark) _showAnnotationTooltip(mark)
  else _hideAnnotationTooltip()
})

results.addEventListener('mouseout', e => {
  if (!e.relatedTarget?.closest?.('.reader-annotation')) _hideAnnotationTooltip()
})

results.addEventListener('focusin', e => {
  const mark = e.target?.closest?.('.reader-annotation')
  if (mark) _showAnnotationTooltip(mark)
})

results.addEventListener('focusout', e => {
  if (!e.relatedTarget?.closest?.('.reader-annotation')) _hideAnnotationTooltip()
})

document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !annotationTooltip?.hasAttribute('hidden')) _hideAnnotationTooltip()
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
    const response = await fetch(url, { headers: getAuthHeaders() })
    if (!response.ok) return
    const lesson = await response.json()
    const progressRows = await getTermProgress(language)
    const dueQueue = progressRows.filter((row) => row.review_bucket === 'due').slice(0, 8)
    if (!detailPane) return
    const uiLang = currentUiLang()
    const termProgress = progressRows.find(row => row.source_lesson_ids?.includes(lesson.id)) ?? null
    openDetail()
    paneBackdrop?.classList.add('is-visible')

    detailPane.show({
      lesson,
      sentenceText: '',
      language,
      dir,
      ttsTag,
      caps,
      depth: currentDepth,
      uiLang,
      onTranslate: makeTranslateCallback(lesson),
      reviewQueue: dueQueue,
      termProgress,
      onSpeak:  (text, l) => speakText(text, l ?? ttsTag),
      onStudy:  () => modal.open({
        lesson,
        objectId: lesson.id,
        caps,
        language,
        onRate:  submitReview,
        onSpeak: (text) => speakText(text, ttsTag),
        onCheckResult: (check) => { void submitLessonCheck(lesson, language, check) },
      }),
    })
  } catch { /* ignore — confusable may not be in store yet */ }
})


// ── Corpus browser ────────────────────────────────────────────────────────────

const corpusBrowserDialog   = document.querySelector('#corpus-browser-dialog')
const corpusBrowserCloseBtn = document.querySelector('#corpus-browser-close-btn')
const openCorpusBrowserBtn  = document.querySelector('#open-corpus-browser-btn')
const corpusBrowserSearch   = document.querySelector('#corpus-browser-search')
const corpusBrowserLang     = document.querySelector('#corpus-browser-lang')
const corpusBrowserType     = document.querySelector('#corpus-browser-type')
const corpusBrowserList     = document.querySelector('#corpus-browser-list')
const corpusBrowserStatus   = document.querySelector('#corpus-browser-status')
const corpusBrowserCount    = document.querySelector('#corpus-browser-count')
const corpusBrowserMoreBtn  = document.querySelector('#corpus-browser-more-btn')

const _CORPUS_PAGE_SIZE = 20
let _corpusOffset = 0
let _corpusTotal  = 0
let _corpusSearchTimer = null

function _corpusParams() {
  const p = new URLSearchParams()
  const q    = corpusBrowserSearch?.value.trim()
  const lang = corpusBrowserLang?.value
  const type = corpusBrowserType?.value
  if (lang)  p.set('language', lang)
  if (type)  p.set('content_type', type)
  if (q)     p.set('q', q)
  p.set('limit', String(_CORPUS_PAGE_SIZE))
  p.set('offset', String(_corpusOffset))
  return p
}

function _buildCorpusItem(item) {
  const li = document.createElement('li')
  li.className = 'corpus-browser-list__item'

  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'corpus-browser-list__btn'

  const titleSpan = document.createElement('span')
  titleSpan.className = 'corpus-browser-list__title'
  titleSpan.textContent = item.title || item.language

  const meta = document.createElement('span')
  meta.className = 'corpus-browser-list__meta'

  const langTag = document.createElement('span')
  langTag.className = 'corpus-browser-list__tag'
  langTag.textContent = item.language.toUpperCase()
  meta.appendChild(langTag)

  if (item.char_count) {
    const chars = document.createElement('span')
    chars.className = 'corpus-browser-list__chars'
    chars.textContent = ti('corpus_char_count', { n: item.char_count.toLocaleString() })
    meta.appendChild(chars)
  }

  const openBtn = document.createElement('button')
  openBtn.type = 'button'
  openBtn.className = 'corpus-browser-list__open'
  openBtn.textContent = t('corpus_open_btn')
  openBtn.addEventListener('click', (e) => {
    e.stopPropagation()
    _loadSource(item.id, item.language)
  })

  btn.appendChild(titleSpan)
  btn.appendChild(meta)
  btn.appendChild(openBtn)
  btn.addEventListener('click', () => _loadSource(item.id, item.language))

  // Progress bar for started documents
  if (item.started && item.sentences_total > 0) {
    const prog = document.createElement('div')
    prog.className = 'corpus-browser-list__progress'
    const fill = document.createElement('span')
    fill.className = 'corpus-browser-list__progress-fill'
    fill.style.inlineSize = `${Math.round((item.completion_fraction ?? 0) * 100)}%`
    prog.appendChild(fill)
    li.appendChild(prog)
  }

  li.appendChild(btn)

  const pct = Math.round((item.completion_fraction ?? 0) * 100)
  const progressText = item.is_complete
    ? t('source_complete')
    : item.started
      ? ti('source_progress_text', { pos: item.next_position, total: item.sentences_total })
      : ''
  btn.setAttribute('aria-label',
    `${t('corpus_open_btn')}: ${item.title || item.language}${progressText ? ` — ${progressText}` : ''}`)

  return li
}

async function _loadCorpus(append = false) {
  if (!corpusBrowserList) return
  if (!append) {
    _corpusOffset = 0
    corpusBrowserList.replaceChildren()
  }
  if (corpusBrowserStatus) corpusBrowserStatus.textContent = t('vocab_loading')
  if (corpusBrowserMoreBtn) corpusBrowserMoreBtn.hidden = true

  try {
    const resp = await fetch(`${API_BASE}/corpus?${_corpusParams()}`, {
      headers: getAuthHeaders(),
    })
    if (!resp.ok) throw new Error(`${resp.status}`)
    const data = await resp.json()
    _corpusTotal = data.total

    if (corpusBrowserStatus) corpusBrowserStatus.textContent = ''

    if (data.items.length === 0 && !append) {
      const li = document.createElement('li')
      li.className = 'corpus-browser-list__empty'
      li.textContent = t('corpus_empty')
      corpusBrowserList.appendChild(li)
    } else {
      for (const item of data.items) {
        corpusBrowserList.appendChild(_buildCorpusItem(item))
      }
      _corpusOffset += data.items.length
    }

    if (corpusBrowserCount) {
      corpusBrowserCount.textContent = ti('corpus_count', { n: _corpusTotal })
    }
    if (corpusBrowserMoreBtn) {
      corpusBrowserMoreBtn.hidden = _corpusOffset >= _corpusTotal
    }
  } catch {
    if (corpusBrowserStatus) corpusBrowserStatus.textContent = t('load_lesson_failed')
  }
}

function _populateCorpusLangSelect() {
  if (!corpusBrowserLang) return
  const current = corpusBrowserLang.value
  const placeholder = corpusBrowserLang.querySelector('option[value=""]')
  const options = [...languageCapabilities.entries()]
    .filter(([code]) => !['x-cjk-test', 'x-rtl-test'].includes(code))
    .map(([code, caps]) => {
      const opt = document.createElement('option')
      opt.value = code
      const label = t('lesson_lang_' + code)
      opt.textContent = (label && label !== 'lesson_lang_' + code) ? label : caps.name || code
      return opt
    })
  corpusBrowserLang.replaceChildren(
    placeholder ?? (() => {
      const o = document.createElement('option'); o.value = ''; o.textContent = t('choose_language'); return o
    })(),
    ...options,
  )
  corpusBrowserLang.value = current
}

openCorpusBrowserBtn?.addEventListener('click', async () => {
  _populateCorpusLangSelect()
  corpusBrowserDialog?.showModal()
  await _loadCorpus()
})

corpusBrowserCloseBtn?.addEventListener('click', () => corpusBrowserDialog?.close())
corpusBrowserDialog?.addEventListener('click', e => {
  if (e.target === corpusBrowserDialog) corpusBrowserDialog.close()
})

corpusBrowserSearch?.addEventListener('input', () => {
  clearTimeout(_corpusSearchTimer)
  _corpusSearchTimer = setTimeout(() => _loadCorpus(), 300)
})

corpusBrowserLang?.addEventListener('change', () => _loadCorpus())
corpusBrowserType?.addEventListener('change', () => _loadCorpus())

corpusBrowserMoreBtn?.addEventListener('click', () => _loadCorpus(true))


// ── TopNav event wiring ───────────────────────────────────────────────────────

const topNav = document.querySelector('mnemosyne-top-nav')
if (topNav && currentDepth) topNav.depth = currentDepth


topNav?.addEventListener('depth-change', ({ detail }) => {
  currentDepth = detail.depth
  localStorage.setItem(ANNOTATION_DEPTH_KEY, currentDepth)
  detailPane?.updateDepth(detail.depth)
  applyAnnotationFilter()
})

document.addEventListener('mnemosyne:mode-changed', ({ detail }) => {
  currentDepth = detail.mode
  applyAnnotationFilter()
})

filterBar?.addEventListener('filter-change', ({ detail }) => {
  activeFilterTypes = detail.types.length ? new Set(detail.types) : null
  if (!detail.active.length) {
    _filterCycleIdx = 0
  } else {
    const idx = FILTER_CYCLE.indexOf(detail.active[0])
    if (idx >= 0) _filterCycleIdx = idx
  }
  applyAnnotationFilter()
})

if (annotationSearch) {
  let _searchDebounce = null
  annotationSearch.addEventListener('input', () => {
    clearTimeout(_searchDebounce)
    _searchDebounce = setTimeout(() => {
      activeSearchTerm = annotationSearch.value.trim().toLowerCase()
      applyAnnotationFilter()
    }, 180)
  })
  annotationSearch.addEventListener('search', () => {
    activeSearchTerm = annotationSearch.value.trim().toLowerCase()
    applyAnnotationFilter()
  })
}

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

  // Whether results are currently rendered.
  const hasResults = resultsSection && !resultsSection.hidden

  switch (e.key) {
    case '?':
      if (!inButton) { e.preventDefault(); openShortcuts() }
      break

    case ' ':
      // Space activates the focused button natively; only intercept in dead space.
      if (!inButton && playbackEngine.state !== 'idle') {
        e.preventDefault()
        playbackEngine.togglePause()
        announce(playbackEngine.state === 'playing' ? t('aria_paused') : t('aria_resumed'))
      }
      break

    case 'ArrowLeft':
      if (!inButton && playbackEngine.state !== 'idle') {
        e.preventDefault()
        playbackEngine.prev()
        announce(t('aria_prev_sentence'))
      }
      break

    case 'ArrowRight':
      if (!inButton && playbackEngine.state !== 'idle') {
        e.preventDefault()
        playbackEngine.next()
        announce(t('aria_next_sentence'))
      }
      break

    case 'l':
    case 'L':
      if (!inButton && !e.ctrlKey && !e.metaKey) {
        e.preventDefault()
        isFollowAlongEnabled = !isFollowAlongEnabled
        announce(isFollowAlongEnabled ? t('aria_follow_along_on') : t('aria_follow_along_off'))
      }
      break

    case 't':
    case 'T':
      if (inButton || e.ctrlKey || e.metaKey || !hasResults) break
      e.preventDefault()
      {
        const focused = /** @type {HTMLElement} */ (e.composedPath()[0])
        const card = focused?.closest?.('.sentence-card')
          ?? results?.querySelector(`[data-sentence-index="${_currentSentenceIdx}"]`)
          ?? results?.querySelector('.sentence-card')
        const translateBtn = card?.querySelector('.reader-sentence__translate-btn')
        if (translateBtn) translateBtn.click()
      }
      break

    case 'd':
    case 'D':
      if (inButton || e.ctrlKey || e.metaKey || !hasResults) break
      if (corpusDrillsBtn?.hidden !== false) break
      e.preventDefault()
      _openCorpusDrills()
      break

    case 'f':
    case 'F':
      if (inButton || e.ctrlKey || e.metaKey) break
      if (!appFilterBar || appFilterBar.hidden) break
      e.preventDefault()
      _filterCycleIdx = (_filterCycleIdx + 1) % FILTER_CYCLE.length
      filterBar?.activateCategory?.(FILTER_CYCLE[_filterCycleIdx])
      break

    case 's':
    case 'S':
      if (inButton || e.ctrlKey || e.metaKey || !hasResults) break
      if (!annotationSearch || appFilterBar?.hidden) break
      e.preventDefault()
      annotationSearch.focus()
      annotationSearch.select()
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
    btn.setAttribute('aria-label',   isPlaying ? t('aria_pause') : t('aria_play_sentence'))
    btn.setAttribute('aria-pressed', String(isActive))
  })

  // Results transport sync
  if (resultsPlayBtn) {
    const idle = state === 'idle'
    resultsPlayBtn.innerHTML        = idle ? `&#x25B6;&thinsp;${t('aria_play_all_sentences')}` : `&#x23F9;&thinsp;${t('aria_stop')}`
    resultsPlayBtn.setAttribute('aria-label', idle ? t('aria_play_all_sentences') : t('aria_stop'))
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
      rnpToggle.setAttribute('aria-label', isPaused ? t('aria_resume') : t('aria_pause'))
    }
  }
})


// ── Render sentence cards ─────────────────────────────────────────────────────

function renderResults(pipelinePayload, language) {
  const payload = validateLessonPipelinePayload(pipelinePayload)
  const sentences = payload.sentences
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
      playBtn.setAttribute('aria-label',   ti('aria_play_sentence_n', { n: sentenceIdx + 1 }))
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

    const debugRanges = []
    row.appendChild(
      buildAnnotatedText(sentence.text, sentence.learnable_objects, language, dir, tokenMode, scriptFam, debugRanges)
    )
    row.dataset.debugRanges = JSON.stringify(debugRanges)
    if (debugRanges.some(r => r.status !== 'selected')) row.dataset.debugIssue = 'true'

    // Translate toggle — skip when reading language matches UI language
    if (language !== currentUiLang()) {
      const translateBtn = document.createElement('button')
      translateBtn.type      = 'button'
      translateBtn.className = 'reader-sentence__translate-btn'
      translateBtn.setAttribute('aria-expanded', 'false')
      translateBtn.setAttribute('aria-label', t('sentence_translate'))
      translateBtn.textContent = t('sentence_translate')

      const translationEl = document.createElement('span')
      translationEl.className = 'reader-sentence__translation'
      translationEl.hidden    = true

      translateBtn.addEventListener('click', () => {
        const expanded = translateBtn.getAttribute('aria-expanded') === 'true'
        if (expanded) {
          translateBtn.setAttribute('aria-expanded', 'false')
          translationEl.hidden = true
        } else {
          translateBtn.setAttribute('aria-expanded', 'true')
          translationEl.hidden = false
          _fetchSentenceTranslation(sentenceIdx, sentence.text, language, translationEl)
        }
      })

      row.appendChild(translateBtn)
      row.appendChild(translationEl)
    }

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

  // Show "Practice confusables" button only when the text has nuance items
  if (corpusDrillsBtn) {
    const hasNuance = sentences.some(s =>
      s.learnable_objects.some(o => o.type === 'nuance')
    )
    corpusDrillsBtn.hidden = !hasNuance
  }

  if (filterBar) {
    const allTypes = [...new Set(sentences.flatMap(s =>
      s.learnable_objects.map(o => o.type).filter(Boolean)
    ))]
    filterBar.setAvailable(allTypes)
    filterBar.reset()
    filterBar.hidden = allTypes.length === 0
    if (appFilterBar) appFilterBar.hidden = allTypes.length === 0
    activeSearchTerm = ''
    if (annotationSearch) annotationSearch.value = ''
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

function buildAnnotatedText(text, items, language, dir, tokenMode, scriptFam, debugRanges = []) {
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
      debugRanges.push({ label: item.label, type: item.type, start: idx, end: idx + item.label.length, status: 'candidate' })
      pos = idx + 1
    }
  }

  const typePriority = {
    conjugation: 6,
    inflection: 5,
    vocabulary: 5,
    nuance: 4,
    grammar: 4,
    idiom: 3,
    phrase_family: 3,
    agreement: 2,
    case_agreement: 2,
  }
  const priorityOf = (r) => typePriority[r?.item?.type] ?? 1

  // Sort by start, then pedagogical priority, then longer match.
  ranges.sort((a, b) => (
    a.start - b.start
    || priorityOf(b) - priorityOf(a)
    || (b.end - b.start) - (a.end - a.start)
  ))

  // Greedy non-overlapping selection with replacement if a higher-priority
  // span competes with the most-recent selected span.
  const selected = []
  for (const r of ranges) {
    const prev = selected[selected.length - 1]
    const overlapsPrev = Boolean(prev) && r.start < prev.end
    if (overlapsPrev) {
      const better = priorityOf(r) > priorityOf(prev)
      const samePriLonger = priorityOf(r) === priorityOf(prev)
        && (r.end - r.start) > (prev.end - prev.start)
      if (better || samePriLonger) {
        const prevMatch = debugRanges.find(x => x.start === prev.start && x.end === prev.end && x.label === prev.item.label)
        if (prevMatch) prevMatch.status = 'overlap_skipped'
        selected[selected.length - 1] = r
        const match = debugRanges.find(x => x.start === r.start && x.end === r.end && x.label === r.item.label)
        if (match) match.status = 'selected'
      } else {
        const match = debugRanges.find(x => x.start === r.start && x.end === r.end && x.label === r.item.label)
        if (match) match.status = 'overlap_skipped'
      }
      continue
    }

    selected.push(r)
    const match = debugRanges.find(x => x.start === r.start && x.end === r.end && x.label === r.item.label)
    if (match) match.status = 'selected'
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
    mark.dataset.label     = item.label ?? ''
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
    mark.addEventListener('focus', () => announce(ti('aria_annotation_focus', { label: item.label })))
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
  inflection:      'var(--ann-grammar)',
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
    const tick     = document.createElement('button')
    tick.type      = 'button'
    tick.className = 'annotation-minimap__tick'
    tick.style.top        = `${pct.toFixed(2)}%`
    tick.style.background = _MINIMAP_COLORS[mark.dataset.type] ?? 'var(--muted)'
    const label = (mark.dataset.type ?? '') + (mark.textContent.trim() ? ': ' + mark.textContent.trim().slice(0, 40) : '')
    tick.setAttribute('aria-label', label)
    tick.addEventListener('click', () => {
      mark.scrollIntoView({ behavior: 'smooth', block: 'center' })
      mark.classList.add('reader-annotation--jump-flash')
      setTimeout(() => mark.classList.remove('reader-annotation--jump-flash'), 700)
    })
    frag.appendChild(tick)
  })
  annotationMinimap.appendChild(frag)
  annotationMinimap.hidden = false
}


// ── Annotation filters ────────────────────────────────────────────────────────

function applyAnnotationFilter() {
  const depthTypes = ANNOTATION_DEPTH_MODEL[currentDepth] ?? ANNOTATION_DEPTH_MODEL[DEPTH_FALLBACK]
  results?.querySelectorAll('.reader-annotation').forEach(mark => {
    const typeAllowedByDepth      = depthTypes.has(mark.dataset.type)
    const typeAllowedByUserFilter = activeFilterTypes === null || activeFilterTypes.has(mark.dataset.type)
    const searchAllowed           = !activeSearchTerm
      || mark.textContent.toLowerCase().includes(activeSearchTerm)
      || (mark.dataset.label ?? '').toLowerCase().includes(activeSearchTerm)
    mark.toggleAttribute('data-filtered', !(typeAllowedByDepth && typeAllowedByUserFilter && searchAllowed))
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

async function submitReview(objectId, quality, wrongAnswer = null) {
  const body = {
    object_id:    objectId,
    quality,
    review_state: reviewStateByObject.get(objectId) ?? null,
    ...(wrongAnswer ? { wrong_answer: wrongAnswer } : {}),
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

async function submitLessonCheck(lesson, language, check) {
  const term = check?.term || lesson?.lesson_data?.lemma || lesson?.examples?.[0] || lesson?.title
  if (!term || !language || !check) return
  const response = await fetch(`${API_BASE}/term-progress`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body: JSON.stringify({
      term,
      lemma: lesson?.lesson_data?.lemma || term,
      language,
      seen: true,
      reviewed: true,
      correct: Boolean(check.correct),
      mastery_delta: check.correct ? 0.08 : -0.1,
      source_lesson_id: lesson.id,
    }),
  })
  termProgressByLanguage.delete(language)
  if (response.ok && lesson?.id) {
    try {
      const tp = await response.json()
      window.dispatchEvent(new CustomEvent('mnemosyne:practice-result', {
        detail: {
          objectId:      lesson.id,
          masteryScore:  tp.mastery_score,
          nextReviewAt:  tp.next_review_at,
          reviewCount:   tp.review_count,
          correctCount:  tp.correct_count,
          incorrectCount: tp.incorrect_count,
          reviewBucket:  tp.review_bucket,
        },
      }))
    } catch {}
  }
}

async function getTermProgress(language) {
  if (!language) return []
  if (termProgressByLanguage.has(language)) return termProgressByLanguage.get(language) || []
  try {
    const response = await fetch(`${API_BASE}/term-progress/${encodeURIComponent(language)}?limit=300`, {
      headers: { ...getAuthHeaders() },
    })
    if (!response.ok) return []
    const rows = await response.json()
    termProgressByLanguage.set(language, rows)
    return rows
  } catch {
    return []
  }
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
    const progressRows = await getTermProgress(lang)
    const dueQueue = progressRows.filter((row) => row.review_bucket === 'due').slice(0, 8)
    if (detailPane) {
      const uiLang = currentUiLang()
      const termProgress = progressRows.find(row => row.source_lesson_ids?.includes(lesson.id)) ?? null
      openDetail()
      detailPane.show({
        lesson,
        sentenceText: '',
        language: lang,
        dir,
        ttsTag,
        caps,
        depth: currentDepth,
        uiLang,
        onTranslate: makeTranslateCallback(lesson),
        reviewQueue: dueQueue,
        termProgress,
        onSpeak: (text, l) => speakText(text, l ?? ttsTag),
        onStudy: () => modal.open({
          lesson,
          objectId: lesson.id,
          caps,
          language: lang,
          onRate:   submitReview,
          onSpeak:  (text) => speakText(text, ttsTag),
          onCheckResult: (check) => { void submitLessonCheck(lesson, lang, check) },
        }),
      })
      paneBackdrop?.classList.add('is-visible')
    }
  } catch { /* best-effort — user may not be authed yet */ }
}


// ── Auth init ─────────────────────────────────────────────────────────────────

initAuth()

// ── Review session + reading history init (runs once #main-content becomes visible)
;(function () {
  const mc = document.querySelector('#main-content')
  if (!mc) return
  let _initialized = false
  function _maybeInit() {
    if (mc.hidden) return
    initReviewSession()
    if (!_initialized) { _initialized = true; _fetchReadingHistory() }
  }
  _maybeInit()
  new MutationObserver(_maybeInit).observe(mc, { attributes: true, attributeFilter: ['hidden'] })
})()
