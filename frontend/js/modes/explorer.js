/**
 * js/modes/explorer.js — Text intake and parsing.
 *
 * Owns: Text-picker dialog, Language auto-detection, Difficulty estimator,
 * Results heading difficulty badge, Results heading, Results empty state,
 * Parse text, Large-text async parse (job API + SSE), Language capabilities,
 * Nuance-coverage indicator, Script view toolbar, Backend health check,
 * Startup-warning header helper, Deep-link (?annotation=ID&language=CODE).
 */
import { API_BASE } from '../config.js'
import { getAuthHeaders } from '../auth.js'
import { t, ti, currentUiLang, CAPABILITY_LABELS_I18N } from '../i18n.js'
import { openDetail } from '../layout.js'
import { buildLessonPipelinePayload } from '../lesson-pipeline.js'
import { escapeHtml, setStatus } from '../shared.js'
import { extractTextFromFile, ACCEPT_ATTRIBUTE } from '../file-text-extractor.js'
import {
  languageCapabilities,
  currentCaps,
  setCurrentCaps,
  currentDepth,
  currentSourceUrl,
  setCurrentSourceUrl,
  currentFilename,
  setCurrentFilename,
  setCurrentDocumentTitle,
  setCurrentDocumentEyebrow,
} from '../reading-state.js'
import { renderResults, makeTranslateCallback, speakText } from './lesson.js'
import { getTermProgress, submitReview, submitLessonCheck } from './review.js'
import { refreshLoadLessonBtn } from './library.js'

// ── DOM references ────────────────────────────────────────────────────────────

const languageSelect    = document.querySelector('#language')
const chooseTextBtn     = document.querySelector('#choose-text-btn')
const changeTextBtn     = document.querySelector('#change-text-btn')
const chosenTextDisplay = document.querySelector('#chosen-text-display')
const saveLessonBtn     = document.querySelector('#save-lesson-btn')
const results           = document.querySelector('#results')
const resultsEmpty      = document.querySelector('.results-empty')
const detailPane        = document.querySelector('#detail-pane')
const paneBackdrop      = document.querySelector('#pane-backdrop')
const resultsToolbar    = document.querySelector('#results-toolbar')
const langNuanceBar     = document.querySelector('#lang-nuance-bar')
const jobProgressPanel  = document.querySelector('#job-progress')
const jobProgressFill   = document.querySelector('#job-progress-fill')
const jobProgressLabel  = document.querySelector('#job-progress-label')

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

const resultsSection     = document.querySelector('#results-section')
const resultsTitle       = document.querySelector('#results-heading')
const resultsEyebrow     = document.querySelector('#results-source-eyebrow')
const resultsDifficulty  = document.querySelector('#results-difficulty')
const parseDialog        = document.querySelector('#parse-dialog')
const parseDialogClose   = document.querySelector('#parse-dialog-close')
const changeLessonBtn    = document.querySelector('#change-lesson-btn')
const siteHero           = document.querySelector('#site-hero')

const startupBanner    = document.querySelector('#startup-banner')
const startupBannerMsg = document.querySelector('#startup-banner-msg')
const lessonModal      = document.querySelector('#lesson-modal')

// ── Reading/parse state local to the explorer surface ──────────────────────────

const MAX_FILE_BYTES = 1_048_576  // 1 MiB
// Fallback used before GET /parse/limits responds.  Must match Settings.max_job_chars default.
const DEFAULT_MAX_JOB_CHARS = 500_000
let maxJobChars = DEFAULT_MAX_JOB_CHARS

let currentContentType    = 'pasted_text'
let currentFetchedTitle   = null
let currentDocumentDifficulty = null  // estimated CEFR level of loaded document
let languageUserSelected  = false
let currentText           = ''   // committed text from picker

// Re-exported so create.js's save-lesson flow can read the picker's
// committed text/source URL without owning this state itself.
export function committedTextValue() { return currentText }
export function committedSourceUrlValue() { return currentSourceUrl() }

const _DIFF_MIN_CHARS = 40

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

function syncCurrentCaps() {
  setCurrentCaps(languageCapabilities.get(languageSelect.value) ?? null)
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
  const nc = currentCaps()?.nuance_capabilities
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

let scriptView = 'native'

export function updateScriptViewToolbar() {
  if (!resultsToolbar) return
  const supported = Boolean(currentCaps()?.transliteration_scheme)
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

export function applyScriptViewToResults() {
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
    setCurrentFilename(file.name)
    languageUserSelected = false
    setPickerStatus(`Loaded: ${escapeHtml(file.name)} (${(file.size / 1024).toFixed(1)} KB)`)
    scheduleLanguageDetection()
    scheduleDifficultyEstimate()
  }).catch(error => {
    const key = error instanceof Error ? error.message : 'file_read_error'
    const translatable = ['unsupported_file_type', 'encrypted_pdf', 'corrupt_file', 'no_extractable_text', 'file_read_error']
    setPickerStatus(t(translatable.includes(key) ? key : 'file_read_error'), 'error')
    currentContentType = 'pasted_text'
    setCurrentFilename(null)
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
    setCurrentFilename(null)
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
    setCurrentFilename(null)
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
  currentText = normalizeParseInput(text)
  setCurrentSourceUrl(pickerUrlInput?.value.trim() || null)

  if (currentContentType === 'article' && currentSourceUrl()) {
    let eyebrow = null
    try { eyebrow = new URL(currentSourceUrl()).hostname } catch { eyebrow = null }
    setCurrentDocumentEyebrow(eyebrow)
    setCurrentDocumentTitle(currentFetchedTitle || eyebrow)
  } else if (currentContentType === 'uploaded_file' && currentFilename()) {
    setCurrentDocumentTitle(currentFilename().replace(/\.[^.]+$/, ''))
    setCurrentDocumentEyebrow(null)
  } else {
    setCurrentDocumentTitle(null)
    setCurrentDocumentEyebrow(null)
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
  const preview = text.length > 300 ? text.slice(0, 300) + '…' : text
  chosenTextDisplay.textContent = preview
  chosenTextDisplay.hidden = false
  if (chooseTextBtn) chooseTextBtn.hidden = true
  if (changeTextBtn) changeTextBtn.hidden = false
}

languageSelect.addEventListener('change', () => {
  languageUserSelected = true
  scriptView = 'native'
  syncCurrentCaps()
  populateSampleLanguageSelect()
  refreshLoadLessonBtn()
  scheduleDifficultyEstimate()
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

// ── Difficulty estimator ──────────────────────────────────────────────────────

const _DIFF_DEBOUNCE_MS  = 800
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

// ── Results heading difficulty badge ─────────────────────────────────────────

export function _clearResultsDifficultyBadge() {
  if (!resultsDifficulty) return
  resultsDifficulty.hidden = true
  resultsDifficulty.textContent = ''
  delete resultsDifficulty.dataset.cefr
  currentDocumentDifficulty = null
}

function _setResultsDifficultyBadge(cefr, confident) {
  if (!resultsDifficulty) return
  resultsDifficulty.textContent = confident ? cefr : `~${cefr}`
  resultsDifficulty.dataset.cefr = cefr
  resultsDifficulty.title = confident ? cefr : `Estimated: ${cefr} (low confidence)`
  resultsDifficulty.hidden = false
  currentDocumentDifficulty = cefr
}

export async function _fetchResultsDifficulty(text, language) {
  _clearResultsDifficultyBadge()
  if (!text || !language || text.length < _DIFF_MIN_CHARS) return
  try {
    const resp = await fetch(`${API_BASE}/estimate-difficulty`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      body:    JSON.stringify({ text, language }),
    })
    if (!resp.ok) return
    const data = await resp.json()
    if (data.estimated_cefr) _setResultsDifficultyBadge(data.estimated_cefr, data.confident)
  } catch {
    // non-critical — badge stays hidden
  }
}

// ── Results heading ───────────────────────────────────────────────────────────

export function setResultsHeading(title, eyebrow) {
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
    _fetchResultsDifficulty(normalizedText, language)
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

// ── Large-text async parse (job API + SSE) ────────────────────────────────────

async function parseWithJob(text, language) {
  const jobResp = await fetch(`${API_BASE}/parse/jobs`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
    body:    JSON.stringify({
      language,
      text,
      source_url: currentSourceUrl() || null,
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

// ── Startup-warning header helper ─────────────────────────────────────────────

function handleStartupWarningHeader(response) {
  const warning = response.headers.get('X-Startup-Warning')
  if (warning) showBackendBanner(warning)
}

// ── Backend health check ──────────────────────────────────────────────────────

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
    const url = `${API_BASE}/lesson/${encodeURIComponent(_dlAnnotation)}?language=${encodeURIComponent(lang)}&depth=${encodeURIComponent(currentDepth())}`
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
        depth: currentDepth(),
        uiLang,
        onTranslate: makeTranslateCallback(lesson),
        reviewQueue: dueQueue,
        termProgress,
        onSpeak: (text, l) => speakText(text, l ?? ttsTag),
        onStudy: () => lessonModal.open({
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

/**
 * initExplorer() — wires language list + parse limits load and runs the
 * initial backend health check. Call once during app startup.
 */
export function initExplorer() {
  loadParseLimits()
  loadLanguages()
  checkBackendHealth()
  window.__checkBackendHealth = checkBackendHealth
}
