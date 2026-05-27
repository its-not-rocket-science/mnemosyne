import { t, currentUiLang } from '../js/i18n.js'
import { API_BASE } from '../js/config.js'

// ── Type metadata (mirrors mnemosyne-pill.js) ─────────────────────────────────
const TYPE_META = {
  vocabulary:      { icon: '📗', labelKey: 'dp_type_vocabulary',     ref: 'oklch(0.50 0.20 142)' },
  conjugation:     { icon: '🔧', labelKey: 'dp_type_verb',            ref: 'oklch(0.50 0.20 240)' },
  agreement:       { icon: '🧩', labelKey: 'dp_type_agreement',       ref: 'oklch(0.50 0.15  50)' },
  inflection:      { icon: '🧬', labelKey: 'dp_type_inflection',      ref: 'oklch(0.50 0.18 160)' },
  idiom:           { icon: '💬', labelKey: 'dp_type_idiom',            ref: 'oklch(0.50 0.20 300)' },
  grammar:         { icon: '📐', labelKey: 'dp_type_grammar',          ref: 'oklch(0.50 0.15  90)' },
  nuance:          { icon: '🎭', labelKey: 'dp_type_nuance',           ref: 'oklch(0.50 0.20  20)' },
  script:          { icon: '✍️', labelKey: 'dp_type_script',          ref: 'oklch(0.50 0.18 200)' },
  transliteration: { icon: '🔤', labelKey: 'dp_type_transliteration', ref: 'oklch(0.50 0.15 170)' },
  phrase_family:   { icon: '🔗', labelKey: 'dp_type_phrase_family',   ref: 'oklch(0.50 0.20 330)' },
}

// Field labels shown in dedicated UI sections — suppress from the generic field list.
const SUPPRESS_IN_EXPLANATION = new Set([
  'known variants', 'confusable with', 'origin', 'variant note',
  // phrase_family fields rendered in dedicated sections:
  'match type', 'note', 'source', 'why it matters',
])

// User-friendly labels and CSS modifier classes for MatchType values.
const MATCH_TYPE_META = {
  exact:                { labelKey: 'dp_match_canonical',    cls: 'canonical' },
  orthographic_variant: { labelKey: 'dp_match_variant',      cls: 'variant'   },
  modernized_variant:   { labelKey: 'dp_match_modern',       cls: 'variant'   },
  inflectional_variant: { labelKey: 'dp_match_inflectional', cls: 'variant'   },
  misquotation:         { labelKey: 'dp_match_misquote',     cls: 'warning'   },
  blend:                { labelKey: 'dp_match_blend',        cls: 'warning'   },
  allusion:             { labelKey: 'dp_match_allusion',     cls: 'allusion'  },
  confusable_not_same:  { labelKey: 'dp_match_confusable',   cls: 'danger'    },
}

// ── Field label / value translation helpers ───────────────────────────────────

function translateFieldLabel(label) {
  const key = 'fl_' + label.toLowerCase().replace(/ /g, '_')
  const tr = t(key)
  return tr !== key ? tr : label
}

function translateFieldValue(value) {
  const key = 'fv_' + value.toLowerCase().replace(/ /g, '_')
  const tr = t(key)
  if (tr !== key) return tr
  // Handle "word (type)" pattern — translate just the parenthetical type
  const m = value.match(/^(.*?)\s+\(([^)]+)\)$/)
  if (m) {
    const typeKey = 'fv_' + m[2].toLowerCase().replace(/ /g, '_')
    const typeT = t(typeKey)
    if (typeT !== typeKey) return `${m[1]} (${typeT})`
  }
  return value
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

function normalize(text) {
  return String(text ?? '').trim().toLowerCase()
}
function tr(key, fallback) {
  const v = t(key)
  return v === key ? fallback : v
}
function _setFeedback(el, correct, correctText, incorrectText) {
  const text = correct ? correctText : (incorrectText ?? correctText)
  el.innerHTML = `<span aria-hidden="true">${correct ? '✓' : '✗'}</span> ${esc(text)}`
}
function normalizeForLanguage(text, language = 'und') {
  const folded = normalize(text).normalize('NFD').replace(/\p{M}+/gu, '')
  return language === 'de' ? folded.replace(/ß/g, 'ss') : folded
}


function tokenSet(text, language = 'und') {
  return new Set(normalizeForLanguage(text, language).split(/[^\p{L}\p{N}]+/u).filter((w) => w.length >= 3))
}

function compareMeaning(candidate, reference, language = 'und') {
  const mine = tokenSet(candidate, language)
  const target = tokenSet(reference, language)
  if (!mine.size || !target.size) return { overlap: 0, ratio: 0 }
  let overlap = 0
  for (const token of mine) if (target.has(token)) overlap += 1
  return { overlap, ratio: overlap / Math.max(1, target.size) }
}

function shuffled(array) {
  const out = [...array]
  for (let i = out.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[out[i], out[j]] = [out[j], out[i]]
  }
  return out
}

/**
 * Populate `container` with the sentence text, wrapping any occurrence of
 * `phrase` in a <mark class="context-highlight"> element.
 * Uses DOM construction (never innerHTML) so no escaping is needed.
 */
function highlightPhrase(container, sentence, phrase) {
  container.replaceChildren()
  if (!sentence) return

  if (!phrase) {
    container.appendChild(document.createTextNode(sentence))
    return
  }

  const re = new RegExp(
    phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'),
    'gi'
  )
  let lastIndex = 0
  let match
  const fragment = document.createDocumentFragment()

  while ((match = re.exec(sentence)) !== null) {
    if (match.index > lastIndex) {
      fragment.appendChild(document.createTextNode(sentence.slice(lastIndex, match.index)))
    }
    const mark = document.createElement('mark')
    mark.className = 'context-highlight'
    mark.textContent = match[0]
    fragment.appendChild(mark)
    lastIndex = re.lastIndex
  }
  if (lastIndex < sentence.length) {
    fragment.appendChild(document.createTextNode(sentence.slice(lastIndex)))
  }
  container.appendChild(fragment)
}

// ── Component ─────────────────────────────────────────────────────────────────

export class MnemosyneDetailPane extends HTMLElement {
  // Private state
  #config         = null   // { lesson, sentenceText, language, dir, ttsTag, caps, depth, uiLang }
  #lastShowArgs   = null   // stored for updateDepth()
  #activeTab      = 0
  #visibleTabs    = []     // subset of ALL_TABS that are rendered
  #onSpeak        = null
  #onStudy        = null
  #onTranslate    = null   // async (text, sourceLang, targetLang) => {text, attribution} | null
  #previousFocus  = null
  #keydownHandler    = null
  #langChangeHandler = null
  #snap           = 'half'
  #dragStartY     = 0
  #dragBaseY      = 0
  #dragActive     = false
  #practiceSession   = { correct: 0, total: 0 }
  // Translation fetch state (reset on each show())
  #vocabTranslationFetched        = false
  #sentenceTranslationFetched     = false
  #explanationTranslationFetched  = false
  #reviewStatusFetched            = false
  #conceptDialogTrigger           = null
  #matchedVariant = ''

  static ALL_TABS = [
    { id: 'explanation',  labelKey: 'dp_tab_explanation',  alwaysShow: true  },
    { id: 'form',         labelKey: 'dp_tab_form',         alwaysShow: false },
    { id: 'paradigm',     labelKey: 'dp_tab_paradigm',     alwaysShow: false },
    { id: 'equivalents',  labelKey: 'dp_tab_equivalents',  alwaysShow: false },
    { id: 'nuance',       labelKey: 'dp_tab_nuance',       alwaysShow: false },
    { id: 'memory',       labelKey: 'dp_tab_memory',       alwaysShow: false },
    { id: 'origins',      labelKey: 'dp_tab_origins',      alwaysShow: false },
    { id: 'context',      labelKey: 'dp_tab_context',      alwaysShow: true  },
    { id: 'related',      labelKey: 'dp_tab_related',      alwaysShow: false },
    { id: 'practice',     labelKey: 'dp_tab_practice',     alwaysShow: true  },
    { id: 'review',       labelKey: 'dp_tab_review',       alwaysShow: false },
  ]

  constructor() {
    super()
    this.attachShadow({ mode: 'open' })
  }

  // ── Public API ──────────────────────────────────────────────────────────────

  show({ lesson, sentenceText, language, dir, ttsTag, caps, onSpeak, onStudy, onTranslate, depth, uiLang, reviewQueue = [], termProgress = null }) {
    this.#lastShowArgs  = { lesson, sentenceText, language, dir, ttsTag, caps, onSpeak, onStudy, onTranslate, depth, uiLang, reviewQueue, termProgress }
    this.#config        = { lesson, sentenceText, language, dir: dir ?? 'ltr', ttsTag, caps, depth: depth ?? 'deep', uiLang: uiLang ?? 'en', reviewQueue, termProgress }
    this.#onSpeak       = onSpeak ?? null
    this.#onTranslate   = onTranslate ?? null
    this.#vocabTranslationFetched    = false
    this.#sentenceTranslationFetched = false
    this.#reviewStatusFetched        = false
    this.#onStudy       = onStudy ?? null
    this.#activeTab     = 0
    this.#explanationTranslationFetched = false
    this.#practiceSession = { correct: 0, total: 0 }
    this.#previousFocus = document.activeElement

    this.removeAttribute('inert')

    // Delegated handlers on the shadow root — wired once, survive innerHTML replacement.
    if (!this._delegateWired) {
      this._delegateWired = true

      this.shadowRoot.addEventListener('click', (e) => {
        // Tab switch
        const tab = e.target.closest('[role="tab"]')
        if (tab) {
          const tabEls = Array.from(this.shadowRoot.querySelectorAll('[role="tab"]'))
          const i = tabEls.indexOf(tab)
          if (i < 0) return
          this.#activeTab = i
          this._applyTabState()
          const tabId = this.#visibleTabs[i]?.id
          if (tabId === 'explanation') this.#fetchVocabTranslation()
          if (tabId === 'context') this.#fetchSentenceTranslation(this.#config.sentenceText || '')
          if (tabId === 'review') this.#fetchReviewStatus()
          return
        }

        // Close
        if (e.target.closest('.pane__close')) { this.hide(); return }

        // Study drills (footer + practice tab CTA)
        if (e.target.closest('.pane__study-btn')) {
          this.dispatchEvent(new CustomEvent('pane-study', { bubbles: true, composed: true }))
          this.#onStudy?.()
          return
        }

        // Audio
        const speakBtn = e.target.closest('[data-speak]')
        if (speakBtn) {
          if (!this.#onSpeak) return
          const { lesson, language, ttsTag } = this.#config
          const ld = lesson.lesson_data ?? {}
          const matchedVariant = ld.matched_variant || lesson.examples?.[0] || ''
          const canonical      = ld.canonical_form  || lesson.examples?.[0] || ''
          const mode = speakBtn.dataset.speak
          let text = ''
          switch (mode) {
            case 'phrase':    text = matchedVariant || canonical; break
            case 'original':  text = matchedVariant;              break
            case 'modern':    text = canonical || matchedVariant; break
            case 'sentence':  text = this.#config.sentenceText || ''; break
            case 'canonical': text = canonical; break
          }
          if (text) this.#onSpeak(text, ttsTag ?? language)
          return
        }

        // Confusable family links
        const confusableBtn = e.target.closest('.pane__confusable-link')
        if (confusableBtn) {
          const familyId = confusableBtn.dataset.familyId
          if (!familyId) return
          this.dispatchEvent(new CustomEvent('pane-navigate', {
            bubbles: true, composed: true,
            detail: { objectId: familyId, language: this.#config.language },
          }))
          return
        }

        // Share
        if (e.target.closest('.pane__share')) {
          const { lesson, language } = this.#config
          const shareHint = this.shadowRoot.querySelector('.pane__share-hint')
          const url = new URL(location.href)
          url.searchParams.set('annotation', lesson.id)
          url.searchParams.set('language',   language)
          const shareUrl = url.toString()
          if (navigator.share) {
            navigator.share({ url: shareUrl, title: lesson.title || lesson.label || '' }).catch(() => {})
          } else {
            navigator.clipboard.writeText(shareUrl).then(() => {
              if (shareHint) {
                shareHint.textContent = t('dp_link_copied')
                setTimeout(() => { shareHint.textContent = '' }, 2200)
              }
            }).catch(() => {
              if (shareHint) {
                shareHint.textContent = 'Copy: ' + shareUrl
                setTimeout(() => { shareHint.textContent = '' }, 6000)
              }
            })
          }
          return
        }

        // Note — save
        if (e.target.closest('.pane__note-save')) {
          const { lesson } = this.#config
          const noteKey   = `mn-note-${lesson.id}`
          const noteInput = this.shadowRoot.querySelector('.pane__note-input')
          if (!noteInput) return
          const val = noteInput.value.trim()
          if (val) localStorage.setItem(noteKey, val)
          else     localStorage.removeItem(noteKey)
          this.dispatchEvent(new CustomEvent('note-updated', {
            bubbles: true, composed: true,
            detail: { objectId: lesson.id, hasNote: Boolean(val) },
          }))
          const saveBtn = e.target.closest('.pane__note-save')
          const orig = saveBtn.textContent
          saveBtn.textContent = t('dp_note_saved')
          setTimeout(() => { saveBtn.textContent = orig }, 1500)
          return
        }

        // Note — clear
        if (e.target.closest('.pane__note-clear')) {
          const { lesson } = this.#config
          const noteKey   = `mn-note-${lesson.id}`
          const noteInput = this.shadowRoot.querySelector('.pane__note-input')
          if (noteInput) noteInput.value = ''
          localStorage.removeItem(noteKey)
          this.dispatchEvent(new CustomEvent('note-updated', {
            bubbles: true, composed: true,
            detail: { objectId: lesson.id, hasNote: false },
          }))
          return
        }

        // Concept help button
        const helpBtn = e.target.closest('[data-concept-id]')
        if (helpBtn) {
          const conceptId = helpBtn.dataset.conceptId
          if (conceptId) this.#openConceptDialog(conceptId, helpBtn)
          return
        }

        // Concept dialog close (button or backdrop click)
        if (e.target.closest('.pane__concept-dialog-close')) {
          this.#closeConceptDialog()
          return
        }
        if (e.target.classList.contains('pane__concept-dialog')) {
          this.#closeConceptDialog()
          return
        }
      })

      // Review confirmed by main.js — update term-state block and session score persistently
      this.addEventListener('review-submitted', ({ detail }) => {
        const stateEl = this.shadowRoot?.querySelector('.pane__term-state')
        if (stateEl && detail?.reviewBucket) {
          const meta = this.#bucketMeta(detail.reviewBucket)
          const days = detail.nextIntervalDays
          const nextText = days != null
            ? tr('dp_mm_next_interval', `next in ${days}d`)
            : ''
          stateEl.dataset.bucket = detail.reviewBucket
          stateEl.innerHTML = /* html */`
            <span class="pane__term-state-badge">${meta.icon} ${esc(meta.label)}</span>
            ${nextText ? `<span class="pane__term-state-next">${esc(nextText)}</span>` : ''}
          `
        }
        const scoreEl = this.shadowRoot?.querySelector('.pane__session-score')
        if (scoreEl) {
          const { correct, total } = this.#practiceSession
          const base = total > 0 ? tr('dp_session_score', `Session: ${correct}/${total}`) : ''
          const note = `<span aria-hidden="true">✓</span> ${esc(tr('dp_mm_synced', 'Memory Map updated'))}`
          scoreEl.innerHTML = base ? `${esc(base)} · ${note}` : note
        }
      })

      // Tab keyboard navigation — delegated for same reason as click
      this.shadowRoot.addEventListener('keydown', (e) => {
        // Escape closes the concept dialog when it is open
        if (e.key === 'Escape') {
          const dialog = this.shadowRoot.querySelector('#dp-concept-dialog')
          if (dialog && !dialog.hidden) {
            e.stopPropagation()
            this.#closeConceptDialog()
            return
          }
        }

        const tab = e.target.closest('[role="tab"]')
        if (!tab) return
        const tabEls = Array.from(this.shadowRoot.querySelectorAll('[role="tab"]'))
        const i = tabEls.indexOf(tab)
        if (i < 0) return
        let next = null
        if (e.key === 'ArrowRight') next = (i + 1) % tabEls.length
        if (e.key === 'ArrowLeft')  next = (i - 1 + tabEls.length) % tabEls.length
        if (e.key === 'Home')       next = 0
        if (e.key === 'End')        next = tabEls.length - 1
        if (next !== null) {
          e.preventDefault()
          this.#activeTab = next
          this._applyTabState()
          tabEls[next].focus()
        }
      })
    }

    this._render()

    // Deferred to the next frame so the browser registers the pre-animation
    // state (translateY(110%) on mobile) before we apply data-open, allowing
    // the CSS transition to play.  Focus moves after the attribute lands so
    // screen readers announce the newly-visible pane.
    requestAnimationFrame(() => {
      this.setAttribute('data-open', '')
      this.#setSnap('full')
      this.shadowRoot.querySelector('[role="tab"]')?.focus()
    })

    // Re-render when UI language changes while pane is open.
    if (!this.#langChangeHandler) {
      this.#langChangeHandler = () => {
        if (this.hasAttribute('data-open')) {
          this.#config.uiLang = currentUiLang()
          this.#explanationTranslationFetched = false
          this.#sentenceTranslationFetched = false
          this._render()
        }
      }
      document.addEventListener('mnemosyne:language-changed', this.#langChangeHandler)
    }

    // Close on Escape; trap Tab within the pane while open.
    if (this.#keydownHandler) {
      document.removeEventListener('keydown', this.#keydownHandler)
    }
    this.#keydownHandler = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        this.hide()
        return
      }
      if (e.key === 'Tab') this.#trapTab(e)
    }
    document.addEventListener('keydown', this.#keydownHandler)
  }

  hide() {
    this.removeAttribute('data-open')
    this.removeAttribute('data-snap')
    this.removeAttribute('data-dragging')
    this.style.transform = ''
    this.setAttribute('inert', '')

    if (this.#keydownHandler) {
      document.removeEventListener('keydown', this.#keydownHandler)
      this.#keydownHandler = null
    }

    this.dispatchEvent(new CustomEvent('pane-close', { bubbles: true, composed: true }))
    this.#previousFocus?.focus?.()
  }

  /** Re-render in place when the user changes depth level while the pane is open. */
  updateDepth(depth) {
    if (!this.#lastShowArgs || !this.hasAttribute('data-open')) return
    this.#config.depth = depth
    this.#lastShowArgs.depth = depth
    const prevTab = this.#activeTab
    this._render()
    if (prevTab < this.#visibleTabs.length) {
      this.#activeTab = prevTab
      this._applyTabState()
    }
  }

  // ── Rendering ───────────────────────────────────────────────────────────────

  _render() {
    const { lesson, sentenceText, language, dir, depth } = this.#config
    const ld   = lesson.lesson_data ?? {}
    const type = lesson.type ?? 'vocabulary'
    const meta = TYPE_META[type] ?? TYPE_META.vocabulary
    const metaLabel = t(meta.labelKey) || meta.labelKey

    const depthIdx = { subtle: 0, learning: 1, deep: 2 }[depth ?? 'deep'] ?? 2

    // Which optional tabs have data?
    const hasOrigins = Boolean(ld.origin || ld.etymology || ld.source_text)
    const hasRelated = Boolean(
      (Array.isArray(ld.variants)         && ld.variants.length > 1) ||
      (Array.isArray(ld.confusables)      && ld.confusables.length > 0) ||
      (Array.isArray(ld.confusable_forms) && ld.confusable_forms.length > 0)
    )

    const hasForm       = (lesson.morphology_axes?.length > 0 || lesson.contrasts?.length > 0)
    const hasParadigm   = lesson.paradigms?.length > 0
    const hasEquivs     = lesson.equivalents?.length > 0
    const hasNuance     = Array.isArray(lesson.nuance_sets) && lesson.nuance_sets.length > 0
    const hasMemory     = lesson.encountered_vocabulary?.length > 0

    // Depth controls which tabs are exposed.
    // subtle=0: Explanation only. learning=1: + Origins + Context. deep=2: all.
    this.#visibleTabs = MnemosyneDetailPane.ALL_TABS.filter(tab => {
      if (tab.id === 'explanation')  return true
      if (tab.id === 'form')         return hasForm
      if (tab.id === 'paradigm')     return hasParadigm
      if (tab.id === 'equivalents')  return hasEquivs
      if (tab.id === 'nuance')       return hasNuance
      if (tab.id === 'memory')       return hasMemory
      if (tab.id === 'origins')      return depthIdx >= 1 && hasOrigins
      if (tab.id === 'context')      return depthIdx >= 1
      if (tab.id === 'related')      return depthIdx >= 2 && hasRelated
      if (tab.id === 'practice')     return depthIdx >= 1
      if (tab.id === 'review')       return depthIdx >= 1
      return false
    })

    const matchedVariant = ld.matched_variant || lesson.examples?.[0] || ''
    this.#matchedVariant = matchedVariant
    const canonical      = ld.canonical_form  || lesson.examples?.[0] || ''
    const matchType      = ld.match_type || ''
    // Use match_type field (authoritative) rather than surface string comparison,
    // which fails for confusable_not_same where matched surface may equal canonical.
    const isNonCanonical = Boolean(matchType && matchType !== 'exact')

    const titleText = canonical || lesson.examples?.[0] || lesson.title || ''

    // ── Assemble shadow DOM ──────────────────────────────────────────────────
    this.shadowRoot.innerHTML = /* html */`
      <style>${this._styles(meta)}</style>
      <aside class="pane" role="complementary" aria-labelledby="dp-heading">

        <div class="pane__drag-handle-area" aria-hidden="true">
          <div class="pane__drag-handle"></div>
        </div>

        <header class="pane__header">
          <div class="pane__badge" aria-hidden="true">${esc(meta.icon)} ${esc(metaLabel)}</div>
          <h2 class="pane__title" id="dp-heading">${esc(titleText)}</h2>
          <button class="pane__share" type="button" aria-label="${esc(t('dp_copy_link_aria'))}">&#x1F517;</button>
          <span class="pane__share-hint" aria-live="polite" aria-atomic="true"></span>
          <button class="pane__close" type="button" aria-label="${esc(t('dp_close_aria'))}">&#x2715;</button>
        </header>

        <div class="pane__tabs" role="tablist" aria-label="${esc(t('dp_tabs_aria'))}">
          ${this.#visibleTabs.map((tab, i) => /* html */`
            <button
              class="pane__tab${i === 0 ? ' pane__tab--active' : ''}"
              role="tab"
              id="dp-tab-${tab.id}"
              aria-selected="${i === 0}"
              aria-controls="dp-panel-${tab.id}"
              tabindex="${i === 0 ? 0 : -1}"
              type="button"
            >${esc(t(tab.labelKey))}</button>
          `).join('')}
        </div>

        <div class="pane__body">
          ${this._htmlExplanationPanel(lesson, ld, matchedVariant, depthIdx)}
          ${hasForm      ? this._htmlFormPanel(lesson, dir)       : ''}
          ${hasParadigm  ? this._htmlParadigmPanel(lesson, dir)   : ''}
          ${hasEquivs    ? this._htmlEquivalentsPanel(lesson)     : ''}
          ${hasNuance    ? this._htmlNuancePanel(lesson, dir)     : ''}
          ${hasMemory    ? this._htmlMemoryPanel(lesson)          : ''}
          ${depthIdx >= 1 && hasOrigins  ? this._htmlOriginsPanel(ld, isNonCanonical, Boolean(ld.source_text), matchType) : ''}
          ${depthIdx >= 1               ? this._htmlContextPanel(sentenceText, language, dir, matchedVariant) : ''}
          ${depthIdx >= 2 && hasRelated  ? this._htmlRelatedPanel(ld, canonical, isNonCanonical) : ''}
          ${this._htmlPracticePanel()}
          ${this._htmlReviewPanel()}
        </div>

        <footer class="pane__footer">
          <button class="pane__study-btn" type="button">${esc(t('dp_study_drills'))}</button>
        </footer>

        <slot name="now-playing"></slot>

        ${this._htmlConceptDialog()}
      </aside>
    `

    // In Context: highlighted sentence (requires DOM node manipulation for <mark> elements)
    const contextEl = this.shadowRoot.querySelector('#dp-panel-context .pane__context-sentence')
    if (contextEl) highlightPhrase(contextEl, sentenceText || '', matchedVariant)

    // Set initial panel visibility
    this._applyTabState()

    // Wire all interactive events
    this._wireEvents(matchedVariant, canonical, sentenceText || '', isNonCanonical)

    // Kick off translations for whichever tab is currently active.
    // All three flags are reset so re-renders (depth change, language change)
    // can refetch cleanly without relying on the tab-click path.
    this.#vocabTranslationFetched       = false
    this.#sentenceTranslationFetched    = false
    this.#explanationTranslationFetched = false
    this.#reviewStatusFetched           = false
    this.#fetchVocabTranslation()
    this.#fetchExplanationTranslation()
    if (this.#visibleTabs[this.#activeTab]?.id === 'context') {
      this.#fetchSentenceTranslation(sentenceText || '')
    }
  }

  // ── HTML fragment builders ──────────────────────────────────────────────────

  _htmlExplanationPanel(lesson, ld, matchedVariant, depthIdx = 2) {
    const allFields    = (lesson.fields ?? [])
      .filter(f => !SUPPRESS_IN_EXPLANATION.has(f.label.toLowerCase()))
    const displayFields = depthIdx >= 1 ? allFields : []

    const fieldsHtml = displayFields.map(f => {
      const cid = f.value_concept_id || f.concept_id || null
      const helpBtn = cid ? /* html */`<button class="pane__concept-help" type="button" data-concept-id="${esc(cid)}" aria-label="${esc(t('dp_explain_concept'))}" title="${esc(t('dp_explain_concept'))}">?</button>` : ''
      return /* html */`
        <div class="pane__field">
          <dt class="pane__field-label">${esc(translateFieldLabel(f.label))}</dt>
          <dd class="pane__field-value">${esc(translateFieldValue(f.value))}${helpBtn}</dd>
        </div>
      `
    }).join('')

    const hasAudio        = Boolean(matchedVariant)
    const matchType       = ld.match_type || ''
    const matchTypeMeta   = matchType ? (MATCH_TYPE_META[matchType] ?? { labelKey: null, cls: 'variant' }) : null
    const showMatchBadge  = Boolean(matchTypeMeta)
    const matchTypeNote   = ld.match_type_note || ''
    const hasWhyItMatters = Boolean(ld.why_it_matters) && depthIdx >= 2
    const isConfusable    = matchType === 'confusable_not_same'
    const confusableWarning = matchTypeNote || t('dp_confusable_warning')

    return /* html */`
      <section
        id="dp-panel-explanation"
        role="tabpanel"
        aria-labelledby="dp-tab-explanation"
        class="pane__panel"
      >
        ${isConfusable ? /* html */`
          <div class="pane__confusable-warning" role="note">
            <span aria-hidden="true">&#x26A0;&#xFE0F;</span>
            <span class="pane__confusable-warning-text">${esc(confusableWarning)}</span>
          </div>
        ` : ''}
        ${showMatchBadge ? /* html */`
          <div class="pane__match-row">
            <span class="pane__match-badge pane__match-badge--${esc(matchTypeMeta.cls)}">
              ${esc(matchTypeMeta.labelKey ? t(matchTypeMeta.labelKey) : matchType)}
            </span>
            ${matchTypeNote ? `<p class="pane__match-note">${esc(matchTypeNote)}</p>` : ''}
          </div>
        ` : ''}
        <p class="pane__explanation">${esc(lesson.explanation || '')}</p>
        <div class="pane__translation-row" hidden>
          <p class="pane__translation-text"></p>
          <small class="pane__translation-attribution"></small>
        </div>
        ${hasWhyItMatters ? /* html */`
          <blockquote class="pane__why-it-matters">
            <p class="pane__why-it-matters-text">${esc(ld.why_it_matters)}</p>
          </blockquote>
        ` : ''}
        ${displayFields.length ? `<dl class="pane__fields">${fieldsHtml}</dl>` : ''}
        ${hasAudio ? /* html */`
          <div class="pane__audio-row">
            <button class="pane__audio-btn" type="button" data-speak="phrase">
              <span aria-hidden="true">&#x1F50A;</span> ${esc(t('dp_hear_phrase'))}
            </button>
          </div>
        ` : ''}
        <div class="pane__note-section">
          <p class="pane__note-label">${esc(t('dp_notes'))}</p>
          <textarea class="pane__note-input"
                    placeholder="${esc(t('dp_note_placeholder'))}"
                    aria-label="${esc(t('dp_note_placeholder'))}"
                    rows="3"
                    spellcheck="false" autocorrect="off" autocapitalize="off"></textarea>
          <div class="pane__note-actions">
            <button class="pane__note-save" type="button">${esc(t('dp_note_save'))}</button>
            <button class="pane__note-clear" type="button">${esc(t('dp_note_clear'))}</button>
          </div>
        </div>
      </section>
    `
  }

  // ── Form tab ──────────────────────────────────────────────────────────────────
  // Renders morphology_axes (each as a labelled row) and contrasts ("don't confuse with").

  _htmlFormPanel(lesson, dir) {
    const axes      = Array.isArray(lesson.morphology_axes) ? lesson.morphology_axes : []
    const contrasts = Array.isArray(lesson.contrasts)       ? lesson.contrasts       : []
    const language  = this.#config?.language || ''
    const langAttr  = language ? `lang="${esc(language)}"` : ''
    const dirAttr   = dir && dir !== 'ltr' ? `dir="${esc(dir)}"` : ''

    const axesHtml = axes.length ? /* html */`
      <section class="pane__subsection" aria-labelledby="dp-form-axes-h">
        <h3 class="pane__section-heading" id="dp-form-axes-h">${esc(tr('dp_form_axes_heading', 'Morphology'))}</h3>
        <dl class="pane__axes-list">
          ${axes.map(ax => {
            const cid = ax.value_concept_id || ax.axis_concept_id || null
            const helpBtn = cid ? /* html */`<button class="pane__concept-help" type="button" data-concept-id="${esc(cid)}" aria-label="${esc(t('dp_explain_concept'))}" title="${esc(t('dp_explain_concept'))}">?</button>` : ''
            return /* html */`
              <div class="pane__axis-row">
                <dt class="pane__axis-label">${esc(ax.axis)}</dt>
                <dd class="pane__axis-value">
                  <span ${langAttr} ${dirAttr}>${esc(ax.label || ax.value)}</span>
                  ${ax.gloss ? `<span class="pane__axis-gloss">${esc(ax.gloss)}</span>` : ''}
                  ${helpBtn}
                </dd>
              </div>
            `
          }).join('')}
        </dl>
      </section>
    ` : ''

    const contrastsHtml = contrasts.length ? /* html */`
      <section class="pane__subsection" aria-labelledby="dp-form-contrasts-h">
        <h3 class="pane__section-heading" id="dp-form-contrasts-h">${esc(tr('dp_contrasts_heading', "Don't confuse with"))}</h3>
        ${contrasts.map((c, ci) => /* html */`
          <article class="pane__contrast-card" aria-labelledby="dp-contrast-${ci}-label">
            <p class="pane__contrast-forms" id="dp-contrast-${ci}-label">
              <span class="pane__contrast-form" ${langAttr} ${dirAttr}>${esc(c.form_a)}</span>
              <span class="pane__contrast-sep" aria-hidden="true"> vs </span>
              <span class="pane__contrast-form" ${langAttr} ${dirAttr}>${esc(c.form_b)}</span>
            </p>
            <p class="pane__contrast-note">${esc(c.note)}</p>
            ${c.example_a ? `<p class="pane__contrast-example" ${langAttr} ${dirAttr}>${esc(c.example_a)}</p>` : ''}
            ${c.example_b ? `<p class="pane__contrast-example" ${langAttr} ${dirAttr}>${esc(c.example_b)}</p>` : ''}
          </article>
        `).join('')}
      </section>
    ` : ''

    return /* html */`
      <section
        id="dp-panel-form"
        role="tabpanel"
        aria-labelledby="dp-tab-form"
        class="pane__panel"
        hidden
      >
        ${axesHtml}
        ${contrastsHtml}
      </section>
    `
  }

  // ── Paradigm tab ──────────────────────────────────────────────────────────────
  // Renders paradigm tables; current form is visually highlighted.

  _htmlParadigmPanel(lesson, dir) {
    const paradigms = Array.isArray(lesson.paradigms) ? lesson.paradigms : []
    const language  = this.#config?.language || ''
    const langAttr  = language ? `lang="${esc(language)}"` : ''
    const dirAttr   = dir && dir !== 'ltr' ? `dir="${esc(dir)}"` : ''

    const tablesHtml = paradigms.map((p, pi) => {
      const cells   = Array.isArray(p.cells) ? p.cells : []
      const title   = p.title ? /* html */`<h3 class="pane__section-heading">${esc(p.title)}</h3>` : ''
      const tableHtml = this.#paradigmTableHtml(p, cells, langAttr, dirAttr, pi)
      return `${title}${tableHtml}`
    }).join('')

    return /* html */`
      <section
        id="dp-panel-paradigm"
        role="tabpanel"
        aria-labelledby="dp-tab-paradigm"
        class="pane__panel"
        hidden
      >
        ${tablesHtml || `<p class="pane__muted">${esc(tr('dp_paradigm_empty', 'No paradigm data available.'))}</p>`}
      </section>
    `
  }

  #paradigmTableHtml(paradigm, cells, langAttr, dirAttr, idx) {
    if (!cells.length) return ''
    const rowAxis = paradigm.row_axis
    const colAxis = paradigm.col_axis

    if (!rowAxis || !colAxis) {
      // Flat grid — no row/col structure available.
      const items = cells.map(cell => /* html */`
        <div class="pane__paradigm-item${cell.is_highlighted ? ' pane__paradigm-item--current' : ''}">
          <span class="pane__paradigm-form" ${langAttr} ${dirAttr}>${esc(cell.form)}</span>
          ${cell.is_highlighted ? `<span class="pane__paradigm-current-label" aria-label="${esc(tr('dp_paradigm_current_form', 'current form'))}" aria-hidden="true">&#x25CF;</span>` : ''}
          ${cell.gloss ? `<span class="pane__paradigm-gloss">${esc(cell.gloss)}</span>` : ''}
        </div>
      `).join('')
      return `<div class="pane__paradigm-grid">${items}</div>`
    }

    // Build a 2D table.
    const rowVals = []
    const colVals = []
    for (const cell of cells) {
      const rv = cell.axes?.[rowAxis] || ''
      const cv = cell.axes?.[colAxis] || ''
      if (rv && !rowVals.includes(rv)) rowVals.push(rv)
      if (cv && !colVals.includes(cv)) colVals.push(cv)
    }

    const cellLookup = new Map()
    for (const cell of cells) {
      const rv = cell.axes?.[rowAxis] || ''
      const cv = cell.axes?.[colAxis] || ''
      cellLookup.set(`${rv}|${cv}`, cell)
    }

    const colHeads = colVals.map(cv => `<th scope="col" class="pane__paradigm-colhead">${esc(cv)}</th>`).join('')
    const rows = rowVals.map(rv => {
      const tds = colVals.map(cv => {
        const cell = cellLookup.get(`${rv}|${cv}`)
        if (!cell) return `<td class="pane__paradigm-cell pane__paradigm-cell--empty" aria-label="${esc(tr('dp_paradigm_empty_cell', 'not applicable'))}">—</td>`
        const highlightClass = cell.is_highlighted ? ' pane__paradigm-cell--current' : ''
        const srLabel = cell.is_highlighted ? ` <span class="pane__sr-only">(${esc(tr('dp_paradigm_current_form', 'current form'))})</span>` : ''
        const glossHtml = cell.gloss ? `<span class="pane__paradigm-gloss">${esc(cell.gloss)}</span>` : ''
        return /* html */`
          <td class="pane__paradigm-cell${highlightClass}">
            <span class="pane__paradigm-form" ${langAttr} ${dirAttr}>${esc(cell.form)}</span>${srLabel}
            ${glossHtml}
          </td>
        `
      }).join('')
      return `<tr><th scope="row" class="pane__paradigm-rowhead">${esc(rv)}</th>${tds}</tr>`
    }).join('')

    const tableLabel = paradigm.title || tr('dp_paradigm_table_label', 'Paradigm table')
    return /* html */`
      <div class="pane__paradigm-table-wrap" role="region" aria-label="${esc(tableLabel)}">
        <table class="pane__paradigm-table">
          <thead><tr><th scope="col"></th>${colHeads}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    `
  }

  // ── Equivalents tab ──────────────────────────────────────────────────────────
  // Renders equivalent constructions (alternative ways to express the same meaning).

  _htmlEquivalentsPanel(lesson) {
    const equivalents = Array.isArray(lesson.equivalents) ? lesson.equivalents : []

    const cards = equivalents.map((eq, ei) => {
      const noteHtml     = eq.note     ? `<p class="pane__equiv-note">${esc(eq.note)}</p>` : ''
      const registerHtml = eq.register ? /* html */`
        <span class="pane__equiv-register pane__equiv-register--${esc(eq.register)}">${esc(eq.register)}</span>
      ` : ''
      const langCode    = eq.language_code || this.#config?.language || ''
      const langAttr    = langCode ? `lang="${esc(langCode)}"` : ''
      return /* html */`
        <article class="pane__equiv-card" aria-labelledby="dp-equiv-${ei}-construction">
          <p class="pane__equiv-construction" id="dp-equiv-${ei}-construction" ${langAttr}>${esc(eq.construction)}</p>
          ${registerHtml}
          ${noteHtml}
        </article>
      `
    }).join('')

    return /* html */`
      <section
        id="dp-panel-equivalents"
        role="tabpanel"
        aria-labelledby="dp-tab-equivalents"
        class="pane__panel"
        hidden
      >
        <section class="pane__subsection" aria-labelledby="dp-equiv-h">
          <h3 class="pane__section-heading" id="dp-equiv-h">${esc(tr('dp_equivalents_heading', 'Equivalent constructions'))}</h3>
          <p class="pane__muted">${esc(tr('dp_equivalents_desc', 'Alternative ways to express the same meaning or function.'))}</p>
          ${cards}
        </section>
      </section>
    `
  }

  // ── Nuance tab ───────────────────────────────────────────────────────────────
  // Renders curated minimal-pair clusters for meaning discrimination.
  // Exploratory — not scored as right/wrong until the learner chooses,
  // then the explanation reveals.

  _htmlNuancePanel(lesson, dir) {
    const sets     = Array.isArray(lesson.nuance_sets) ? lesson.nuance_sets : []
    const language = this.#config?.language || ''
    const langAttr = language ? `lang="${esc(language)}"` : ''
    const dirAttr  = dir && dir !== 'ltr' ? `dir="${esc(dir)}"` : ''

    const DIMENSION_LABELS = {
      temporal:              'temporal interpretation',
      aspect:                'aspect',
      ontological:           'identity vs condition',
      certainty:             'certainty / mood',
      purpose_cause:         'purpose vs cause',
      motion_vs_location:    'motion vs location',
      formality:             'formality',
      information_structure: 'information structure',
      register:              'register',
      implication:           'implication',
    }

    const setsHtml = sets.map((ns, si) => {
      const dimLabel = DIMENSION_LABELS[ns.dimension] || ns.dimension.replace(/_/g, ' ')
      const pairsHtml = (ns.pairs || []).map((pair, pi) => /* html */`
        <article
          class="pane__nuance-pair"
          data-set-index="${si}"
          data-pair-index="${pi}"
          data-answer="${esc(pair.answer)}"
          aria-labelledby="dp-np-${si}-${pi}-q"
        >
          <p class="pane__nuance-question" id="dp-np-${si}-${pi}-q">${esc(pair.question)}</p>
          <div class="pane__nuance-choices" role="group" aria-labelledby="dp-np-${si}-${pi}-q">
            <button
              class="pane__nuance-choice"
              type="button"
              data-choice="a"
              aria-describedby="dp-np-${si}-${pi}-a"
            >
              <span class="pane__nuance-choice-label" aria-hidden="true">A</span>
              <span class="pane__nuance-sentence" ${langAttr} ${dirAttr} id="dp-np-${si}-${pi}-a">${esc(pair.sentence_a)}</span>
              ${pair.label_a ? `<span class="pane__nuance-hint" aria-hidden="true">${esc(pair.label_a)}</span>` : ''}
            </button>
            <button
              class="pane__nuance-choice"
              type="button"
              data-choice="b"
              aria-describedby="dp-np-${si}-${pi}-b"
            >
              <span class="pane__nuance-choice-label" aria-hidden="true">B</span>
              <span class="pane__nuance-sentence" ${langAttr} ${dirAttr} id="dp-np-${si}-${pi}-b">${esc(pair.sentence_b)}</span>
              ${pair.label_b ? `<span class="pane__nuance-hint" aria-hidden="true">${esc(pair.label_b)}</span>` : ''}
            </button>
          </div>
          <div class="pane__nuance-reveal" hidden>
            <p class="pane__nuance-explanation">${esc(pair.explanation)}</p>
          </div>
          <p class="pane__nuance-feedback" aria-live="polite" aria-atomic="true"></p>
        </article>
      `).join('')

      return /* html */`
        <section class="pane__nuance-set pane__subsection" aria-labelledby="dp-ns-${si}-h">
          <h3 class="pane__section-heading" id="dp-ns-${si}-h">${esc(ns.title)}</h3>
          <div class="pane__nuance-meta">
            <span class="pane__nuance-dim-badge">${esc(dimLabel)}</span>
            ${ns.cefr_level ? `<span class="pane__nuance-cefr">${esc(ns.cefr_level)}</span>` : ''}
          </div>
          <p class="pane__muted">${esc(ns.description)}</p>
          ${pairsHtml}
        </section>
      `
    }).join('')

    return /* html */`
      <section
        id="dp-panel-nuance"
        role="tabpanel"
        aria-labelledby="dp-tab-nuance"
        class="pane__panel"
        hidden
      >
        <p class="pane__muted pane__nuance-intro">${esc(tr('dp_nuance_intro', 'Observe what changes when a native speaker chooses one form instead of another. Select the sentence that fits each description, then read the explanation.'))}</p>
        ${setsHtml}
      </section>
    `
  }

  // ── Memory tab ───────────────────────────────────────────────────────────────
  // Renders encountered_vocabulary — context vocabulary with gloss summaries.

  _htmlMemoryPanel(lesson) {
    const vocab    = Array.isArray(lesson.encountered_vocabulary) ? lesson.encountered_vocabulary : []
    const language = this.#config?.language || ''
    const dir      = this.#config?.dir || 'ltr'
    const langAttr = language ? `lang="${esc(language)}"` : ''
    const dirAttr  = dir !== 'ltr' ? `dir="${esc(dir)}"` : ''

    const cards = vocab.map(v => {
      const formAndLemma = (v.lemma && v.lemma !== v.form)
        ? `${esc(v.form)} <span class="pane__vocab-lemma">(${esc(v.lemma)})</span>`
        : esc(v.form)
      const freqBadge = v.is_high_frequency ? /* html */`
        <span class="pane__vocab-freq" title="${esc(tr('dp_vocab_high_freq_title', 'High-frequency word'))}" aria-label="${esc(tr('dp_vocab_high_freq_aria', 'high frequency'))}">&#x2605;</span>
      ` : ''
      const posHtml  = v.pos  ? `<span class="pane__vocab-pos">${esc(v.pos)}</span>` : ''
      const glossHtml = v.gloss ? `<p class="pane__vocab-gloss">${esc(v.gloss)}</p>` : ''
      return /* html */`
        <article class="pane__vocab-card">
          <div class="pane__vocab-head">
            <span class="pane__vocab-form" ${langAttr} ${dirAttr}>${formAndLemma}${freqBadge}</span>
            ${posHtml}
          </div>
          ${glossHtml}
        </article>
      `
    }).join('')

    return /* html */`
      <section
        id="dp-panel-memory"
        role="tabpanel"
        aria-labelledby="dp-tab-memory"
        class="pane__panel"
        hidden
      >
        <section class="pane__subsection" aria-labelledby="dp-memory-h">
          <h3 class="pane__section-heading" id="dp-memory-h">${esc(tr('dp_memory_heading', 'Context vocabulary'))}</h3>
          <p class="pane__muted">${esc(tr('dp_memory_desc', 'Vocabulary encountered in the context of this lesson.'))}</p>
          ${cards}
        </section>
      </section>
    `
  }

  _htmlOriginsPanel(ld, isNonCanonical, hasSourceText, matchType = '') {
    const isConfusable = matchType === 'confusable_not_same'
    const originText   = ld.origin || ''
    const sourceText   = ld.source_text || ''
    // etymology is a structured object {origin_summary, roots?, cognates?, semantic_shift?}
    const etym = (ld.etymology && typeof ld.etymology === 'object') ? ld.etymology : null
    return /* html */`
      <section
        id="dp-panel-origins"
        role="tabpanel"
        aria-labelledby="dp-tab-origins"
        class="pane__panel"
        hidden
      >
        ${originText ? /* html */`
          <p class="pane__origin-text">${esc(originText)}</p>
        ` : ''}
        ${etym ? /* html */`
          <div class="pane__etymology${originText ? ' pane__etymology--ruled' : ''}">
            <h3 class="pane__section-heading">${esc(t('dp_etymology_heading'))}</h3>
            <p class="pane__etymology-summary">${esc(etym.origin_summary || '')}</p>
            ${(etym.roots?.length || etym.cognates?.length || etym.semantic_shift) ? /* html */`
              <dl class="pane__etymology-meta">
                ${etym.roots?.length ? /* html */`
                  <dt class="pane__etymology-term">${esc(t('dp_etymology_roots'))}</dt>
                  <dd class="pane__etymology-def">${etym.roots.map(r => esc(r)).join('; ')}</dd>
                ` : ''}
                ${etym.cognates?.length ? /* html */`
                  <dt class="pane__etymology-term">${esc(t('dp_etymology_cognates'))}</dt>
                  <dd class="pane__etymology-def">${etym.cognates.map(c => esc(c)).join(', ')}</dd>
                ` : ''}
                ${etym.semantic_shift ? /* html */`
                  <dt class="pane__etymology-term">${esc(t('dp_etymology_shift'))}</dt>
                  <dd class="pane__etymology-def">${esc(etym.semantic_shift)}</dd>
                ` : ''}
              </dl>
            ` : ''}
          </div>
        ` : ''}
        ${hasSourceText ? /* html */`
          <cite class="pane__source-citation">${esc(sourceText)}</cite>
        ` : ''}
        <div class="pane__audio-row">
          ${isNonCanonical ? /* html */`
            <button class="pane__audio-btn" type="button" data-speak="original">
              <span aria-hidden="true">&#x1F50A;</span>
              ${isConfusable ? esc(t('dp_hear_this_phrase')) : esc(t('dp_hear_original'))}
            </button>
            <button class="pane__audio-btn" type="button" data-speak="canonical">
              <span aria-hidden="true">&#x1F50A;</span> ${esc(t('dp_hear_canonical'))}
            </button>
          ` : /* html */`
            <button class="pane__audio-btn" type="button" data-speak="phrase">
              <span aria-hidden="true">&#x1F50A;</span> ${esc(t('dp_hear_phrase'))}
            </button>
          `}
        </div>
      </section>
    `
  }

  _htmlContextPanel(sentenceText, language, dir, matchedVariant) {
    // Sentence text is embedded as plain text here; highlightPhrase() replaces
    // it with <mark>-wrapped content after innerHTML is set.
    return /* html */`
      <section
        id="dp-panel-context"
        role="tabpanel"
        aria-labelledby="dp-tab-context"
        class="pane__panel"
        hidden
      >
        <p class="pane__context-sentence"
          ${language ? `lang="${esc(language)}"` : ''}
          ${dir && dir !== 'ltr' ? `dir="${esc(dir)}"` : ''}
        >${esc(sentenceText || '')}</p>
        <div class="pane__sentence-translation-row" hidden>
          <p class="pane__sentence-translation-text"></p>
          <small class="pane__sentence-translation-attribution"></small>
        </div>
        <div class="pane__audio-row">
          <button class="pane__audio-btn" type="button" data-speak="sentence">
            <span aria-hidden="true">&#x1F50A;</span> ${esc(t('dp_hear_sentence'))}
          </button>
        </div>
      </section>
    `
  }

  _htmlRelatedPanel(ld, canonical, isNonCanonical) {
    // variants may be list[dict{surface,match_type,note}] or legacy list[str]
    const rawVariants      = Array.isArray(ld.variants)         ? ld.variants         : []
    const confusableForms    = Array.isArray(ld.confusable_forms)    ? ld.confusable_forms    : []
    // Prefer rich confusable_families; fall back to raw IDs shaped as minimal refs.
    const rawConfusables     = Array.isArray(ld.confusables)         ? ld.confusables         : []
    const confusableFamilies = Array.isArray(ld.confusable_families) ? ld.confusable_families
      : rawConfusables.map(id => ({ family_id: id }))

    const variantItems = rawVariants.map(v => {
      const surface  = typeof v === 'string' ? v : (v.surface ?? '')
      const note     = typeof v === 'object' ? (v.note ?? '') : ''
      const mt       = typeof v === 'string' ? '' : (v.match_type ?? '')
      const mtMeta   = mt ? (MATCH_TYPE_META[mt] ?? { label: mt, cls: 'variant' }) : null
      const isCanon  = canonical && surface.toLowerCase() === canonical.toLowerCase()
      return /* html */`
        <li class="pane__variant-item${isCanon ? ' pane__variant-item--canonical' : ''}">
          <span class="pane__variant-surface-row">
            <span class="pane__variant-text">${esc(surface)}</span>
            ${isCanon ? '<span class="pane__canonical-star" aria-label="canonical form">&#x2605;</span>' : ''}
            ${mtMeta && !isCanon ? /* html */`
              <span class="pane__match-badge pane__match-badge--${esc(mtMeta.cls)} pane__match-badge--sm">
                ${esc(mtMeta.labelKey ? t(mtMeta.labelKey) : mtMeta.cls)}
              </span>
            ` : ''}
          </span>
          ${note ? `<p class="pane__variant-note">${esc(note)}</p>` : ''}
        </li>
      `
    }).join('')

    const confusableFormItems = confusableForms.map(cf => /* html */`
      <li class="pane__confusable-form-item">
        <span class="pane__match-badge pane__match-badge--danger pane__match-badge--sm">
          ${esc(t(MATCH_TYPE_META.confusable_not_same.labelKey))}
        </span>
        <span class="pane__confusable-form-surface">${esc(cf.surface ?? '')}</span>
        ${cf.note ? `<p class="pane__confusable-form-note">${esc(cf.note)}</p>` : ''}
      </li>
    `).join('')

    const confusableItems = confusableFamilies.map(cf => {
      const familyId = String(cf.family_id ?? '')
      const display  = cf.canonical_form || familyId.replace(/_/g, '\u00a0')
      const meaning  = cf.meaning || ''
      return /* html */`
        <li class="pane__confusable-item">
          <button class="pane__confusable-link" type="button" data-family-id="${esc(familyId)}">
            <span class="pane__confusable-canonical">${esc(display)}</span>
            ${meaning ? `<span class="pane__confusable-meaning">${esc(meaning)}</span>` : ''}
          </button>
        </li>
      `
    }).join('')

    const hasAnyConfusables = confusableFamilies.length > 0 || confusableForms.length > 0

    return /* html */`
      <section
        id="dp-panel-related"
        role="tabpanel"
        aria-labelledby="dp-tab-related"
        class="pane__panel"
        hidden
      >
        ${rawVariants.length ? /* html */`
          <section class="pane__subsection" aria-labelledby="dp-variants-h">
            <h3 class="pane__section-heading" id="dp-variants-h">${esc(t('dp_variant_forms'))}</h3>
            <ul class="pane__variant-list">${variantItems}</ul>
          </section>
        ` : ''}
        ${hasAnyConfusables ? /* html */`
          <section class="pane__subsection" aria-labelledby="dp-confusables-h">
            <h3 class="pane__section-heading" id="dp-confusables-h">${esc(t('dp_confusable_with'))}</h3>
            <ul class="pane__confusable-list">
              ${confusableFormItems}
              ${confusableItems}
            </ul>
          </section>
        ` : ''}
        ${isNonCanonical && ld.match_type !== 'confusable_not_same' ? /* html */`
          <div class="pane__audio-row">
            <button class="pane__audio-btn" type="button" data-speak="canonical">
              <span aria-hidden="true">&#x1F50A;</span> ${esc(t('dp_hear_canonical'))}
            </button>
          </div>
        ` : ''}
      </section>
    `
  }

  _htmlPracticePanel() {
    const lesson = this.#config?.lesson || {}
    const activities = Array.isArray(lesson.practice_activities) ? lesson.practice_activities : []
    const reviewQueue = Array.isArray(this.#config?.reviewQueue) ? this.#config.reviewQueue : []
    const dueItems = reviewQueue.slice(0, 5)
    const sentenceText = this.#config?.sentenceText || ''

    const checks = activities
      .filter(a => a?.type === 'comprehension_questions' && a.prompt && a.expected_answer)
      .slice(0, 2)

    const sentenceDrills = activities
      .filter(a => ['sentence_level_vocabulary_recall', 'cloze_completion'].includes(a?.type) && a.prompt && a.expected_answer)
      .slice(0, 2)

    const chunkDrills = activities
      .filter(a => a?.type === 'chunk_recall' && a.prompt && a.expected_answer)
      .slice(0, 2)

    const discItems = activities
      .filter(a => a?.type === 'grammar_discrimination' && a.prompt && a.expected_answer)
      .slice(0, 2)

    const transformDrills = activities
      .filter(a => a?.type === 'transformation_drills' && a.prompt && a.expected_answer)
      .slice(0, 2)

    const productionItems = activities
      .filter(a => a?.type === 'constrained_free_production' && a.prompt)
      .slice(0, 1)

    const canRetell = sentenceText.trim().split(/\s+/).length >= 8
    const quizItems = this.#buildMiniQuizItems(lesson, reviewQueue).slice(0, 8)

    const termStateHtml = (() => {
      const tp = this.#config?.termProgress
      if (!tp?.review_bucket) return ''
      const meta = this.#bucketMeta(tp.review_bucket)
      const days = tp.next_review_at
        ? Math.ceil((Date.parse(tp.next_review_at) - Date.now()) / 86400000)
        : null
      const nextText = days != null && days > 0
        ? tr('dp_mm_next_interval', `next in ${days}d`)
        : days != null && days <= 0
          ? tr('dp_bucket_due', 'due')
          : ''
      return /* html */`
        <div class="pane__term-state" data-bucket="${esc(tp.review_bucket)}">
          <span class="pane__term-state-badge">${meta.icon} ${esc(meta.label)}</span>
          ${nextText ? `<span class="pane__term-state-next">${esc(nextText)}</span>` : ''}
        </div>
      `
    })()

    // ── Section: Comprehension (MC) ──────────────────────────────────────────
    const checksHtml = checks.map((a, idx) => {
      const opts = [a.expected_answer, ...(a.acceptable_alternatives || [])].filter(Boolean).slice(0, 4)
      const uniq = [...new Set(opts)].sort(() => Math.random() - 0.5)
      return /* html */`
        <article class="pane__check" data-check-index="${idx}" data-check-type="comprehension_questions" data-expected="${esc(a.expected_answer)}">
          <p class="pane__check-prompt" id="dp-ck-${idx}-prompt">${esc(a.prompt)}</p>
          <div class="pane__check-options" role="group" aria-labelledby="dp-ck-${idx}-prompt">
            ${uniq.map(opt => `<button type="button" class="pane__check-option" data-answer="${esc(opt)}">${esc(opt)}</button>`).join('')}
          </div>
          <p class="pane__muted pane__check-feedback" aria-live="polite" aria-atomic="true"></p>
        </article>
      `
    }).join('')

    // ── Section: Cloze / vocabulary recall (typed) ───────────────────────────
    const sentenceDrillsHtml = sentenceDrills.map((a, idx) => /* html */`
      <article class="pane__check pane__check--typed" data-drill-index="${idx}">
        <p class="pane__check-prompt" id="dp-sd-${idx}-prompt">${esc(a.prompt)}</p>
        <form class="pane__typed-form">
          <input class="pane__typed-input" type="text" autocomplete="off" spellcheck="false" autocorrect="off" autocapitalize="off" aria-labelledby="dp-sd-${idx}-prompt" />
          <button type="submit" class="pane__check-option" aria-describedby="dp-sd-${idx}-prompt">${esc(tr('dp_practice_submit', 'Check'))}</button>
        </form>
        <p class="pane__muted pane__check-feedback" aria-live="polite" aria-atomic="true"></p>
      </article>
    `).join('')

    // ── Section: Chunk recall (idioms / phrases) ─────────────────────────────
    const chunkHtml = chunkDrills.map((a, idx) => /* html */`
      <article class="pane__check pane__check--typed" data-chunk-index="${idx}">
        <p class="pane__drill-section-label">${esc(tr('dp_drill_type_chunk_recall', 'Chunk recall'))}</p>
        <p class="pane__check-prompt" id="dp-chunk-${idx}-prompt">${esc(a.prompt)}</p>
        <form class="pane__typed-form">
          <input class="pane__typed-input" type="text" autocomplete="off" spellcheck="false" autocorrect="off" autocapitalize="off" aria-labelledby="dp-chunk-${idx}-prompt" />
          <button type="submit" class="pane__check-option" aria-describedby="dp-chunk-${idx}-prompt">${esc(tr('dp_practice_submit', 'Check'))}</button>
        </form>
        <p class="pane__muted pane__check-feedback" aria-live="polite" aria-atomic="true"></p>
      </article>
    `).join('')

    // ── Section: Grammar discrimination (MC — pick the right form) ───────────
    const discHtml = discItems.map((a, idx) => {
      const opts = [a.expected_answer, ...(a.acceptable_alternatives || [])].filter(Boolean).slice(0, 4)
      const uniq = [...new Set(opts)].sort(() => Math.random() - 0.5)
      return /* html */`
        <article class="pane__check" data-check-index="${idx}" data-check-type="grammar_discrimination" data-expected="${esc(a.expected_answer)}">
          <p class="pane__drill-section-label">${esc(tr('dp_drill_type_grammar_discrimination', 'Grammar discrimination'))}</p>
          <p class="pane__check-prompt" id="dp-disc-${idx}-prompt">${esc(a.prompt)}</p>
          <div class="pane__check-options" role="group" aria-labelledby="dp-disc-${idx}-prompt">
            ${uniq.map(opt => `<button type="button" class="pane__check-option" data-answer="${esc(opt)}">${esc(opt)}</button>`).join('')}
          </div>
          <p class="pane__muted pane__check-feedback" aria-live="polite" aria-atomic="true"></p>
        </article>
      `
    }).join('')

    // ── Section: Transformation drills (typed, first-class) ──────────────────
    const transformHtml = transformDrills.map((a, idx) => /* html */`
      <article class="pane__check pane__check--typed" data-transform-index="${idx}">
        <p class="pane__drill-section-label">${esc(tr('dp_drill_type_transformation', 'Transform'))}</p>
        <p class="pane__check-prompt" id="dp-tr-${idx}-prompt">${esc(a.prompt)}</p>
        <form class="pane__typed-form">
          <input class="pane__typed-input" type="text" autocomplete="off" spellcheck="false" autocorrect="off" autocapitalize="off" aria-labelledby="dp-tr-${idx}-prompt" />
          <button type="submit" class="pane__check-option" aria-describedby="dp-tr-${idx}-prompt">${esc(tr('dp_practice_submit', 'Check'))}</button>
        </form>
        <p class="pane__muted pane__check-feedback" aria-live="polite" aria-atomic="true"></p>
      </article>
    `).join('')

    // ── Section: Constrained free production (text + self-rate) ─────────────
    const productionHtml = productionItems.map((a, idx) => /* html */`
      <article class="pane__check pane__check--production" data-production-index="${idx}">
        <p class="pane__drill-section-label">${esc(tr('dp_drill_type_constrained_production', 'Free production'))}</p>
        <p class="pane__check-prompt" id="dp-prod-${idx}-prompt">${esc(a.prompt)}</p>
        <div class="pane__production-area">
          <textarea class="pane__typed-input pane__typed-input--area" rows="2"
                    spellcheck="false" autocomplete="off" autocorrect="off" autocapitalize="off"
                    aria-labelledby="dp-prod-${idx}-prompt"></textarea>
          <button type="button" class="pane__reveal-btn" aria-controls="dp-prod-${idx}-reveal">
            ${esc(tr('dp_reveal_example', 'Reveal example'))}
          </button>
        </div>
        <div class="pane__example-reveal" id="dp-prod-${idx}-reveal" hidden>
          <p class="pane__muted"><strong>${esc(tr('dp_example_label', 'Example:'))}</strong> ${esc(a.expected_answer)}</p>
          <p class="pane__muted" id="dp-prod-${idx}-rate-lbl">${esc(tr('dp_self_rate_heading', 'How did you do?'))}</p>
          <div class="pane__self-rate" role="group" aria-labelledby="dp-prod-${idx}-rate-lbl">
            <button type="button" class="pane__self-rate-btn pane__self-rate-btn--again" data-quality="1">${esc(tr('dp_self_rate_again', 'Again'))}</button>
            <button type="button" class="pane__self-rate-btn pane__self-rate-btn--hard"  data-quality="2">${esc(tr('dp_self_rate_hard',  'Hard'))}</button>
            <button type="button" class="pane__self-rate-btn pane__self-rate-btn--good"  data-quality="3">${esc(tr('dp_self_rate_good',  'Good'))}</button>
            <button type="button" class="pane__self-rate-btn pane__self-rate-btn--easy"  data-quality="4">${esc(tr('dp_self_rate_easy',  'Easy'))}</button>
          </div>
        </div>
        <p class="pane__muted pane__check-feedback" aria-live="polite" aria-atomic="true"></p>
      </article>
    `).join('')

    // ── Section: Retrieval retell ─────────────────────────────────────────────
    const retellHtml = !canRetell ? '' : /* html */`
      <article class="pane__check pane__check--typed" data-retell-mode="recall">
        <p class="pane__check-prompt" id="dp-retell-recall-prompt">${esc(tr('dp_recall_challenge', 'Recall challenge: without looking, write key details from this passage.'))}</p>
        <form class="pane__typed-form">
          <input class="pane__typed-input" type="text" autocomplete="off" spellcheck="false" autocorrect="off" autocapitalize="off" aria-labelledby="dp-retell-recall-prompt" />
          <button type="submit" class="pane__check-option" aria-describedby="dp-retell-recall-prompt">${esc(tr('dp_practice_submit', 'Check'))}</button>
        </form>
        <p class="pane__muted pane__check-feedback" aria-live="polite" aria-atomic="true"></p>
      </article>
      ${[
        ['target_language',    tr('dp_retell_target_language',    'Retell in the target language.')],
        ['interface_language', tr('dp_retell_interface_language', 'Retell in your interface language.')],
        ['three_facts',        tr('dp_retell_three_facts',        'List 3 key facts from the passage.')],
        ['continue_story',     tr('dp_retell_continue_story',     'Continue the story in 1–2 sentences.')],
      ].map(([mode, prompt]) => /* html */`
        <article class="pane__check pane__check--typed" data-retell-mode="${mode}">
          <p class="pane__check-prompt" id="dp-retell-${mode}-prompt">${esc(prompt)}</p>
          <form class="pane__typed-form">
            <input class="pane__typed-input" type="text" autocomplete="off" spellcheck="false" autocorrect="off" autocapitalize="off" aria-labelledby="dp-retell-${mode}-prompt" />
            <button type="submit" class="pane__check-option" aria-describedby="dp-retell-${mode}-prompt">${esc(tr('dp_practice_submit', 'Check'))}</button>
          </form>
          <p class="pane__muted pane__check-feedback" aria-live="polite" aria-atomic="true"></p>
        </article>
      `).join('')}
    `

    // ── Mini-quiz ─────────────────────────────────────────────────────────────
    const quizItemsHtml = quizItems.map((q, idx) => /* html */`
      <article class="pane__check pane__check--typed" data-quiz-index="${idx}">
        <p class="pane__check-prompt" id="dp-qi-${idx}-prompt"><strong>${esc(tr(`dp_quiz_type_${q.kind}`, 'Quiz'))}</strong> · ${esc(q.prompt)}</p>
        <form class="pane__typed-form">
          <input class="pane__typed-input" type="text" autocomplete="off" spellcheck="false" autocorrect="off" autocapitalize="off" aria-labelledby="dp-qi-${idx}-prompt" />
          <button type="submit" class="pane__check-option" aria-describedby="dp-qi-${idx}-prompt">${esc(tr('dp_practice_submit', 'Check'))}</button>
        </form>
        <p class="pane__muted pane__check-feedback" aria-live="polite" aria-atomic="true"></p>
      </article>
    `).join('')

    return /* html */`
      <section
        id="dp-panel-practice"
        role="tabpanel"
        aria-labelledby="dp-tab-practice"
        class="pane__panel"
        hidden
      >
        <section class="pane__subsection" aria-labelledby="dp-practice-h">
          <h3 class="pane__section-heading" id="dp-practice-h">${esc(t('dp_practice_heading'))}</h3>
          <p class="pane__muted">${esc(t('dp_practice_description'))}</p>
          ${termStateHtml}
          <article class="pane__check" aria-labelledby="dp-practice-why-h">
            <p class="pane__check-prompt" id="dp-practice-why-h"><strong>${esc(tr('dp_practice_explain_title', 'Why practice?'))}</strong></p>
            <p class="pane__muted">${esc(tr('dp_practice_explain_body', 'Practice helps turn reading into memory. Start with comprehension checks, then try vocabulary recall and pattern activities. Missed terms come back later for review, while strong terms appear less often.'))}</p>
            <p class="pane__muted">${esc(tr('dp_practice_explain_optional', 'Practice is optional—you can skip it anytime and keep reading.'))}</p>
            <p class="pane__muted">${esc(tr('dp_practice_explain_memory_map', 'Practice updates your Memory Map by strengthening terms you answer well and resurfacing terms you miss.'))}</p>
          </article>
          <button class="pane__study-btn pane__study-btn--inline" type="button">${esc(t('dp_practice_start_btn'))}</button>
          <p class="pane__muted">${esc(t('dp_practice_tip'))}</p>
          <p class="pane__muted pane__session-score" aria-live="polite" aria-atomic="true"></p>

          ${dueItems.length ? /* html */`
            <article class="pane__check">
              <p class="pane__check-prompt"><strong>${esc(tr('dp_due_now', 'Due now'))}</strong></p>
              <ul class="pane__variant-list">
                ${dueItems.map(item => `<li class="pane__variant-item"><span class="pane__variant-text">${esc(item.lemma || item.term)}</span></li>`).join('')}
              </ul>
            </article>
          ` : ''}

          ${checksHtml ? /* html */`
            <div class="pane__drill-section" data-drill-section="comprehension">
              <p class="pane__drill-section-label">${esc(tr('dp_drill_section_comprehension', 'Comprehension'))}</p>
              ${checksHtml}
            </div>
          ` : ''}

          ${sentenceDrillsHtml ? /* html */`
            <div class="pane__drill-section" data-drill-section="cloze">
              <p class="pane__drill-section-label">${esc(tr('dp_drill_section_cloze', 'Vocabulary & Cloze'))}</p>
              ${sentenceDrillsHtml}
            </div>
          ` : ''}

          ${chunkHtml ? /* html */`
            <div class="pane__drill-section" data-drill-section="chunk">
              ${chunkHtml}
            </div>
          ` : ''}

          ${discHtml ? /* html */`
            <div class="pane__drill-section" data-drill-section="discrimination">
              ${discHtml}
            </div>
          ` : ''}

          ${transformHtml ? /* html */`
            <div class="pane__drill-section" data-drill-section="transform">
              <p class="pane__drill-section-label">${esc(tr('dp_drill_section_transform', 'Transformation'))}</p>
              ${transformHtml}
            </div>
          ` : ''}

          ${productionHtml ? /* html */`
            <div class="pane__drill-section" data-drill-section="production">
              ${productionHtml}
            </div>
          ` : ''}

          ${retellHtml ? /* html */`
            <div class="pane__drill-section" data-drill-section="retell">
              <p class="pane__drill-section-label">${esc(tr('dp_drill_section_retell', 'Retrieval & Retell'))}</p>
              ${retellHtml}
            </div>
          ` : ''}

          ${quizItems.length >= 5 ? /* html */`
            <article class="pane__check">
              <p class="pane__check-prompt"><strong>${esc(tr('dp_quiz_heading', 'Mini-quiz'))}</strong></p>
              <p class="pane__muted">${esc(tr('dp_quiz_description', 'Optional mixed review across current and older terms.'))}</p>
              <details>
                <summary>${esc(tr('dp_quiz_start', 'Start short quiz'))}</summary>
                <div class="pane__quiz" data-quiz-items='${esc(JSON.stringify(quizItems))}'>
                  ${quizItemsHtml}
                  <button type="button" class="pane__check-option" data-quiz-finish>${esc(tr('dp_quiz_finish', 'Finish quiz'))}</button>
                  <p class="pane__muted pane__quiz-progress" aria-live="polite" aria-atomic="true"></p>
                  <div class="pane__quiz-mistakes"></div>
                </div>
              </details>
            </article>
          ` : ''}

        </section>
      </section>
    `
  }

  #buildMiniQuizItems(lesson, reviewQueue) {
    const activities = Array.isArray(lesson.practice_activities) ? lesson.practice_activities : []
    const currentTerm = lesson.lesson_data?.lemma || lesson.title || ''
    const dueTerms = reviewQueue
      .filter((row) => row.review_bucket === 'due' || row.review_bucket === 'weak')
      .map((row) => row.lemma || row.term)
      .filter(Boolean)
    const weightedDue = [...dueTerms, ...dueTerms]
    const questions = []
    if (currentTerm && lesson.explanation) {
      questions.push({
        kind: 'term',
        prompt: tr('dp_quiz_prompt_current', `Type the current lesson term for this meaning: ${lesson.explanation}`),
        answers: [currentTerm],
      })
    }
    for (const term of weightedDue.slice(0, 4)) {
      questions.push({
        kind: 'due',
        prompt: tr('dp_quiz_prompt_due', `Type this review term: ${term}`),
        answers: [term],
      })
    }
    for (const a of activities.filter((x) => x?.type === 'comprehension_questions').slice(0, 2)) {
      questions.push({ kind: 'comprehension', prompt: a.prompt, answers: [a.expected_answer, ...(a.acceptable_alternatives || [])].filter(Boolean) })
    }
    for (const a of activities.filter((x) => x?.type === 'cloze_completion').slice(0, 2)) {
      questions.push({ kind: 'cloze', prompt: a.prompt, answers: [a.expected_answer, ...(a.acceptable_alternatives || [])].filter(Boolean) })
    }
    for (const a of activities.filter((x) => x?.type === 'notice_the_pattern' || x?.type === 'transformation_drills').slice(0, 2)) {
      questions.push({ kind: 'grammar', prompt: a.prompt, answers: [a.expected_answer, ...(a.acceptable_alternatives || [])].filter(Boolean) })
    }
    for (const a of activities.filter((x) => x?.type === 'chunk_recall').slice(0, 1)) {
      questions.push({ kind: 'chunk', prompt: a.prompt, answers: [a.expected_answer, ...(a.acceptable_alternatives || [])].filter(Boolean) })
    }
    return shuffled(questions).filter((q) => q.answers.length > 0)
  }

  // ── Review tab ────────────────────────────────────────────────────────────────

  _htmlReviewPanel() {
    return /* html */`
      <section
        id="dp-panel-review"
        role="tabpanel"
        aria-labelledby="dp-tab-review"
        class="pane__panel"
        hidden
      >
        <div id="dp-review-status" class="pane__review-status" aria-live="polite" aria-atomic="false">
          <p class="pane__muted">${esc(tr('dp_review_tab_intro', 'Select this tab to load your review status for this item.'))}</p>
        </div>
      </section>
    `
  }

  // ── Concept help dialog ───────────────────────────────────────────────────────

  _htmlConceptDialog() {
    return /* html */`
      <div id="dp-concept-dialog"
           class="pane__concept-dialog"
           role="dialog"
           aria-modal="true"
           aria-labelledby="dp-concept-title"
           hidden>
        <div class="pane__concept-dialog-inner">
          <header class="pane__concept-dialog-header">
            <h3 id="dp-concept-title" class="pane__concept-dialog-title"></h3>
            <button class="pane__concept-dialog-close" type="button"
                    aria-label="${esc(t('dp_concept_dialog_close'))}">&#x2715;</button>
          </header>
          <div class="pane__concept-dialog-body"></div>
        </div>
      </div>
    `
  }

  async #openConceptDialog(conceptId, triggerEl) {
    const dialog  = this.shadowRoot?.querySelector('#dp-concept-dialog')
    if (!dialog) return
    this.#conceptDialogTrigger = triggerEl

    const titleEl = dialog.querySelector('#dp-concept-title')
    const bodyEl  = dialog.querySelector('.pane__concept-dialog-body')
    if (titleEl) titleEl.textContent = '…'
    if (bodyEl)  bodyEl.innerHTML = ''
    dialog.hidden = false
    dialog.querySelector('.pane__concept-dialog-close')?.focus()

    try {
      const { language, uiLang } = this.#config || {}
      const params = new URLSearchParams()
      if (language) params.set('language_code', language)
      if (uiLang)   params.set('l1_language', uiLang)
      const token = localStorage.getItem('mnemosyne_token')
      const resp = await fetch(
        `${API_BASE}/lesson/concepts/${encodeURIComponent(conceptId)}?${params}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} },
      )
      if (!resp.ok) throw new Error(`${resp.status}`)
      const concept = await resp.json()
      if (titleEl) titleEl.textContent = concept.title || conceptId
      if (bodyEl)  bodyEl.innerHTML = this.#renderConceptDialogBody(concept)
    } catch {
      if (titleEl) titleEl.textContent = t('dp_concept_unavailable')
      if (bodyEl)  bodyEl.innerHTML = ''
    }
  }

  #renderConceptDialogBody(concept) {
    const parts = []
    if (concept.short_definition) {
      parts.push(`<p class="pane__concept-def">${esc(concept.short_definition)}</p>`)
    }
    if (concept.learner_explanation) {
      parts.push(`<p class="pane__concept-body">${esc(concept.learner_explanation)}</p>`)
    }
    if (concept.target_language_note) {
      parts.push(`<p class="pane__concept-note">${esc(concept.target_language_note)}</p>`)
    }
    if (concept.l1_comparison) {
      parts.push(`<p class="pane__concept-note pane__concept-note--l1">${esc(concept.l1_comparison)}</p>`)
    }
    if (Array.isArray(concept.examples) && concept.examples.length) {
      const items = concept.examples.map(ex => `<li class="pane__concept-example-item">${esc(ex)}</li>`).join('')
      parts.push(`<p class="pane__concept-section-label">${esc(t('dp_concept_examples'))}</p><ul class="pane__concept-examples">${items}</ul>`)
    }
    if (Array.isArray(concept.related_concepts) && concept.related_concepts.length) {
      const items = concept.related_concepts.map(rc => `<li>${esc(rc)}</li>`).join('')
      parts.push(`<p class="pane__concept-section-label">${esc(t('dp_concept_related'))}</p><ul class="pane__concept-related">${items}</ul>`)
    }
    return parts.join('')
  }

  #closeConceptDialog() {
    const dialog = this.shadowRoot?.querySelector('#dp-concept-dialog')
    if (dialog) dialog.hidden = true
    const trigger = this.#conceptDialogTrigger
    this.#conceptDialogTrigger = null
    if (trigger) trigger.focus()
  }

  async #fetchReviewStatus() {
    if (this.#reviewStatusFetched) return
    const el = this.shadowRoot?.querySelector('#dp-review-status')
    if (!el) return
    const { lesson } = this.#config
    const objectId = lesson?.id
    if (!objectId) return

    this.#reviewStatusFetched = true
    el.innerHTML = `<p class="pane__muted" aria-live="polite">${esc(tr('dp_review_loading', 'Loading review status…'))}</p>`

    try {
      const token = localStorage.getItem('mnemosyne_token')
      const resp = await fetch(
        `${API_BASE}/weakness/object/${encodeURIComponent(objectId)}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} }
      )
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const status = await resp.json()
      el.innerHTML = this.#renderReviewStatus(status)
    } catch (_err) {
      this.#reviewStatusFetched = false
      el.innerHTML = `<p class="pane__muted">${esc(tr('dp_review_error', 'Review status unavailable. Sign in to track your progress.'))}</p>`
    }
  }

  #renderReviewStatus(status) {
    const STAGE_LABELS = {
      recognition:               tr('dp_stage_recognition',               'Recognition'),
      guided_recall:             tr('dp_stage_guided_recall',             'Guided recall'),
      partial_production:        tr('dp_stage_partial_production',        'Partial production'),
      transformation:            tr('dp_stage_transformation',            'Transformation'),
      free_production:           tr('dp_stage_free_production',           'Free production'),
      contextual_interpretation: tr('dp_stage_contextual_interpretation', 'Contextual interpretation'),
    }
    const STAGE_DESCS = {
      recognition:               tr('dp_stage_desc_recognition',               'Identifying this item on encounter.'),
      guided_recall:             tr('dp_stage_desc_guided_recall',             'Recalling with contextual support.'),
      partial_production:        tr('dp_stage_desc_partial_production',        'Producing with scaffolding.'),
      transformation:            tr('dp_stage_desc_transformation',            'Applying patterns under instruction.'),
      free_production:           tr('dp_stage_desc_free_production',           'Using this item independently in context.'),
      contextual_interpretation: tr('dp_stage_desc_contextual_interpretation', 'Interpreting subtle discourse nuances.'),
    }
    const STAGE_ORDER = [
      'recognition', 'guided_recall', 'partial_production',
      'transformation', 'free_production', 'contextual_interpretation',
    ]

    const stage = status.progression_stage || 'recognition'
    const stageIdx = STAGE_ORDER.indexOf(stage)
    const masteryPct = Math.round((status.mastery_score || 0) * 100)

    const daysUntil = status.days_until_due
    const daysText = daysUntil != null
      ? (daysUntil <= 0
          ? tr('dp_due_now', 'Due now')
          : tr('dp_due_in_days', `Due in ${daysUntil}d`))
      : ''

    const stepsHtml = STAGE_ORDER.map((s, i) => {
      const done = i < stageIdx
      const current = i === stageIdx
      const marker = done ? '✓' : current ? '●' : '○'
      return /* html */`
        <li class="pane__stage-step${done ? ' pane__stage-step--done' : ''}${current ? ' pane__stage-step--current' : ''}">
          <span class="pane__stage-marker" aria-hidden="true">${marker}</span>
          <span class="pane__stage-name">${esc(STAGE_LABELS[s] || s)}</span>
        </li>
      `
    }).join('')

    const confusionHtml = (status.confusion_pairs || []).map(pair => /* html */`
      <li class="pane__confusion-item">
        <span class="pane__confusion-form">${esc(pair.confused_with)}</span>
        <span class="pane__confusion-count" aria-label="${pair.confusion_count} time${pair.confusion_count !== 1 ? 's' : ''}">${pair.confusion_count}×</span>
      </li>
    `).join('')

    const masteryBar = /* html */`
      <div class="pane__mastery-bar" role="progressbar" aria-valuenow="${masteryPct}" aria-valuemin="0" aria-valuemax="100" aria-label="${esc(tr('dp_review_mastery', 'Mastery'))} ${masteryPct}%">
        <div class="pane__mastery-bar-fill" style="inline-size:${masteryPct}%"></div>
      </div>
    `

    return /* html */`
      <section class="pane__subsection" aria-labelledby="dp-review-stage-h">
        <h3 class="pane__section-heading" id="dp-review-stage-h">${esc(tr('dp_review_acquisition_stage', 'Acquisition stage'))}</h3>
        <div class="pane__stage-badge" data-stage="${esc(stage)}">${esc(STAGE_LABELS[stage] || stage)}</div>
        <p class="pane__muted">${esc(STAGE_DESCS[stage] || '')}</p>
        <ol class="pane__stage-steps" aria-label="${esc(tr('dp_stage_progress_label', 'Progress through acquisition stages'))}">
          ${stepsHtml}
        </ol>
      </section>

      <section class="pane__subsection" aria-labelledby="dp-review-schedule-h">
        <h3 class="pane__section-heading" id="dp-review-schedule-h">${esc(tr('dp_review_schedule', 'Schedule'))}</h3>
        ${masteryBar}
        <dl class="pane__fields">
          <div class="pane__field">
            <dt class="pane__field-label">${esc(tr('dp_review_mastery', 'Mastery'))}</dt>
            <dd class="pane__field-value">${masteryPct}%</dd>
          </div>
          ${daysText ? /* html */`
          <div class="pane__field">
            <dt class="pane__field-label">${esc(tr('dp_review_next_review', 'Next review'))}</dt>
            <dd class="pane__field-value">${esc(daysText)}</dd>
          </div>
          ` : ''}
          ${status.total_reviews ? /* html */`
          <div class="pane__field">
            <dt class="pane__field-label">${esc(tr('dp_review_total_reviews', 'Reviews'))}</dt>
            <dd class="pane__field-value">${status.total_reviews}</dd>
          </div>
          ` : ''}
          ${status.concept_type_label ? /* html */`
          <div class="pane__field">
            <dt class="pane__field-label">${esc(tr('dp_review_concept_type', 'Concept type'))}</dt>
            <dd class="pane__field-value">${esc(status.concept_type_label)}</dd>
          </div>
          ` : ''}
          ${status.stability != null ? /* html */`
          <div class="pane__field">
            <dt class="pane__field-label">${esc(tr('dp_review_stability', 'Stability'))}</dt>
            <dd class="pane__field-value">${Math.round(status.stability)}d</dd>
          </div>
          ` : ''}
          ${status.lapses != null && status.lapses > 0 ? /* html */`
          <div class="pane__field">
            <dt class="pane__field-label">${esc(tr('dp_review_lapses', 'Lapses'))}</dt>
            <dd class="pane__field-value">${status.lapses}</dd>
          </div>
          ` : ''}
        </dl>
      </section>

      ${status.confusion_pairs?.length ? /* html */`
      <section class="pane__subsection" aria-labelledby="dp-review-confusion-h">
        <h3 class="pane__section-heading" id="dp-review-confusion-h">${esc(tr('dp_review_confusion_pairs', 'Confusion pairs'))}</h3>
        <p class="pane__muted">${esc(tr('dp_review_confusion_desc', 'Items you have confused with this one. These are scheduled for contrast practice.'))}</p>
        <ul class="pane__confusion-list">
          ${confusionHtml}
        </ul>
      </section>
      ` : ''}
    `
  }

  // ── Event wiring ─────────────────────────────────────────────────────────────

  // ── Translation fetchers ─────────────────────────────────────────────────────

  async #fetchVocabTranslation() {
    if (this.#vocabTranslationFetched || !this.#onTranslate) return
    const { lesson, language, uiLang } = this.#config
    if (lesson.type !== 'vocabulary' || !uiLang || uiLang === language) return
    const lemma = lesson.lesson_data?.lemma || lesson.examples?.[0]
    if (!lemma) return
    this.#vocabTranslationFetched = true
    const result = await this.#onTranslate(lemma, language, uiLang)
    if (!result) return
    const row  = this.shadowRoot.querySelector('#dp-panel-explanation .pane__translation-row')
    const text = this.shadowRoot.querySelector('#dp-panel-explanation .pane__translation-text')
    const attr = this.shadowRoot.querySelector('#dp-panel-explanation .pane__translation-attribution')
    if (row && text) {
      text.textContent = result.text
      if (attr && result.attribution) attr.textContent = result.attribution
      row.hidden = false
    }
  }

  async #fetchExplanationTranslation() {
    if (this.#explanationTranslationFetched || !this.#onTranslate) return
    const { lesson, uiLang } = this.#config
    const explanation = lesson.explanation
    if (!explanation || !uiLang || uiLang === 'en') return
    this.#explanationTranslationFetched = true
    const result = await this.#onTranslate(explanation, 'en', uiLang)
    if (!result?.text) return
    const el = this.shadowRoot.querySelector('.pane__explanation')
    if (el) el.textContent = result.text
  }

  async #fetchSentenceTranslation(sentenceText) {
    if (this.#sentenceTranslationFetched || !this.#onTranslate) return
    const { language, uiLang } = this.#config
    if (!sentenceText || !uiLang || uiLang === language) return
    this.#sentenceTranslationFetched = true

    // Wrap the matched phrase in the source sentence with rare Unicode bracket
    // markers before sending to MT. Most MT engines pass through characters
    // they cannot translate, so the markers survive and identify the phrase
    // boundary in the output — giving us the contextual translation of the
    // exact phrase rather than an out-of-context word translation.
    const phrase = this.#matchedVariant
    const OPEN = '⟪'  // ⟪  Mathematical Left Double Angle Bracket
    const CLOSE = '⟫' // ⟫  Mathematical Right Double Angle Bracket
    let markedSentence = sentenceText
    let useMarkers = false
    if (phrase) {
      const re = new RegExp(phrase.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')
      if (re.test(sentenceText)) {
        markedSentence = sentenceText.replace(re, m => `${OPEN}${m}${CLOSE}`)
        useMarkers = true
      }
    }

    const result = await this.#onTranslate(markedSentence, language, uiLang)
    if (!result) return

    const row  = this.shadowRoot.querySelector('#dp-panel-context .pane__sentence-translation-row')
    const text = this.shadowRoot.querySelector('#dp-panel-context .pane__sentence-translation-text')
    const attr = this.shadowRoot.querySelector('#dp-panel-context .pane__sentence-translation-attribution')
    if (!row || !text) return

    let translatedText = result.text
    let highlight = ''

    if (useMarkers) {
      // Extract the phrase the MT placed between the markers.
      const markerRe = new RegExp(`⟪([^⟫]*)⟫`)
      const m = markerRe.exec(translatedText)
      if (m) {
        highlight = m[1]
        // Remove markers, keep extracted phrase in place.
        translatedText = translatedText.slice(0, m.index) + m[1] + translatedText.slice(m.index + m[0].length)
      } else {
        // Markers lost — strip any stray marker chars and degrade gracefully.
        translatedText = translatedText.replace(/[⟪⟫]/g, '')
      }
    }

    highlightPhrase(text, translatedText, highlight)
    if (attr && result.attribution) attr.textContent = result.attribution
    row.hidden = false
  }

  _wireEvents(matchedVariant, canonical, sentenceText, isNonCanonical) {
    const { lesson, language, ttsTag } = this.#config

    this.shadowRoot.querySelectorAll('.pane__check').forEach((checkEl) => {
      if (checkEl.closest('.pane__quiz')) return  // handled by quizContainer block
      const feedback = checkEl.querySelector('.pane__check-feedback')
      const typedForm = checkEl.querySelector('.pane__typed-form')
      if (typedForm) {
        const retellMode = checkEl.dataset.retellMode
        let activeDrill = null
        if (checkEl.dataset.drillIndex !== undefined) {
          const idx = Number(checkEl.dataset.drillIndex)
          activeDrill = (lesson.practice_activities || [])
            .filter(a => ['sentence_level_vocabulary_recall', 'cloze_completion'].includes(a?.type))[idx]
        } else if (checkEl.dataset.chunkIndex !== undefined) {
          activeDrill = (lesson.practice_activities || [])
            .filter(a => a?.type === 'chunk_recall')[Number(checkEl.dataset.chunkIndex)]
        } else if (checkEl.dataset.transformIndex !== undefined) {
          activeDrill = (lesson.practice_activities || [])
            .filter(a => a?.type === 'transformation_drills')[Number(checkEl.dataset.transformIndex)]
        }
        const input = checkEl.querySelector('.pane__typed-input')
        let attempts = 0
        typedForm.addEventListener('submit', (event) => {
          event.preventDefault()
          attempts += 1
          const typed = input?.value || ''
          if (retellMode) {
            const reference = [sentenceText, lesson.explanation, ...(lesson.examples || [])].filter(Boolean).join(' ')
            const { overlap, ratio } = compareMeaning(typed, reference, language)
            const meaningFocused = ratio >= 0.22
            if (feedback) _setFeedback(feedback, meaningFocused,
              tr('dp_retell_correct', 'Good meaning recall.'),
              tr('dp_retell_try_again', 'Try again. Focus on main ideas: who/what happened, and why it matters.')
            )
            const historyKey = `mn-retell-history-${lesson.id}`
            const prior = JSON.parse(localStorage.getItem(historyKey) || '[]')
            prior.push({ mode: retellMode, answer: typed, overlap, ratio, meaningFocused, answeredAt: new Date().toISOString() })
            localStorage.setItem(historyKey, JSON.stringify(prior.slice(-25)))
            this.dispatchEvent(new CustomEvent('pane-practice-check', {
              bubbles: true,
              composed: true,
              detail: { type: `retell_${retellMode}`, correct: meaningFocused, answeredAt: new Date().toISOString(), lesson, language, objectId: lesson.id, term: lesson.lesson_data?.lemma || lesson.title, attempts },
            }))
            this._updatePracticeScore(meaningFocused)
            return
          }
          const accepted = [activeDrill?.expected_answer, ...(activeDrill?.acceptable_alternatives || [])].filter(Boolean)
          const correct = accepted.some((ans) => normalizeForLanguage(ans, language) === normalizeForLanguage(typed, language))
          if (feedback) _setFeedback(feedback, correct,
            tr('dp_practice_correct', 'Correct.'),
            activeDrill?.feedback_text || tr('dp_practice_try_again', 'Try again.')
          )
          this.dispatchEvent(new CustomEvent('pane-practice-check', {
            bubbles: true,
            composed: true,
            detail: { type: activeDrill?.type || 'typed', correct, answeredAt: new Date().toISOString(), lesson, language, objectId: lesson.id, term: activeDrill?.target_term_or_pattern, attempts },
          }))
          this._updatePracticeScore(correct)
          if (correct && input) input.disabled = true
        })
        return
      }
      const buttons = checkEl.querySelectorAll('.pane__check-option')
      let answered = false
      buttons.forEach((btn) => btn.addEventListener('click', () => {
        if (answered) return
        answered = true
        const expected = checkEl.dataset.expected || ''
        const selected = btn.dataset.answer || ''
        const correct = normalize(selected) === normalize(expected)
        buttons.forEach((b) => { b.disabled = true })
        const checkType = checkEl.dataset.checkType || 'comprehension_questions'
        const checkIdx = Number(checkEl.dataset.checkIndex ?? -1)
        const mcActivity = checkIdx >= 0
          ? (lesson.practice_activities || []).filter(a => a?.type === checkType)[checkIdx]
          : null
        if (feedback) {
          _setFeedback(feedback, correct,
            tr('dp_practice_correct', 'Correct.'),
            mcActivity?.feedback_text || tr('dp_practice_try_again', 'Try again.')
          )
        }
        this.dispatchEvent(new CustomEvent('pane-practice-check', {
          bubbles: true,
          composed: true,
          detail: {
            type: checkType,
            correct,
            wrongAnswer: correct ? null : selected,
            answeredAt: new Date().toISOString(),
            lesson,
            language,
            objectId: lesson.id,
            term: mcActivity?.target_term_or_pattern,
            attempts: 1,
          },
        }))
        this._updatePracticeScore(correct)
      }))
    })

    const quizContainer = this.shadowRoot.querySelector('.pane__quiz')
    if (quizContainer) {
      const quizItems = JSON.parse(quizContainer.dataset.quizItems || '[]')
      const state = { answered: 0, correct: 0, mistakes: [] }
      const progressEl = quizContainer.querySelector('.pane__quiz-progress')
      const mistakesEl = quizContainer.querySelector('.pane__quiz-mistakes')
      const updateProgress = () => {
        if (!progressEl) return
        progressEl.textContent = tr(
          'dp_quiz_progress',
          `Progress: ${state.answered}/${quizItems.length} · Score: ${state.correct}`
        )
      }
      updateProgress()
      quizContainer.querySelectorAll('[data-quiz-index]').forEach((rowEl) => {
        const idx = Number(rowEl.dataset.quizIndex)
        const item = quizItems[idx]
        const form = rowEl.querySelector('.pane__typed-form')
        const input = rowEl.querySelector('.pane__typed-input')
        const feedback = rowEl.querySelector('.pane__check-feedback')
        let done = false
        form?.addEventListener('submit', (event) => {
          event.preventDefault()
          if (done) return
          done = true
          state.answered += 1
          const typed = input?.value || ''
          const correct = (item?.answers || []).some((ans) => normalizeForLanguage(ans, language) === normalizeForLanguage(typed, language))
          if (correct) state.correct += 1
          else state.mistakes.push({ prompt: item.prompt, expected: item.answers?.[0] || '' })
          if (feedback) _setFeedback(feedback, correct,
            tr('dp_practice_correct', 'Correct.'),
            tr('dp_quiz_try_again', 'Review this one after finishing.')
          )
          if (input) input.disabled = true
          updateProgress()
          this.dispatchEvent(new CustomEvent('pane-practice-check', {
            bubbles: true, composed: true,
            detail: { type: `mini_quiz_${item?.kind || 'item'}`, correct, answeredAt: new Date().toISOString(), lesson, language, objectId: lesson.id, term: lesson.lesson_data?.lemma || lesson.title, attempts: 1 },
          }))
          this._updatePracticeScore(correct)
        })
      })
      quizContainer.querySelector('[data-quiz-finish]')?.addEventListener('click', () => {
        if (!progressEl) return
        progressEl.textContent = tr('dp_quiz_done', `Quiz complete: ${state.correct}/${quizItems.length}.`)
        if (mistakesEl) {
          mistakesEl.innerHTML = state.mistakes.length
            ? `<p class="pane__muted"><strong>${esc(tr('dp_quiz_review_mistakes', 'Review mistakes'))}</strong></p><ul class="pane__variant-list">${state.mistakes.map((m) => `<li class="pane__variant-item">${esc(m.prompt)} → <strong>${esc(m.expected)}</strong></li>`).join('')}</ul>`
            : `<p class="pane__muted">${esc(tr('dp_quiz_perfect', 'No mistakes this round.'))}</p>`
        }
      })
    }

    // Constrained free production — reveal + self-rate
    this.shadowRoot.querySelectorAll('[data-production-index]').forEach((prodEl) => {
      const prodIdx = Number(prodEl.dataset.productionIndex)
      const activity = (lesson.practice_activities || [])
        .filter(a => a?.type === 'constrained_free_production')[prodIdx]
      const revealBtn = prodEl.querySelector('.pane__reveal-btn')
      const revealArea = prodEl.querySelector('.pane__example-reveal')
      const feedback = prodEl.querySelector('.pane__check-feedback')

      revealBtn?.addEventListener('click', () => {
        if (revealArea) revealArea.hidden = false
        if (revealBtn) revealBtn.disabled = true
      })

      prodEl.querySelectorAll('.pane__self-rate-btn').forEach((btn) => {
        btn.addEventListener('click', () => {
          const quality = Number(btn.dataset.quality)
          const correct = quality >= 3
          if (feedback) _setFeedback(feedback, correct,
            tr('dp_practice_correct', 'Correct.'),
            activity?.feedback_text || tr('dp_practice_try_again', 'Try again.')
          )
          prodEl.querySelectorAll('.pane__self-rate-btn').forEach(b => { b.disabled = true })
          this.dispatchEvent(new CustomEvent('pane-practice-check', {
            bubbles: true, composed: true,
            detail: { type: 'constrained_free_production', correct, quality, answeredAt: new Date().toISOString(), lesson, language, objectId: lesson.id, term: activity?.target_term_or_pattern, attempts: 1 },
          }))
          this._updatePracticeScore(correct)
        })
      })
    })

    // Note — restore saved value from localStorage on each render
    const noteInput = this.shadowRoot.querySelector('.pane__note-input')
    if (noteInput) {
      noteInput.value = localStorage.getItem(`mn-note-${lesson.id}`) ?? ''
    }

    // Nuance pair choice buttons — reveal explanation after selection.
    this.shadowRoot.querySelectorAll('.pane__nuance-pair').forEach((pairEl) => {
      const feedback  = pairEl.querySelector('.pane__nuance-feedback')
      const reveal    = pairEl.querySelector('.pane__nuance-reveal')
      const correct   = pairEl.dataset.answer
      let answered    = false

      pairEl.querySelectorAll('.pane__nuance-choice').forEach((btn) => {
        btn.addEventListener('click', () => {
          if (answered) return
          answered = true
          const chosen  = btn.dataset.choice
          const isRight = chosen === correct

          pairEl.querySelectorAll('.pane__nuance-choice').forEach((b) => {
            b.disabled = true
            if (b.dataset.choice === correct) b.classList.add('pane__nuance-choice--correct')
            else b.classList.add('pane__nuance-choice--wrong')
          })

          if (reveal) reveal.hidden = false

          if (feedback) {
            feedback.textContent = ''
            queueMicrotask(() => {
              feedback.textContent = isRight
                ? tr('dp_nuance_correct', 'Right — read the explanation below.')
                : tr('dp_nuance_wrong',   'Not quite — read the explanation to see why.')
            })
          }

          this.dispatchEvent(new CustomEvent('pane-practice-check', {
            bubbles: true,
            composed: true,
            detail: {
              type: 'nuance_discrimination',
              correct: isRight,
              answeredAt: new Date().toISOString(),
              lesson,
              language,
              objectId: lesson.id,
              term: lesson.lesson_data?.nuance_type || lesson.title,
              attempts: 1,
            },
          }))
          this._updatePracticeScore(isRight)
        })
      })
    })

    this.#wireDrag()
  }

  _updatePracticeScore(correct) {
    this.#practiceSession.total += 1
    if (correct) this.#practiceSession.correct += 1
    this._renderSessionScore()
  }

  _renderSessionScore() {
    const el = this.shadowRoot?.querySelector('.pane__session-score')
    if (!el) return
    const { correct, total } = this.#practiceSession
    el.textContent = total > 0 ? tr('dp_session_score', `Session: ${correct}/${total}`) : ''
  }

  #bucketMeta(bucket) {
    const i = (ch) => `<span aria-hidden="true">${ch}</span>`
    const map = {
      new:      { icon: i('✦'), label: tr('adaptive_memory_weak_stat', 'new') },
      due:      { icon: i('⏰'), label: tr('dp_bucket_due', 'due') },
      learning: { icon: i('📖'), label: tr('dp_bucket_learning', 'learning') },
      fading:   { icon: i('📉'), label: tr('adaptive_memory_fading_stat', 'needs review') },
      strong:   { icon: i('⭐'), label: tr('adaptive_memory_strong_stat', 'strong') },
    }
    return map[bucket] ?? { icon: '', label: bucket }
  }

  // Apply aria-selected, tabindex, and panel visibility for the active tab.
  _applyTabState() {
    const tabEls   = Array.from(this.shadowRoot.querySelectorAll('[role="tab"]'))
    const panelEls = Array.from(this.shadowRoot.querySelectorAll('[role="tabpanel"]'))

    tabEls.forEach((tab, i) => {
      const active = i === this.#activeTab
      tab.setAttribute('aria-selected', String(active))
      tab.setAttribute('tabindex', active ? '0' : '-1')
      tab.classList.toggle('pane__tab--active', active)
    })
    panelEls.forEach((panel, i) => {
      panel.hidden = i !== this.#activeTab
    })
  }

  // ── Focus trap ────────────────────────────────────────────────────────────────

  #focusable() {
    return [...this.shadowRoot.querySelectorAll(
      'button:not(:disabled), [href], input:not(:disabled), ' +
      'select:not(:disabled), textarea:not(:disabled), ' +
      '[tabindex]:not([tabindex="-1"])'
    )].filter(el => !el.closest('[hidden]') && !el.closest('[inert]'))
  }

  #trapTab(e) {
    const els = this.#focusable()
    if (!els.length) return
    const first  = els[0]
    const last   = els[els.length - 1]
    const active = this.shadowRoot.activeElement
    if (e.shiftKey) {
      if (active === first) { e.preventDefault(); last.focus() }
    } else {
      if (active === last)  { e.preventDefault(); first.focus() }
    }
  }

  // ── Snap + drag (mobile bottom-sheet) ────────────────────────────────────────

  #setSnap(snap) {
    this.#snap = snap
    this.setAttribute('data-snap', snap)
  }

  #wireDrag() {
    const area = this.shadowRoot.querySelector('.pane__drag-handle-area')
    area?.addEventListener('pointerdown', this.#onDragStart, { passive: true })
  }

  #onDragStart = (e) => {
    if (!window.matchMedia('(max-width: 53.99rem)').matches) return
    this.#dragActive = true
    this.#dragStartY = e.clientY
    this.#dragBaseY  = this.#snap === 'full' ? 0 : window.innerHeight * 0.5
    this.setAttribute('data-dragging', '')
    document.addEventListener('pointermove', this.#onDragMove, { passive: true })
    document.addEventListener('pointerup',   this.#onDragEnd)
  }

  #onDragMove = (e) => {
    if (!this.#dragActive) return
    const raw = this.#dragBaseY + (e.clientY - this.#dragStartY)
    const pct = Math.min(Math.max(raw / window.innerHeight * 100, 0), 110)
    this.style.transform = `translateY(${pct.toFixed(1)}%)`
  }

  #onDragEnd = (e) => {
    if (!this.#dragActive) return
    this.#dragActive = false
    document.removeEventListener('pointermove', this.#onDragMove)
    document.removeEventListener('pointerup',   this.#onDragEnd)
    this.removeAttribute('data-dragging')
    this.style.transform = ''
    const newY  = this.#dragBaseY + (e.clientY - this.#dragStartY)
    const viewH = window.innerHeight
    if      (newY > viewH * 0.65) this.hide()
    else if (newY < viewH * 0.28) this.#setSnap('full')
    else                          this.#setSnap('half')
  }

  // ── Scoped styles ─────────────────────────────────────────────────────────────

  _styles(meta) {
    const ref = meta.ref
    return /* css */`
      /* ── Desktop: hide when not open ────────────────────────────────────── */
      @media (min-width: 54rem) {
        :host(:not([data-open])) {
          display: none;
        }

        :host([data-open]) {
          display: block;
          animation: dp-fadein 0.18s ease;
        }

        @keyframes dp-fadein {
          from { opacity: 0; transform: translateX(0.75rem); }
          to   { opacity: 1; transform: translateX(0); }
        }

        @media (prefers-reduced-motion: reduce) {
          :host([data-open]) { animation: none; }
        }
      }

      /* ── Mobile: bottom-sheet ────────────────────────────────────────────── */
      @media (max-width: 53.99rem) {
        :host {
          position: fixed;
          inset-inline: 0;
          inset-block-end: 0;
          block-size: 100dvh;
          z-index: 200;
          transform: translateY(110%);
          transition: transform 0.35s cubic-bezier(0.32, 0, 0.67, 0);
          pointer-events: none;
        }

        :host([data-open]) {
          pointer-events: auto;
          transition-timing-function: cubic-bezier(0.33, 1, 0.68, 1);
        }

        /* Half snap: top half of pane visible (drag handle + header + tab + body start) */
        :host([data-snap="half"]) { transform: translateY(50%); }

        /* Full snap: entire pane fills viewport */
        :host([data-snap="full"]) { transform: translateY(0); }

        /* No transition while finger is dragging */
        :host([data-dragging]) { transition: none !important; }

        @media (prefers-reduced-motion: reduce) {
          :host                     { transition: none; }
          :host([data-snap="half"]) { transform: translateY(50%); }
          :host([data-snap="full"]) { transform: translateY(0); }
        }
      }

      /* ── Pane shell ─────────────────────────────────────────────────────── */
      .pane {
        background: var(--surface);
        color: var(--text, CanvasText);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        /* Accent stripe on the inline-start edge, keyed to the object type. */
        border-inline-start: 3px solid var(--detail-accent, ${ref});
        display: flex;
        flex-direction: column;
        overflow: hidden;
        block-size: 100%;
        /* max-block-size is set by the parent layout via max-block-size on :host. */
      }

      /* On mobile the pane is a bottom sheet — round the top corners only. */
      @media (max-width: 53.99rem) {
        .pane {
          border-radius: 1rem 1rem 0 0;
          border-block-start: 3px solid var(--detail-accent, ${ref});
          border-inline-start: 1px solid var(--border);
        }
      }

      /* ── Now-playing slot ────────────────────────────────────────────────── */
      slot[name="now-playing"] { display: block; flex-shrink: 0; }

      /* Slot is only meaningful inside the mobile sheet */
      @media (min-width: 54rem) {
        slot[name="now-playing"] { display: none; }
      }

      /* ── Drag handle (mobile affordance + generous touch target) ────────── */
      .pane__drag-handle-area {
        display: none;
      }

      @media (max-width: 53.99rem) {
        .pane__drag-handle-area {
          display: flex;
          justify-content: center;
          align-items: center;
          min-block-size: 1.5rem;
          padding-block: 0.55rem 0.2rem;
          flex-shrink: 0;
          cursor: grab;
          touch-action: none;
          user-select: none;
        }
        .pane__drag-handle-area:active { cursor: grabbing; }

        .pane__drag-handle {
          inline-size: 2.5rem;
          block-size: 0.25rem;
          background: var(--border-input, color-mix(in srgb, CanvasText 28%, Canvas));
          border-radius: 999px;
          pointer-events: none;
        }
      }

      /* ── Header ─────────────────────────────────────────────────────────── */
      .pane__header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.6rem 0.75rem 0.6rem 1rem;
        border-block-end: 1px solid var(--border);
        flex-shrink: 0;
      }

      .pane__badge {
        font-size: 0.6875rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: color-mix(in oklch, var(--detail-accent, ${ref}) 80%, CanvasText);
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 14%, Canvas);
        border: 1px solid color-mix(in oklch, var(--detail-accent, ${ref}) 30%, Canvas);
        border-radius: 999px;
        padding: 0.15rem 0.55rem;
        white-space: nowrap;
        flex-shrink: 0;
      }

      .pane__title {
        flex: 1 1 0;
        font-size: 0.9rem;
        font-weight: 600;
        margin: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        min-inline-size: 0;
        line-height: 1.35;
      }

      .pane__close {
        flex-shrink: 0;
        background: transparent;
        border: none;
        padding: 0;
        min-block-size: 2.75rem;
        min-inline-size: 2.75rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font: inherit;
        font-size: 1.1rem;
        color: var(--muted);
        cursor: pointer;
        border-radius: 0.4rem;
      }
      .pane__close:hover { color: var(--text); background: var(--border); }
      .pane__close:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: 2px;
      }

      /* ── Tab strip ──────────────────────────────────────────────────────── */
      .pane__tabs {
        display: flex;
        border-block-end: 1px solid var(--border);
        flex-shrink: 0;
        overflow-x: auto;
        scrollbar-width: none;
      }
      .pane__tabs::-webkit-scrollbar { display: none; }

      .pane__tab {
        flex: 1;
        background: transparent;
        border: none;
        border-block-end: 2px solid transparent;
        margin-block-end: -1px;
        padding-block: 0.6rem;
        padding-inline: 0.65rem;
        font: inherit;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.01em;
        cursor: pointer;
        color: var(--muted);
        white-space: nowrap;
        min-block-size: 2.75rem;
        text-align: center;
        transition: color 0.1s ease, border-color 0.1s ease;
      }
      .pane__tab--active,
      .pane__tab[aria-selected="true"] {
        color: var(--text);
        border-block-end-color: color-mix(in oklch, var(--detail-accent, ${ref}) 85%, CanvasText);
      }
      .pane__tab:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: -2px;
      }
      @media (prefers-reduced-motion: reduce) {
        .pane__tab { transition: none; }
      }

      /* ── Scrollable panel body ──────────────────────────────────────────── */
      .pane__body {
        flex: 1 1 0;
        overflow-y: auto;
        scrollbar-width: thin;
        scrollbar-color: var(--border) transparent;
        min-block-size: 0;
      }

      .pane__panel {
        padding: 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.9rem;
      }
      .pane__panel[hidden] { display: none; }

      /* ── Confusable warning banner ──────────────────────────────────────── */
      .pane__confusable-warning {
        display: flex;
        align-items: flex-start;
        gap: 0.4rem;
        background: color-mix(in oklch, oklch(0.55 0.20 29) 10%, Canvas);
        border: 1px solid color-mix(in oklch, oklch(0.55 0.20 29) 30%, Canvas);
        border-radius: 0.5rem;
        padding: 0.5rem 0.65rem;
        font-size: 0.8125rem;
        line-height: 1.5;
        color: color-mix(in oklch, oklch(0.55 0.20 29) 85%, CanvasText);
      }

      .pane__confusable-warning-text { flex: 1; margin: 0; }

      /* ── Match-type badge row ────────────────────────────────────────────── */
      .pane__match-row {
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
      }

      .pane__match-note {
        margin: 0;
        font-size: 0.8125rem;
        color: var(--muted);
        font-style: italic;
        line-height: 1.5;
      }

      /* ── Match-type badges ───────────────────────────────────────────────── */
      .pane__match-badge {
        display: inline-flex;
        align-items: center;
        font-size: 0.625rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        border-radius: 999px;
        padding: 0.18rem 0.6rem;
        white-space: nowrap;
        flex-shrink: 0;
      }

      /* Small variant for use inside variant list items */
      .pane__match-badge--sm {
        font-size: 0.5625rem;
        padding: 0.1rem 0.45rem;
      }

      /* canonical — green */
      .pane__match-badge--canonical {
        background: color-mix(in oklch, oklch(0.55 0.18 145) 14%, Canvas);
        color:      color-mix(in oklch, oklch(0.55 0.18 145) 80%, CanvasText);
        border: 1px solid color-mix(in oklch, oklch(0.55 0.18 145) 30%, Canvas);
      }
      /* variant — type accent */
      .pane__match-badge--variant {
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 14%, Canvas);
        color:      color-mix(in oklch, var(--detail-accent, ${ref}) 80%, CanvasText);
        border: 1px solid color-mix(in oklch, var(--detail-accent, ${ref}) 30%, Canvas);
      }
      /* warning — amber */
      .pane__match-badge--warning {
        background: color-mix(in oklch, oklch(0.72 0.18 55) 14%, Canvas);
        color:      color-mix(in oklch, oklch(0.72 0.18 55) 80%, CanvasText);
        border: 1px solid color-mix(in oklch, oklch(0.72 0.18 55) 30%, Canvas);
      }
      /* allusion — violet */
      .pane__match-badge--allusion {
        background: color-mix(in oklch, oklch(0.55 0.18 300) 14%, Canvas);
        color:      color-mix(in oklch, oklch(0.55 0.18 300) 80%, CanvasText);
        border: 1px solid color-mix(in oklch, oklch(0.55 0.18 300) 30%, Canvas);
      }
      /* danger — red (confusable_not_same) */
      .pane__match-badge--danger {
        background: color-mix(in oklch, oklch(0.55 0.20 29) 14%, Canvas);
        color:      color-mix(in oklch, oklch(0.55 0.20 29) 80%, CanvasText);
        border: 1px solid color-mix(in oklch, oklch(0.55 0.20 29) 30%, Canvas);
      }

      /* ── Explanation prose ──────────────────────────────────────────────── */
      .pane__explanation {
        margin: 0;
        font-size: 0.9375rem;
        line-height: 1.6;
      }

      /* ── Translation rows ───────────────────────────────────────────────── */
      .pane__translation-row,
      .pane__sentence-translation-row {
        margin-block-start: 0.5rem;
        padding: 0.45rem 0.6rem;
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 7%, Canvas);
        border-radius: 0.35rem;
        border-inline-start: 2px solid color-mix(in oklch, var(--detail-accent, ${ref}) 40%, Canvas);
      }

      .pane__translation-text,
      .pane__sentence-translation-text {
        margin: 0;
        font-size: 0.9rem;
        line-height: 1.55;
      }

      .pane__translation-attribution,
      .pane__sentence-translation-attribution {
        display: block;
        margin-block-start: 0.2rem;
        font-size: 0.7rem;
        color: var(--text-muted, color-mix(in srgb, CanvasText 55%, Canvas));
      }

      /* ── Why it matters ─────────────────────────────────────────────────── */
      .pane__why-it-matters {
        margin: 0;
        padding: 0.6rem 0.75rem;
        border-inline-start: 3px solid color-mix(in oklch, var(--detail-accent, ${ref}) 55%, Canvas);
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 6%, Canvas);
        border-radius: 0 0.4rem 0.4rem 0;
      }

      .pane__why-it-matters-text {
        margin: 0;
        font-size: 0.85rem;
        line-height: 1.65;
        color: var(--text);
      }

      /* ── Field list (dl/dt/dd) ──────────────────────────────────────────── */
      .pane__fields {
        margin: 0;
        display: flex;
        flex-direction: column;
        border-block-start: 1px solid var(--border);
      }

      .pane__field {
        display: grid;
        grid-template-columns: 9rem 1fr;
        gap: 0.4rem;
        align-items: baseline;
        padding-block: 0.45rem;
        border-block-end: 1px solid var(--border);
      }

      .pane__field-label {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--muted);
        line-height: 1.4;
      }

      .pane__field-value {
        font-size: 0.875rem;
        line-height: 1.5;
        margin: 0;
        overflow-wrap: break-word;
      }

      /* ── Audio action row ───────────────────────────────────────────────── */
      .pane__audio-row {
        display: flex;
        gap: 0.5rem;
        flex-wrap: wrap;
        padding-block-start: 0.25rem;
      }

      .pane__audio-btn {
        display: inline-flex;
        align-items: center;
        gap: 0.3rem;
        background: transparent;
        border: 1px solid var(--border-input);
        border-radius: 999px;
        padding: 0.3rem 0.75rem;
        font: inherit;
        font-size: 0.8rem;
        color: var(--text);
        cursor: pointer;
        min-block-size: 2.75rem;
        white-space: nowrap;
        transition: background 0.1s ease, border-color 0.1s ease;
      }
      .pane__audio-btn:hover {
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 10%, Canvas);
        border-color: color-mix(in oklch, var(--detail-accent, ${ref}) 45%, Canvas);
      }
      .pane__audio-btn:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: 2px;
      }
      @media (prefers-reduced-motion: reduce) {
        .pane__audio-btn { transition: none; }
      }

      /* ── Origins ────────────────────────────────────────────────────────── */
      .pane__origin-text {
        margin: 0;
        font-size: 0.9rem;
        line-height: 1.7;
        font-style: italic;
        color: var(--text);
      }

      .pane__source-citation {
        display: block;
        font-size: 0.75rem;
        font-style: normal;
        font-weight: 600;
        color: var(--muted);
        letter-spacing: 0.02em;
        padding-block-start: 0.35rem;
        border-block-start: 1px solid var(--border);
        margin-block-start: 0.25rem;
      }

      .pane__etymology--ruled {
        margin-block-start: 0.75rem;
        padding-block-start: 0.75rem;
        border-block-start: 1px solid var(--border);
      }

      .pane__etymology-summary {
        margin: 0.25rem 0 0;
        font-size: 0.9rem;
        line-height: 1.7;
        color: var(--text);
      }

      .pane__etymology-meta {
        margin: 0.6rem 0 0;
        display: grid;
        grid-template-columns: 7rem 1fr;
        gap: 0.25rem 0.5rem;
        align-items: baseline;
      }

      .pane__etymology-term {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--muted);
        margin: 0;
      }

      .pane__etymology-def {
        font-size: 0.85rem;
        line-height: 1.5;
        margin: 0;
        overflow-wrap: break-word;
      }

      /* ── In Context ─────────────────────────────────────────────────────── */
      .pane__context-sentence {
        margin: 0;
        font-size: 1rem;
        line-height: 1.75;
        overflow-wrap: break-word;
      }

      /*
       * Highlight: background tint + underline so it works without color.
       * mark resets UA yellow background; we supply our own color-mix tint.
       */
      .context-highlight {
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 24%, Canvas);
        color: inherit;
        border-radius: 0.2em;
        padding-inline: 0.1em;
        text-decoration: underline;
        text-decoration-thickness: 1px;
        text-underline-offset: 0.2em;
        text-decoration-color: color-mix(in oklch, var(--detail-accent, ${ref}) 55%, CanvasText);
      }

      /* ── Related — section headings ─────────────────────────────────────── */
      .pane__subsection + .pane__subsection {
        padding-block-start: 0.75rem;
        border-block-start: 1px solid var(--border);
        margin-block-start: 0.25rem;
      }

      .pane__section-heading {
        margin: 0 0 0.5rem 0;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--muted);
      }

      /* ── Variant list ────────────────────────────────────────────────────── */
      .pane__variant-list,
      .pane__confusable-list {
        list-style: none;
        margin: 0;
        padding: 0;
        display: flex;
        flex-direction: column;
      }

      .pane__variant-item {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        padding-block: 0.35rem;
        border-block-end: 1px solid var(--border);
        font-size: 0.875rem;
        line-height: 1.4;
      }
      .pane__variant-item:last-child { border-block-end: none; }

      /* Flex row within each variant item: text + optional match-type badge */
      .pane__variant-surface-row {
        display: flex;
        align-items: baseline;
        gap: 0.35rem;
        flex-wrap: wrap;
        flex: 1 1 0;
        min-inline-size: 0;
      }

      .pane__variant-text {
        overflow-wrap: break-word;
      }

      .pane__variant-item--canonical .pane__variant-text {
        font-weight: 600;
      }

      .pane__canonical-star {
        font-size: 0.75rem;
        flex-shrink: 0;
        color: color-mix(in oklch, var(--detail-accent, ${ref}) 75%, CanvasText);
      }

      .pane__variant-note {
        display: block;
        font-size: 0.75rem;
        color: var(--muted);
        font-style: italic;
        inline-size: 100%;
        margin-block-start: 0.15rem;
      }

      .pane__confusable-item {
        padding-block: 0.2rem;
      }

      .pane__confusable-link {
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
        inline-size: 100%;
        background: none;
        border: none;
        border-radius: 0.3rem;
        padding: 0.3rem 0.4rem;
        text-align: start;
        cursor: pointer;
        color: inherit;
        transition: background 0.12s;
      }
      .pane__confusable-link:hover,
      .pane__confusable-link:focus-visible {
        background: color-mix(in oklch, var(--accent) 10%, Canvas);
        outline: 2px solid var(--accent);
        outline-offset: -2px;
      }

      .pane__confusable-canonical {
        font-size: 0.875rem;
        font-weight: 500;
        overflow-wrap: break-word;
        color: var(--accent);
      }

      .pane__confusable-meaning {
        font-size: 0.75rem;
        color: var(--muted);
        font-style: italic;
        line-height: 1.4;
        overflow-wrap: break-word;
      }

      /* Within-family confusable forms (confusable_not_same variants) */
      .pane__confusable-form-item {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        padding-block: 0.4rem;
        border-block-end: 1px solid var(--border);
        font-size: 0.875rem;
      }
      .pane__confusable-form-item:last-child { border-block-end: none; }

      .pane__confusable-form-surface {
        font-weight: 500;
        overflow-wrap: break-word;
      }

      .pane__confusable-form-note {
        margin: 0;
        font-size: 0.75rem;
        color: var(--muted);
        font-style: italic;
        line-height: 1.5;
      }

      /* ── Footer ──────────────────────────────────────────────────────────── */
      .pane__footer {
        flex-shrink: 0;
        padding: 0.65rem 0.75rem;
        border-block-start: 1px solid var(--border);
        display: flex;
        justify-content: flex-end;
        align-items: center;
        gap: 0.5rem;
      }

      .pane__study-btn {
        background: var(--accent);
        color: white;
        border: none;
        border-radius: 999px;
        padding-inline: 1rem;
        padding-block: 0.5rem;
        font: inherit;
        font-size: 0.875rem;
        font-weight: 500;
        cursor: pointer;
        min-block-size: 2.75rem;
        transition: background 0.12s ease;
      }
      .pane__study-btn:hover {
        background: color-mix(in srgb, var(--accent) 85%, black);
      }
      .pane__study-btn:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: 3px;
      }
      .pane__study-btn--inline {
        align-self: flex-start;
      }

      /* ── Term memory-state chip (practice tab) ──────────────────────────── */
      .pane__term-state {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.3rem 0.6rem;
        border-radius: 0.35rem;
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 8%, Canvas);
        border: 1px solid color-mix(in oklch, var(--detail-accent, ${ref}) 20%, Canvas);
        font-size: 0.8125rem;
      }
      .pane__term-state-badge { font-weight: 500; }
      .pane__term-state-next {
        color: var(--muted, color-mix(in srgb, CanvasText 55%, Canvas));
      }
      .pane__term-state[data-bucket="new"],
      .pane__term-state[data-bucket="learning"] {
        background: color-mix(in oklch, oklch(0.55 0.18 145) 8%, Canvas);
        border-color: color-mix(in oklch, oklch(0.55 0.18 145) 25%, Canvas);
      }
      .pane__term-state[data-bucket="due"],
      .pane__term-state[data-bucket="fading"] {
        background: color-mix(in oklch, oklch(0.72 0.18 55) 8%, Canvas);
        border-color: color-mix(in oklch, oklch(0.72 0.18 55) 25%, Canvas);
      }
      .pane__term-state[data-bucket="strong"] {
        background: color-mix(in oklch, oklch(0.55 0.18 145) 8%, Canvas);
        border-color: color-mix(in oklch, oklch(0.55 0.18 145) 25%, Canvas);
      }

      .pane__muted {
        margin: 0;
        color: var(--muted);
        font-size: 0.8125rem;
        line-height: 1.55;
      }
      @media (prefers-reduced-motion: reduce) {
        .pane__study-btn { transition: none; }
      }

      /* ── Share button ────────────────────────────────────────────────────── */
      .pane__share {
        flex-shrink: 0;
        background: transparent;
        border: none;
        padding: 0;
        min-block-size: 2.75rem;
        min-inline-size: 2.75rem;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font: inherit;
        font-size: 1rem;
        color: var(--muted);
        cursor: pointer;
        border-radius: 0.4rem;
      }
      .pane__share:hover { color: var(--text); background: var(--border); }
      .pane__share:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: 2px;
      }

      .pane__share-hint {
        font-size: 0.7rem;
        color: var(--success);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        max-inline-size: 10rem;
        flex-shrink: 1;
      }

      /* ── Note section ────────────────────────────────────────────────────── */
      .pane__note-section {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
        border-block-start: 1px solid var(--border);
        padding-block-start: 0.75rem;
      }

      .pane__note-label {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--muted);
        margin: 0;
      }

      .pane__note-input {
        font: inherit;
        font-size: 0.875rem;
        line-height: 1.5;
        resize: vertical;
        min-block-size: 4.5rem;
        border: 1px solid var(--border-input);
        border-radius: 0.4rem;
        padding: 0.4rem 0.5rem;
        background: var(--surface);
        color: var(--text);
      }
      .pane__note-input:focus {
        outline: 3px solid var(--accent);
        outline-offset: 1px;
        border-color: transparent;
      }

      .pane__note-actions {
        display: flex;
        gap: 0.4rem;
      }

      .pane__note-save,
      .pane__note-clear {
        background: transparent;
        border: 1px solid var(--border-input);
        border-radius: 999px;
        padding: 0.25rem 0.65rem;
        font: inherit;
        font-size: 0.8rem;
        cursor: pointer;
        color: var(--text);
        min-block-size: 2.75rem;
        transition: background 0.1s ease, color 0.1s ease, border-color 0.1s ease;
      }
      .pane__note-save:hover  { background: var(--border); }
      .pane__note-clear:hover {
        background: color-mix(in srgb, var(--error) 10%, Canvas);
        color: var(--error);
        border-color: color-mix(in srgb, var(--error) 40%, Canvas);
      }
      .pane__note-save:focus-visible,
      .pane__note-clear:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: 2px;
      }
      @media (prefers-reduced-motion: reduce) {
        .pane__note-save, .pane__note-clear { transition: none; }
      }

      /* ── Screen-reader-only utility ─────────────────────────────────────────── */
      .pane__sr-only {
        position: absolute;
        inline-size: 1px; block-size: 1px;
        padding: 0; margin: -1px;
        overflow: hidden; clip-path: inset(50%);
        white-space: nowrap; border: 0;
      }

      /* ── Morphology axes (Form tab) ──────────────────────────────────────────── */
      .pane__axes-list {
        margin: 0;
        display: flex;
        flex-direction: column;
        border-block-start: 1px solid var(--border);
      }

      .pane__axis-row {
        display: grid;
        grid-template-columns: 8rem 1fr;
        gap: 0.4rem;
        align-items: baseline;
        padding-block: 0.4rem;
        border-block-end: 1px solid var(--border);
      }

      .pane__axis-label {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--muted);
        line-height: 1.4;
      }

      .pane__axis-value {
        font-size: 0.875rem;
        line-height: 1.5;
        margin: 0;
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
      }

      .pane__axis-gloss {
        font-size: 0.75rem;
        color: var(--muted);
        font-style: italic;
        line-height: 1.4;
      }

      /* ── Contrast cards (Form tab) ───────────────────────────────────────────── */
      .pane__contrast-card {
        border: 1px solid color-mix(in oklch, oklch(0.72 0.18 55) 30%, Canvas);
        background: color-mix(in oklch, oklch(0.72 0.18 55) 6%, Canvas);
        border-radius: 0.5rem;
        padding: 0.65rem 0.75rem;
        display: flex;
        flex-direction: column;
        gap: 0.35rem;
      }

      .pane__contrast-forms {
        margin: 0;
        font-size: 0.9375rem;
        font-weight: 600;
        line-height: 1.4;
        overflow-wrap: break-word;
      }

      .pane__contrast-sep {
        font-weight: 400;
        font-size: 0.8rem;
        color: var(--muted);
        margin-inline: 0.25rem;
      }

      .pane__contrast-note {
        margin: 0;
        font-size: 0.875rem;
        line-height: 1.55;
        color: var(--text);
      }

      .pane__contrast-example {
        margin: 0;
        font-size: 0.8125rem;
        line-height: 1.6;
        color: var(--muted);
        font-style: italic;
        overflow-wrap: break-word;
      }

      /* ── Paradigm table (Paradigm tab) ───────────────────────────────────────── */
      .pane__paradigm-table-wrap {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
        border-radius: 0.4rem;
        border: 1px solid var(--border);
      }

      .pane__paradigm-table {
        border-collapse: collapse;
        inline-size: 100%;
        font-size: 0.875rem;
        line-height: 1.5;
      }

      .pane__paradigm-table th,
      .pane__paradigm-table td {
        padding: 0.4rem 0.6rem;
        border: 1px solid var(--border);
        vertical-align: top;
      }

      .pane__paradigm-colhead,
      .pane__paradigm-rowhead {
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--muted);
        background: color-mix(in srgb, CanvasText 3%, Canvas);
        white-space: nowrap;
      }

      .pane__paradigm-cell {
        text-align: center;
      }

      .pane__paradigm-cell--current {
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 16%, Canvas);
        font-weight: 600;
        outline: 2px solid color-mix(in oklch, var(--detail-accent, ${ref}) 60%, Canvas);
        outline-offset: -2px;
      }

      .pane__paradigm-cell--empty {
        color: var(--muted);
        text-align: center;
      }

      .pane__paradigm-form {
        display: block;
        overflow-wrap: break-word;
      }

      .pane__paradigm-gloss {
        display: block;
        font-size: 0.7rem;
        color: var(--muted);
        font-style: italic;
        margin-block-start: 0.1rem;
      }

      .pane__paradigm-current-label {
        font-size: 0.6rem;
        color: color-mix(in oklch, var(--detail-accent, ${ref}) 75%, CanvasText);
        margin-inline-start: 0.2em;
        vertical-align: middle;
      }

      .pane__paradigm-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(6rem, 1fr));
        gap: 0.4rem;
      }

      .pane__paradigm-item {
        border: 1px solid var(--border);
        border-radius: 0.3rem;
        padding: 0.35rem 0.5rem;
        display: flex;
        flex-direction: column;
        gap: 0.1rem;
        text-align: center;
      }

      .pane__paradigm-item--current {
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 16%, Canvas);
        border-color: color-mix(in oklch, var(--detail-accent, ${ref}) 60%, Canvas);
        font-weight: 600;
      }

      /* ── Equivalent constructions (Equivalents tab) ──────────────────────────── */
      .pane__equiv-card {
        border: 1px solid var(--border);
        border-inline-start: 3px solid color-mix(in oklch, var(--detail-accent, ${ref}) 60%, Canvas);
        border-radius: 0 0.4rem 0.4rem 0;
        padding: 0.55rem 0.75rem;
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 4%, Canvas);
      }

      .pane__equiv-construction {
        margin: 0;
        font-size: 1rem;
        font-weight: 600;
        line-height: 1.4;
        overflow-wrap: break-word;
      }

      .pane__equiv-note {
        margin: 0;
        font-size: 0.8125rem;
        line-height: 1.55;
        color: var(--muted);
      }

      .pane__equiv-register {
        display: inline-flex;
        align-items: center;
        font-size: 0.6rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        border-radius: 999px;
        padding: 0.1rem 0.4rem;
        border: 1px solid;
        align-self: flex-start;
      }

      .pane__equiv-register--formal {
        background: color-mix(in oklch, oklch(0.55 0.18 240) 10%, Canvas);
        color: color-mix(in oklch, oklch(0.55 0.18 240) 80%, CanvasText);
        border-color: color-mix(in oklch, oklch(0.55 0.18 240) 30%, Canvas);
      }
      .pane__equiv-register--informal,
      .pane__equiv-register--colloquial {
        background: color-mix(in oklch, oklch(0.72 0.18 55) 10%, Canvas);
        color: color-mix(in oklch, oklch(0.72 0.18 55) 80%, CanvasText);
        border-color: color-mix(in oklch, oklch(0.72 0.18 55) 30%, Canvas);
      }

      /* ── Nuance pairs (Nuance tab) ───────────────────────────────────────────── */
      .pane__nuance-intro {
        margin-block-end: 0.75rem;
      }

      .pane__nuance-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem;
        align-items: center;
        margin-block-end: 0.5rem;
      }

      .pane__nuance-dim-badge {
        display: inline-flex;
        align-items: center;
        font-size: 0.625rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        padding: 0.15rem 0.5rem;
        border-radius: 999px;
        background: color-mix(in oklch, var(--detail-accent, oklch(0.50 0.20 20)) 12%, Canvas);
        color: color-mix(in oklch, var(--detail-accent, oklch(0.50 0.20 20)) 85%, CanvasText);
        border: 1px solid color-mix(in oklch, var(--detail-accent, oklch(0.50 0.20 20)) 25%, Canvas);
      }

      .pane__nuance-cefr {
        font-size: 0.625rem;
        font-weight: 600;
        color: var(--muted);
        border: 1px solid var(--border);
        border-radius: 999px;
        padding: 0.1rem 0.4rem;
      }

      .pane__nuance-pair {
        border: 1px solid var(--border);
        border-radius: 0.5rem;
        padding: 0.75rem;
        margin-block: 0.75rem;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        background: color-mix(in oklch, Canvas 96%, var(--detail-accent, oklch(0.50 0.20 20)));
      }

      .pane__nuance-question {
        margin: 0;
        font-size: 0.9rem;
        font-weight: 600;
        line-height: 1.45;
      }

      .pane__nuance-choices {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.5rem;
      }

      @media (max-width: 380px) {
        .pane__nuance-choices { grid-template-columns: 1fr; }
      }

      .pane__nuance-choice {
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
        padding: 0.6rem 0.75rem;
        border: 1.5px solid var(--border);
        border-radius: 0.4rem;
        background: Canvas;
        cursor: pointer;
        text-align: start;
        transition: border-color 0.12s, background 0.12s;
        min-block-size: 2.75rem;
        color: inherit;
      }

      .pane__nuance-choice:hover:not(:disabled) {
        border-color: color-mix(in oklch, var(--detail-accent, oklch(0.50 0.20 20)) 55%, Canvas);
        background: color-mix(in oklch, var(--detail-accent, oklch(0.50 0.20 20)) 5%, Canvas);
      }

      .pane__nuance-choice:focus-visible {
        outline: 2px solid var(--detail-accent, oklch(0.50 0.20 20));
        outline-offset: 2px;
      }

      .pane__nuance-choice--correct {
        border-color: oklch(0.52 0.18 142);
        background: color-mix(in oklch, oklch(0.52 0.18 142) 8%, Canvas);
      }

      .pane__nuance-choice--wrong {
        border-color: oklch(0.52 0.20 25);
        background: color-mix(in oklch, oklch(0.52 0.20 25) 6%, Canvas);
        opacity: 0.75;
      }

      .pane__nuance-choice-label {
        font-size: 0.6rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: var(--muted);
        align-self: flex-start;
      }

      .pane__nuance-sentence {
        font-size: 0.875rem;
        line-height: 1.5;
        overflow-wrap: break-word;
      }

      .pane__nuance-hint {
        font-size: 0.7rem;
        font-style: italic;
        color: var(--muted);
        line-height: 1.3;
      }

      .pane__nuance-reveal {
        margin-block-start: 0.25rem;
        padding: 0.6rem 0.75rem;
        border-inline-start: 3px solid oklch(0.52 0.18 142);
        background: color-mix(in oklch, oklch(0.52 0.18 142) 5%, Canvas);
        border-radius: 0 0.35rem 0.35rem 0;
      }

      .pane__nuance-explanation {
        margin: 0;
        font-size: 0.85rem;
        line-height: 1.6;
      }

      .pane__nuance-feedback {
        margin: 0;
        font-size: 0.8125rem;
        min-block-size: 1.2em;
        color: var(--muted);
      }

      /* ── Context vocabulary (Memory tab) ─────────────────────────────────────── */
      .pane__vocab-card {
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
        padding-block: 0.4rem;
        border-block-end: 1px solid var(--border);
      }
      .pane__vocab-card:last-child { border-block-end: none; }

      .pane__vocab-head {
        display: flex;
        align-items: baseline;
        gap: 0.4rem;
        flex-wrap: wrap;
      }

      .pane__vocab-form {
        font-size: 0.9375rem;
        font-weight: 600;
        line-height: 1.4;
        overflow-wrap: break-word;
      }

      .pane__vocab-lemma {
        font-size: 0.8125rem;
        font-weight: 400;
        color: var(--muted);
      }

      .pane__vocab-freq {
        font-size: 0.7rem;
        color: color-mix(in oklch, oklch(0.72 0.18 55) 80%, CanvasText);
        margin-inline-start: 0.1em;
        vertical-align: text-top;
      }

      .pane__vocab-pos {
        font-size: 0.625rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: color-mix(in oklch, var(--detail-accent, ${ref}) 80%, CanvasText);
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 10%, Canvas);
        border: 1px solid color-mix(in oklch, var(--detail-accent, ${ref}) 25%, Canvas);
        border-radius: 999px;
        padding: 0.1rem 0.35rem;
        white-space: nowrap;
        flex-shrink: 0;
      }

      .pane__vocab-gloss {
        margin: 0;
        font-size: 0.8125rem;
        line-height: 1.55;
        color: var(--muted);
      }

      /* ── Practice check cards ──────────────────────────────────────────────── */
      .pane__check {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        padding: 0.6rem 0.65rem;
        border: 1px solid var(--border);
        border-radius: 0.45rem;
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 3%, Canvas);
      }

      .pane__check-prompt {
        margin: 0;
        font-size: 0.875rem;
        line-height: 1.55;
      }

      .pane__check-options {
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
      }

      .pane__check-option {
        background: transparent;
        border: 1px solid var(--border-input);
        border-radius: 0.4rem;
        padding: 0.35rem 0.65rem;
        font: inherit;
        font-size: 0.8125rem;
        color: var(--text);
        cursor: pointer;
        text-align: start;
        min-block-size: 2.75rem;
        transition: background 0.1s ease, border-color 0.1s ease;
      }
      .pane__check-option:hover:not(:disabled) {
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 10%, Canvas);
        border-color: color-mix(in oklch, var(--detail-accent, ${ref}) 45%, Canvas);
      }
      .pane__check-option:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: 2px;
      }
      .pane__check-option:disabled { opacity: 0.65; cursor: not-allowed; }
      @media (prefers-reduced-motion: reduce) {
        .pane__check-option { transition: none; }
      }

      /* ── Typed form (input + submit inline) ──────────────────────────────── */
      .pane__typed-form {
        display: flex;
        gap: 0.4rem;
        align-items: stretch;
      }

      .pane__typed-input {
        flex: 1 1 0;
        font: inherit;
        font-size: 0.875rem;
        border: 1px solid var(--border-input);
        border-radius: 0.4rem;
        padding: 0.35rem 0.5rem;
        background: var(--surface);
        color: var(--text);
        min-block-size: 2.75rem;
        min-inline-size: 0;
      }
      .pane__typed-input:focus {
        outline: 3px solid var(--accent);
        outline-offset: 1px;
        border-color: transparent;
      }

      .pane__typed-input--area {
        resize: vertical;
        min-block-size: 3.5rem;
        flex: none;
        inline-size: 100%;
        box-sizing: border-box;
      }

      /* ── Drill section grouping ──────────────────────────────────────────── */
      .pane__drill-section {
        display: flex;
        flex-direction: column;
        gap: 0.55rem;
        border-block-start: 1px solid var(--border);
        padding-block-start: 0.7rem;
        margin-block-start: 0.1rem;
      }

      .pane__drill-section-label {
        font-size: 0.625rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.09em;
        color: color-mix(in oklch, var(--detail-accent, ${ref}) 80%, CanvasText);
        margin: 0;
      }

      /* ── Constrained free production ─────────────────────────────────────── */
      .pane__production-area {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
      }

      .pane__reveal-btn {
        align-self: flex-start;
        background: transparent;
        border: 1px solid var(--border-input);
        border-radius: 999px;
        padding: 0.3rem 0.75rem;
        font: inherit;
        font-size: 0.8rem;
        color: var(--text);
        cursor: pointer;
        min-block-size: 2.75rem;
        transition: background 0.1s ease, border-color 0.1s ease;
      }
      .pane__reveal-btn:hover:not(:disabled) {
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 10%, Canvas);
        border-color: color-mix(in oklch, var(--detail-accent, ${ref}) 45%, Canvas);
      }
      .pane__reveal-btn:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: 2px;
      }
      .pane__reveal-btn:disabled { opacity: 0.5; cursor: not-allowed; }
      @media (prefers-reduced-motion: reduce) {
        .pane__reveal-btn { transition: none; }
      }

      .pane__example-reveal {
        display: flex;
        flex-direction: column;
        gap: 0.4rem;
        padding: 0.5rem 0.65rem;
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 6%, Canvas);
        border: 1px solid color-mix(in oklch, var(--detail-accent, ${ref}) 22%, Canvas);
        border-radius: 0.4rem;
      }

      /* ── Self-rate quality buttons ───────────────────────────────────────── */
      .pane__self-rate {
        display: flex;
        gap: 0.3rem;
        flex-wrap: wrap;
      }

      .pane__self-rate-btn {
        flex: 1 1 auto;
        min-inline-size: 3rem;
        background: transparent;
        border: 1px solid var(--border-input);
        border-radius: 0.4rem;
        padding: 0.3rem 0.4rem;
        font: inherit;
        font-size: 0.75rem;
        font-weight: 600;
        cursor: pointer;
        min-block-size: 2.75rem;
        text-align: center;
        transition: background 0.1s ease, border-color 0.1s ease, color 0.1s ease;
      }
      .pane__self-rate-btn:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: 2px;
      }
      .pane__self-rate-btn:disabled { opacity: 0.5; cursor: not-allowed; }

      .pane__self-rate-btn--again {
        color: oklch(0.55 0.20 29);
        border-color: color-mix(in oklch, oklch(0.55 0.20 29) 35%, Canvas);
      }
      .pane__self-rate-btn--again:hover:not(:disabled) {
        background: color-mix(in oklch, oklch(0.55 0.20 29) 10%, Canvas);
      }
      .pane__self-rate-btn--hard {
        color: oklch(0.62 0.16 55);
        border-color: color-mix(in oklch, oklch(0.62 0.16 55) 35%, Canvas);
      }
      .pane__self-rate-btn--hard:hover:not(:disabled) {
        background: color-mix(in oklch, oklch(0.62 0.16 55) 10%, Canvas);
      }
      .pane__self-rate-btn--good {
        color: oklch(0.55 0.18 145);
        border-color: color-mix(in oklch, oklch(0.55 0.18 145) 35%, Canvas);
      }
      .pane__self-rate-btn--good:hover:not(:disabled) {
        background: color-mix(in oklch, oklch(0.55 0.18 145) 10%, Canvas);
      }
      .pane__self-rate-btn--easy {
        color: oklch(0.55 0.18 240);
        border-color: color-mix(in oklch, oklch(0.55 0.18 240) 35%, Canvas);
      }
      .pane__self-rate-btn--easy:hover:not(:disabled) {
        background: color-mix(in oklch, oklch(0.55 0.18 240) 10%, Canvas);
      }
      @media (prefers-reduced-motion: reduce) {
        .pane__self-rate-btn { transition: none; }
      }

      /* ── Review tab ──────────────────────────────────────────────────────────── */
      .pane__review-status { }

      .pane__stage-badge {
        display: inline-block;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.04em;
        padding: 0.2em 0.65em;
        border-radius: 999px;
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 12%, Canvas);
        border: 1px solid color-mix(in oklch, var(--detail-accent, ${ref}) 30%, Canvas);
        color: var(--text);
        margin-block-end: 0.4rem;
      }

      .pane__stage-steps {
        list-style: none;
        padding: 0;
        margin: 0.6rem 0 0;
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
      }

      .pane__stage-step {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.8rem;
        color: var(--muted);
        padding: 0.15rem 0;
      }

      .pane__stage-step--done { color: oklch(0.55 0.15 145); }

      .pane__stage-step--current {
        color: var(--text);
        font-weight: 600;
      }

      .pane__stage-marker {
        font-size: 0.7rem;
        inline-size: 1.1em;
        flex-shrink: 0;
      }

      .pane__mastery-bar {
        block-size: 5px;
        background: color-mix(in oklch, CanvasText 12%, Canvas);
        border-radius: 999px;
        overflow: hidden;
        margin-block: 0.5rem;
      }

      .pane__mastery-bar-fill {
        block-size: 100%;
        background: var(--detail-accent, ${ref});
        border-radius: 999px;
        transition: inline-size 0.4s ease;
      }

      @media (prefers-reduced-motion: reduce) {
        .pane__mastery-bar-fill { transition: none; }
      }

      .pane__confusion-list {
        list-style: none;
        padding: 0;
        margin: 0.4rem 0 0;
        display: flex;
        flex-direction: column;
        gap: 0.3rem;
      }

      .pane__confusion-item {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.85rem;
        padding: 0.3rem 0.5rem;
        border-radius: 0.35rem;
        background: color-mix(in oklch, oklch(0.55 0.20 29) 6%, Canvas);
        border: 1px solid color-mix(in oklch, oklch(0.55 0.20 29) 18%, Canvas);
      }

      .pane__confusion-form {
        flex: 1;
        font-weight: 500;
      }

      .pane__confusion-count {
        font-size: 0.75rem;
        color: var(--muted);
        font-variant-numeric: tabular-nums;
      }

      @media (forced-colors: active) {
        .pane__stage-badge { border: 1px solid ButtonText; }
        .pane__mastery-bar-fill { forced-color-adjust: none; background: Highlight; }
        .pane__confusion-item { border: 1px solid ButtonText; }
      }

      /* ── Concept help button (inline "?" next to field values) ─────────── */
      .pane__concept-help {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        inline-size: 1.25rem;
        block-size: 1.25rem;
        border-radius: 50%;
        border: 1px solid var(--border-input);
        background: transparent;
        color: var(--muted);
        font: 600 0.65rem/1 inherit;
        cursor: pointer;
        margin-inline-start: 0.35rem;
        vertical-align: middle;
        flex-shrink: 0;
        transition: background 0.1s ease, color 0.1s ease, border-color 0.1s ease;
      }
      .pane__concept-help:hover {
        background: color-mix(in oklch, var(--detail-accent, ${ref}) 12%, Canvas);
        border-color: color-mix(in oklch, var(--detail-accent, ${ref}) 50%, Canvas);
        color: var(--text);
      }
      .pane__concept-help:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: 2px;
      }
      @media (prefers-reduced-motion: reduce) {
        .pane__concept-help { transition: none; }
      }
      @media (forced-colors: active) {
        .pane__concept-help { border: 1px solid ButtonText; color: ButtonText; background: ButtonFace; }
      }

      /* ── Concept help dialog (floating over the pane body) ──────────────── */
      .pane__concept-dialog {
        position: fixed;
        inset: 0;
        z-index: 100;
        background: color-mix(in oklch, CanvasText 30%, transparent);
        display: flex;
        align-items: flex-start;
        justify-content: center;
        padding-block-start: 4rem;
        padding-inline: 0.75rem;
      }
      .pane__concept-dialog[hidden] {
        display: none;
      }
      .pane__concept-dialog-inner {
        background: var(--surface, Canvas);
        border: 1px solid var(--border);
        border-radius: 0.75rem;
        box-shadow: 0 8px 24px color-mix(in oklch, Canvas 10%, transparent);
        inline-size: 100%;
        max-inline-size: 28rem;
        max-block-size: 70vh;
        overflow-y: auto;
        display: flex;
        flex-direction: column;
      }
      .pane__concept-dialog-header {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.85rem 1rem 0.6rem;
        border-block-end: 1px solid var(--border);
        position: sticky;
        inset-block-start: 0;
        background: var(--surface, Canvas);
        z-index: 1;
      }
      .pane__concept-dialog-title {
        flex: 1;
        margin: 0;
        font-size: 0.9375rem;
        font-weight: 700;
        line-height: 1.3;
        overflow-wrap: break-word;
      }
      .pane__concept-dialog-close {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        inline-size: 2rem;
        block-size: 2rem;
        border-radius: 50%;
        border: none;
        background: transparent;
        cursor: pointer;
        color: var(--muted);
        font-size: 0.9rem;
        flex-shrink: 0;
        transition: background 0.1s ease, color 0.1s ease;
      }
      .pane__concept-dialog-close:hover {
        background: color-mix(in oklch, var(--muted) 12%, Canvas);
        color: var(--text);
      }
      .pane__concept-dialog-close:focus-visible {
        outline: 3px solid var(--accent);
        outline-offset: 2px;
      }
      .pane__concept-dialog-body {
        padding: 0.75rem 1rem 1rem;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }
      .pane__concept-def {
        margin: 0;
        font-size: 0.875rem;
        font-weight: 600;
        line-height: 1.5;
      }
      .pane__concept-body {
        margin: 0;
        font-size: 0.875rem;
        line-height: 1.6;
      }
      .pane__concept-note {
        margin: 0;
        font-size: 0.8125rem;
        line-height: 1.55;
        color: var(--muted);
        font-style: italic;
      }
      .pane__concept-note--l1 {
        color: var(--text);
        font-style: normal;
        border-inline-start: 2px solid color-mix(in oklch, var(--detail-accent, ${ref}) 40%, Canvas);
        padding-inline-start: 0.5rem;
      }
      .pane__concept-section-label {
        margin: 0.25rem 0 0.1rem;
        font-size: 0.7rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.07em;
        color: var(--muted);
      }
      .pane__concept-examples,
      .pane__concept-related {
        margin: 0;
        padding-inline-start: 1.25rem;
        display: flex;
        flex-direction: column;
        gap: 0.2rem;
      }
      .pane__concept-example-item,
      .pane__concept-related li {
        font-size: 0.8125rem;
        line-height: 1.5;
      }
      @media (forced-colors: active) {
        .pane__concept-dialog-inner { border: 2px solid ButtonText; }
        .pane__concept-dialog-close { border: 1px solid ButtonText; }
      }
    `
  }
}

customElements.define('mnemosyne-detail-pane', MnemosyneDetailPane)
