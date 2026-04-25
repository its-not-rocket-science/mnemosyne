/**
 * mnemosyne-detail-pane.js
 *
 * Right-side concordance panel. Opens when a learnable-object pill is clicked;
 * shows four tab sections (Explanation / Origins / In Context / Related) and
 * audio action buttons. "Study drills" delegates to the existing modal.
 *
 * Public API
 * ──────────
 *   detailPane.show({ lesson, sentenceText, language, dir, ttsTag, caps,
 *                     onSpeak, onStudy })
 *   detailPane.hide()
 *
 * Events dispatched (composed, bubbles)
 * ──────────────────────────────────────
 *   pane-close   user dismissed the pane (close button or Escape)
 *   pane-study   user clicked "Study drills" (open modal)
 */

// ── Type metadata (mirrors mnemosyne-pill.js) ─────────────────────────────────
const TYPE_META = {
  vocabulary:      { icon: '📗', label: 'Vocabulary',     ref: 'oklch(0.50 0.20 142)' },
  conjugation:     { icon: '🔧', label: 'Verb',            ref: 'oklch(0.50 0.20 240)' },
  agreement:       { icon: '🧩', label: 'Agreement',       ref: 'oklch(0.50 0.15  50)' },
  idiom:           { icon: '💬', label: 'Idiom',            ref: 'oklch(0.50 0.20 300)' },
  grammar:         { icon: '📐', label: 'Grammar',          ref: 'oklch(0.50 0.15  90)' },
  nuance:          { icon: '🎭', label: 'Nuance',           ref: 'oklch(0.50 0.20  20)' },
  script:          { icon: '✍️', label: 'Script',          ref: 'oklch(0.50 0.18 200)' },
  transliteration: { icon: '🔤', label: 'Transliteration', ref: 'oklch(0.50 0.15 170)' },
  phrase_family:   { icon: '🔗', label: 'Phrase family',   ref: 'oklch(0.50 0.20 330)' },
}

// Field labels shown in dedicated UI sections — suppress from the generic field list.
const SUPPRESS_IN_EXPLANATION = new Set([
  'known variants', 'confusable with', 'origin', 'variant note',
  // phrase_family fields rendered in dedicated sections:
  'match type', 'note', 'source', 'why it matters',
])

// User-friendly labels and CSS modifier classes for MatchType values.
const MATCH_TYPE_META = {
  exact:                { label: 'Canonical form',              cls: 'canonical' },
  orthographic_variant: { label: 'Spelling variant',            cls: 'variant'   },
  modernized_variant:   { label: 'Modernised form',             cls: 'variant'   },
  inflectional_variant: { label: 'Inflectional variant',        cls: 'variant'   },
  misquotation:         { label: 'Common misquote',             cls: 'warning'   },
  blend:                { label: 'Blend / corruption',          cls: 'warning'   },
  allusion:             { label: 'Allusion',                    cls: 'allusion'  },
  confusable_not_same:  { label: 'Confusable \u2014 different meaning', cls: 'danger' },
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
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
  #config         = null   // { lesson, sentenceText, language, dir, ttsTag, caps, depth }
  #lastShowArgs   = null   // stored for updateDepth()
  #activeTab      = 0
  #visibleTabs    = []     // subset of ALL_TABS that are rendered
  #onSpeak        = null
  #onStudy        = null
  #previousFocus  = null
  #keydownHandler = null
  #snap           = 'half'
  #dragStartY     = 0
  #dragBaseY      = 0
  #dragActive     = false

  static ALL_TABS = [
    { id: 'explanation', label: 'Explanation', alwaysShow: true  },
    { id: 'origins',     label: 'Origins',     alwaysShow: false },
    { id: 'context',     label: 'In Context',  alwaysShow: true  },
    { id: 'related',     label: 'Related',     alwaysShow: false },
  ]

  constructor() {
    super()
    this.attachShadow({ mode: 'open' })
  }

  // ── Public API ──────────────────────────────────────────────────────────────

  show({ lesson, sentenceText, language, dir, ttsTag, caps, onSpeak, onStudy, depth }) {
    this.#lastShowArgs  = { lesson, sentenceText, language, dir, ttsTag, caps, onSpeak, onStudy, depth }
    this.#config        = { lesson, sentenceText, language, dir: dir ?? 'ltr', ttsTag, caps, depth: depth ?? 'scholar' }
    this.#onSpeak       = onSpeak ?? null
    this.#onStudy       = onStudy ?? null
    this.#activeTab     = 0
    this.#previousFocus = document.activeElement

    this.removeAttribute('inert')
    this._render()

    // Deferred to the next frame so the browser registers the pre-animation
    // state (translateY(110%) on mobile) before we apply data-open, allowing
    // the CSS transition to play.  Focus moves after the attribute lands so
    // screen readers announce the newly-visible pane.
    requestAnimationFrame(() => {
      this.setAttribute('data-open', '')
      this.#setSnap('half')
      this.shadowRoot.querySelector('[role="tab"]')?.focus()
    })

    // Close on Escape; trap Tab within the pane while open.
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

    const depthIdx = { basic: 0, intermediate: 1, scholar: 2 }[depth ?? 'scholar'] ?? 2

    // Which optional tabs have data?
    const hasOrigins = Boolean(ld.origin || ld.etymology || ld.source_text)
    const hasRelated = Boolean(
      (Array.isArray(ld.variants)         && ld.variants.length > 1) ||
      (Array.isArray(ld.confusables)      && ld.confusables.length > 0) ||
      (Array.isArray(ld.confusable_forms) && ld.confusable_forms.length > 0)
    )

    // Depth controls which tabs are exposed.
    // basic=0: Explanation only.  intermediate=1: + Origins + Context.  scholar=2: all.
    this.#visibleTabs = MnemosyneDetailPane.ALL_TABS.filter(t => {
      if (t.id === 'explanation') return true
      if (t.id === 'origins')     return depthIdx >= 1 && hasOrigins
      if (t.id === 'context')     return depthIdx >= 1
      if (t.id === 'related')     return depthIdx >= 2 && hasRelated
      return false
    })

    const matchedVariant = ld.matched_variant || lesson.label || ''
    const canonical      = ld.canonical_form  || ''
    const matchType      = ld.match_type || ''
    // Use match_type field (authoritative) rather than surface string comparison,
    // which fails for confusable_not_same where matched surface may equal canonical.
    const isNonCanonical = Boolean(matchType && matchType !== 'exact')

    // ── Assemble shadow DOM ──────────────────────────────────────────────────
    this.shadowRoot.innerHTML = /* html */`
      <style>${this._styles(meta)}</style>
      <aside class="pane" role="complementary" aria-labelledby="dp-heading">

        <div class="pane__drag-handle-area" aria-hidden="true">
          <div class="pane__drag-handle"></div>
        </div>

        <header class="pane__header">
          <div class="pane__badge" aria-hidden="true">${esc(meta.icon)} ${esc(meta.label)}</div>
          <h2 class="pane__title" id="dp-heading"></h2>
          <button class="pane__share" type="button" aria-label="Copy link to annotation">&#x1F517;</button>
          <span class="pane__share-hint" aria-live="polite" aria-atomic="true"></span>
          <button class="pane__close" type="button" aria-label="Close details panel">&#x2715;</button>
        </header>

        <div class="pane__tabs" role="tablist" aria-label="Details sections">
          ${this.#visibleTabs.map((tab, i) => /* html */`
            <button
              class="pane__tab${i === 0 ? ' pane__tab--active' : ''}"
              role="tab"
              id="dp-tab-${tab.id}"
              aria-selected="${i === 0}"
              aria-controls="dp-panel-${tab.id}"
              tabindex="${i === 0 ? 0 : -1}"
              type="button"
            >${esc(tab.label)}</button>
          `).join('')}
        </div>

        <div class="pane__body">
          ${this._htmlExplanationPanel(lesson, ld, matchedVariant, depthIdx)}
          ${depthIdx >= 1 && hasOrigins  ? this._htmlOriginsPanel(isNonCanonical, Boolean(ld.source_text), matchType) : ''}
          ${depthIdx >= 1               ? this._htmlContextPanel(language, dir) : ''}
          ${depthIdx >= 2 && hasRelated  ? this._htmlRelatedPanel(ld, canonical, isNonCanonical) : ''}
        </div>

        <footer class="pane__footer">
          <button class="pane__study-btn" type="button">Study drills &#x2192;</button>
        </footer>

        <slot name="now-playing"></slot>

      </aside>
    `

    // ── Populate text content safely (never via innerHTML) ──────────────────

    // Header title
    const titleEl = this.shadowRoot.querySelector('#dp-heading')
    if (titleEl) titleEl.textContent = canonical || lesson.title || lesson.label || ''

    // Explanation: confusable warning banner
    const confusableWarnEl = this.shadowRoot.querySelector('#dp-panel-explanation .pane__confusable-warning-text')
    if (confusableWarnEl) {
      confusableWarnEl.textContent = (ld.match_type_note)
        ? ld.match_type_note
        : 'This phrase looks similar to the family but has a different meaning.'
    }

    // Explanation: match type note
    const matchNoteEl = this.shadowRoot.querySelector('#dp-panel-explanation .pane__match-note')
    if (matchNoteEl) matchNoteEl.textContent = ld.match_type_note || ''

    // Explanation: main prose
    const explanationEl = this.shadowRoot.querySelector('#dp-panel-explanation .pane__explanation')
    if (explanationEl) explanationEl.textContent = lesson.explanation || ''

    // Explanation: why it matters
    const whyEl = this.shadowRoot.querySelector('#dp-panel-explanation .pane__why-it-matters-text')
    if (whyEl) whyEl.textContent = ld.why_it_matters || ''

    // Explanation fields (values only — labels were set in _htmlExplanationPanel)
    const fieldValues = Array.from(
      this.shadowRoot.querySelectorAll('#dp-panel-explanation .pane__field-value')
    )
    const displayFields = (lesson.fields ?? [])
      .filter(f => !SUPPRESS_IN_EXPLANATION.has(f.label.toLowerCase()))
    fieldValues.forEach((el, i) => {
      if (displayFields[i]) el.textContent = displayFields[i].value
    })

    // Origins: prose
    const originEl = this.shadowRoot.querySelector('#dp-panel-origins .pane__origin-text')
    if (originEl) originEl.textContent = ld.origin || ld.etymology || ''

    // Origins: source citation
    const sourceEl = this.shadowRoot.querySelector('#dp-panel-origins .pane__source-citation')
    if (sourceEl) sourceEl.textContent = ld.source_text || ''

    // In Context: highlighted sentence
    const contextEl = this.shadowRoot.querySelector('#dp-panel-context .pane__context-sentence')
    if (contextEl) {
      if (language) contextEl.setAttribute('lang', language)
      if (dir && dir !== 'ltr') contextEl.setAttribute('dir', dir)
      highlightPhrase(contextEl, sentenceText || '', matchedVariant)
    }

    // Related: variant items (dicts with surface/match_type/note, or legacy strings)
    const rawVariants = Array.isArray(ld.variants) ? ld.variants : []
    this.shadowRoot.querySelectorAll('#dp-panel-related .pane__variant-text').forEach((el, i) => {
      const v = rawVariants[i]
      if (v != null) el.textContent = typeof v === 'string' ? v : (v.surface ?? '')
    })
    this.shadowRoot.querySelectorAll('#dp-panel-related .pane__variant-note').forEach((el, i) => {
      const v = rawVariants[i]
      const note = typeof v === 'object' ? (v?.note ?? '') : ''
      if (note) { el.textContent = note; el.hidden = false }
    })

    // Related: within-family confusable forms
    const confusableForms = Array.isArray(ld.confusable_forms) ? ld.confusable_forms : []
    this.shadowRoot.querySelectorAll('#dp-panel-related .pane__confusable-form-surface').forEach((el, i) => {
      if (confusableForms[i]) el.textContent = confusableForms[i].surface ?? ''
    })
    this.shadowRoot.querySelectorAll('#dp-panel-related .pane__confusable-form-note').forEach((el, i) => {
      const note = confusableForms[i]?.note ?? ''
      if (note) { el.textContent = note; el.hidden = false }
    })

    // Related: cross-family confusable IDs
    const confusables = Array.isArray(ld.confusables) ? ld.confusables : []
    this.shadowRoot.querySelectorAll('#dp-panel-related .pane__confusable-id').forEach((el, i) => {
      if (confusables[i] != null) {
        el.textContent = String(confusables[i]).replace(/_/g, '\u00a0')
      }
    })

    // Set initial panel visibility
    this._applyTabState()

    // Wire all interactive events
    this._wireEvents(matchedVariant, canonical, sentenceText || '', isNonCanonical)
  }

  // ── HTML fragment builders ──────────────────────────────────────────────────

  _htmlExplanationPanel(lesson, ld, matchedVariant, depthIdx = 2) {
    const allFields    = (lesson.fields ?? [])
      .filter(f => !SUPPRESS_IN_EXPLANATION.has(f.label.toLowerCase()))
    // Scholar (2): show all fields. Basic (0): none. Intermediate (1): all fields.
    const displayFields = depthIdx >= 1 ? allFields : []

    const fieldsHtml = displayFields.map(f => /* html */`
      <div class="pane__field">
        <dt class="pane__field-label">${esc(f.label)}</dt>
        <dd class="pane__field-value"></dd>
      </div>
    `).join('')

    const hasAudio        = Boolean(matchedVariant)
    const matchType       = ld.match_type || ''
    const matchTypeMeta   = matchType ? (MATCH_TYPE_META[matchType] ?? { label: matchType, cls: 'variant' }) : null
    const showMatchBadge  = Boolean(matchTypeMeta)
    const hasMatchNote    = Boolean(ld.match_type_note)
    // Why it matters only for Scholar depth
    const hasWhyItMatters = Boolean(ld.why_it_matters) && depthIdx >= 2
    const isConfusable    = matchType === 'confusable_not_same'

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
            <span class="pane__confusable-warning-text"></span>
          </div>
        ` : ''}
        ${showMatchBadge ? /* html */`
          <div class="pane__match-row">
            <span class="pane__match-badge pane__match-badge--${esc(matchTypeMeta.cls)}">
              ${esc(matchTypeMeta.label)}
            </span>
            ${hasMatchNote ? '<p class="pane__match-note"></p>' : ''}
          </div>
        ` : ''}
        <p class="pane__explanation"></p>
        ${hasWhyItMatters ? /* html */`
          <blockquote class="pane__why-it-matters">
            <p class="pane__why-it-matters-text"></p>
          </blockquote>
        ` : ''}
        ${displayFields.length ? `<dl class="pane__fields">${fieldsHtml}</dl>` : ''}
        ${hasAudio ? /* html */`
          <div class="pane__audio-row">
            <button class="pane__audio-btn" type="button" data-speak="phrase">
              <span aria-hidden="true">&#x1F50A;</span> Hear phrase
            </button>
          </div>
        ` : ''}
        <div class="pane__note-section">
          <p class="pane__note-label">Notes</p>
          <textarea class="pane__note-input"
                    placeholder="Add a note about this phrase\u2026"
                    aria-label="Your note about this annotation"
                    rows="3"></textarea>
          <div class="pane__note-actions">
            <button class="pane__note-save" type="button">Save</button>
            <button class="pane__note-clear" type="button">Clear</button>
          </div>
        </div>
      </section>
    `
  }

  _htmlOriginsPanel(isNonCanonical, hasSourceText, matchType = '') {
    const isConfusable = matchType === 'confusable_not_same'
    return /* html */`
      <section
        id="dp-panel-origins"
        role="tabpanel"
        aria-labelledby="dp-tab-origins"
        class="pane__panel"
        hidden
      >
        <p class="pane__origin-text"></p>
        ${hasSourceText ? /* html */`
          <cite class="pane__source-citation"></cite>
        ` : ''}
        <div class="pane__audio-row">
          ${isNonCanonical ? /* html */`
            <button class="pane__audio-btn" type="button" data-speak="original">
              <span aria-hidden="true">&#x1F50A;</span>
              ${isConfusable ? 'Hear this phrase' : 'Hear original form'}
            </button>
            <button class="pane__audio-btn" type="button" data-speak="canonical">
              <span aria-hidden="true">&#x1F50A;</span> Hear canonical form
            </button>
          ` : /* html */`
            <button class="pane__audio-btn" type="button" data-speak="phrase">
              <span aria-hidden="true">&#x1F50A;</span> Hear phrase
            </button>
          `}
        </div>
      </section>
    `
  }

  _htmlContextPanel(language, dir) {
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
        ></p>
        <div class="pane__audio-row">
          <button class="pane__audio-btn" type="button" data-speak="sentence">
            <span aria-hidden="true">&#x1F50A;</span> Hear sentence
          </button>
        </div>
      </section>
    `
  }

  _htmlRelatedPanel(ld, canonical, isNonCanonical) {
    // variants may be list[dict{surface,match_type,note}] or legacy list[str]
    const rawVariants      = Array.isArray(ld.variants)         ? ld.variants         : []
    const confusables      = Array.isArray(ld.confusables)      ? ld.confusables      : []
    const confusableForms  = Array.isArray(ld.confusable_forms) ? ld.confusable_forms : []

    const variantItems = rawVariants.map(v => {
      const surface  = typeof v === 'string' ? v : (v.surface ?? '')
      const mt       = typeof v === 'string' ? '' : (v.match_type ?? '')
      const mtMeta   = mt ? (MATCH_TYPE_META[mt] ?? { label: mt, cls: 'variant' }) : null
      const hasNote  = typeof v !== 'string' && Boolean(v.note)
      const isCanon  = canonical && surface.toLowerCase() === canonical.toLowerCase()
      return /* html */`
        <li class="pane__variant-item${isCanon ? ' pane__variant-item--canonical' : ''}">
          <span class="pane__variant-surface-row">
            <span class="pane__variant-text"></span>
            ${isCanon ? '<span class="pane__canonical-star" aria-label="canonical form">&#x2605;</span>' : ''}
            ${mtMeta && !isCanon ? /* html */`
              <span class="pane__match-badge pane__match-badge--${esc(mtMeta.cls)} pane__match-badge--sm">
                ${esc(mtMeta.label)}
              </span>
            ` : ''}
          </span>
          ${hasNote ? '<p class="pane__variant-note" hidden></p>' : ''}
        </li>
      `
    }).join('')

    const confusableFormItems = confusableForms.map(() => /* html */`
      <li class="pane__confusable-form-item">
        <span class="pane__match-badge pane__match-badge--danger pane__match-badge--sm">
          ${esc(MATCH_TYPE_META.confusable_not_same.label)}
        </span>
        <span class="pane__confusable-form-surface"></span>
        <p class="pane__confusable-form-note" hidden></p>
      </li>
    `).join('')

    const confusableItems = confusables.map(() => /* html */`
      <li class="pane__confusable-item">
        <span class="pane__confusable-id"></span>
      </li>
    `).join('')

    const hasAnyConfusables = confusables.length > 0 || confusableForms.length > 0

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
            <h3 class="pane__section-heading" id="dp-variants-h">Variant forms</h3>
            <ul class="pane__variant-list">${variantItems}</ul>
          </section>
        ` : ''}
        ${hasAnyConfusables ? /* html */`
          <section class="pane__subsection" aria-labelledby="dp-confusables-h">
            <h3 class="pane__section-heading" id="dp-confusables-h">Confusable with</h3>
            <ul class="pane__confusable-list">
              ${confusableFormItems}
              ${confusableItems}
            </ul>
          </section>
        ` : ''}
        ${isNonCanonical && ld.match_type !== 'confusable_not_same' ? /* html */`
          <div class="pane__audio-row">
            <button class="pane__audio-btn" type="button" data-speak="canonical">
              <span aria-hidden="true">&#x1F50A;</span> Hear canonical form
            </button>
          </div>
        ` : ''}
      </section>
    `
  }

  // ── Event wiring ─────────────────────────────────────────────────────────────

  _wireEvents(matchedVariant, canonical, sentenceText, isNonCanonical) {
    const { lesson, language, ttsTag } = this.#config

    // Close button
    this.shadowRoot.querySelector('.pane__close')
      ?.addEventListener('click', () => this.hide())

    // Study drills button
    this.shadowRoot.querySelector('.pane__study-btn')
      ?.addEventListener('click', () => {
        this.dispatchEvent(new CustomEvent('pane-study', { bubbles: true, composed: true }))
        this.#onStudy?.()
      })

    // Tab keyboard navigation (ARIA APG roving-tabindex pattern)
    const tabEls = Array.from(this.shadowRoot.querySelectorAll('[role="tab"]'))
    tabEls.forEach((tab, i) => {
      tab.addEventListener('click', () => {
        this.#activeTab = i
        this._applyTabState()
      })
      tab.addEventListener('keydown', (e) => {
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
    })

    // Audio buttons
    this.shadowRoot.querySelectorAll('[data-speak]').forEach(btn => {
      btn.addEventListener('click', () => {
        if (!this.#onSpeak) return
        const mode = btn.dataset.speak
        let text = ''
        switch (mode) {
          case 'phrase':    text = matchedVariant || canonical;  break
          // "original" = the non-canonical matched form (e.g. the Shakespeare spelling)
          case 'original':  text = matchedVariant;               break
          // "modern" = the canonical / most-cited form
          case 'modern':    text = canonical || matchedVariant;  break
          case 'sentence':  text = sentenceText;                 break
          case 'canonical': text = canonical;                    break
        }
        if (text) this.#onSpeak(text, ttsTag ?? language)
      })
    })

    // Share button — build a deep-link URL and copy it / use Web Share API
    const shareBtn  = this.shadowRoot.querySelector('.pane__share')
    const shareHint = this.shadowRoot.querySelector('.pane__share-hint')
    shareBtn?.addEventListener('click', () => {
      const url = new URL(location.href)
      url.searchParams.set('annotation', lesson.id)
      url.searchParams.set('language',   language)
      const shareUrl = url.toString()
      if (navigator.share) {
        navigator.share({ url: shareUrl, title: lesson.title || lesson.label || '' }).catch(() => {})
      } else {
        navigator.clipboard.writeText(shareUrl).then(() => {
          if (shareHint) {
            shareHint.textContent = 'Link copied!'
            setTimeout(() => { shareHint.textContent = '' }, 2200)
          }
        }).catch(() => {
          if (shareHint) {
            shareHint.textContent = 'Copy: ' + shareUrl
            setTimeout(() => { shareHint.textContent = '' }, 6000)
          }
        })
      }
    })

    // Note section — load from localStorage, wire save / clear
    const noteKey   = `mn-note-${lesson.id}`
    const noteInput = this.shadowRoot.querySelector('.pane__note-input')
    const noteSave  = this.shadowRoot.querySelector('.pane__note-save')
    const noteClear = this.shadowRoot.querySelector('.pane__note-clear')
    if (noteInput) {
      noteInput.value = localStorage.getItem(noteKey) ?? ''

      noteSave?.addEventListener('click', () => {
        const val = noteInput.value.trim()
        if (val) {
          localStorage.setItem(noteKey, val)
        } else {
          localStorage.removeItem(noteKey)
        }
        this.dispatchEvent(new CustomEvent('note-updated', {
          bubbles: true, composed: true,
          detail: { objectId: lesson.id, hasNote: Boolean(val) },
        }))
        if (noteSave) {
          const orig = noteSave.textContent
          noteSave.textContent = 'Saved!'
          setTimeout(() => { noteSave.textContent = orig }, 1500)
        }
      })

      noteClear?.addEventListener('click', () => {
        noteInput.value = ''
        localStorage.removeItem(noteKey)
        this.dispatchEvent(new CustomEvent('note-updated', {
          bubbles: true, composed: true,
          detail: { objectId: lesson.id, hasNote: false },
        }))
      })
    }

    this.#wireDrag()
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
        border: 1px solid var(--border);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        /* Accent stripe on the inline-start edge, keyed to the object type. */
        border-inline-start: 3px solid ${ref};
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
          border-block-start: 3px solid ${ref};
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
        color: color-mix(in oklch, ${ref} 80%, CanvasText);
        background: color-mix(in oklch, ${ref} 14%, Canvas);
        border: 1px solid color-mix(in oklch, ${ref} 30%, Canvas);
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
        border-block-end-color: color-mix(in oklch, ${ref} 85%, CanvasText);
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
        background: color-mix(in oklch, ${ref} 14%, Canvas);
        color:      color-mix(in oklch, ${ref} 80%, CanvasText);
        border: 1px solid color-mix(in oklch, ${ref} 30%, Canvas);
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

      /* ── Why it matters ─────────────────────────────────────────────────── */
      .pane__why-it-matters {
        margin: 0;
        padding: 0.6rem 0.75rem;
        border-inline-start: 3px solid color-mix(in oklch, ${ref} 55%, Canvas);
        background: color-mix(in oklch, ${ref} 6%, Canvas);
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
        background: color-mix(in oklch, ${ref} 10%, Canvas);
        border-color: color-mix(in oklch, ${ref} 45%, Canvas);
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
        background: color-mix(in oklch, ${ref} 24%, Canvas);
        color: inherit;
        border-radius: 0.2em;
        padding-inline: 0.1em;
        text-decoration: underline;
        text-decoration-thickness: 1px;
        text-underline-offset: 0.2em;
        text-decoration-color: color-mix(in oklch, ${ref} 55%, CanvasText);
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
        color: color-mix(in oklch, ${ref} 75%, CanvasText);
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
        padding-block: 0.3rem;
        font-size: 0.875rem;
        color: var(--muted);
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
        min-block-size: 2rem;
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
    `
  }
}

customElements.define('mnemosyne-detail-pane', MnemosyneDetailPane)
