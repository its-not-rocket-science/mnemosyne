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

// Field labels shown in the Explanation panel — suppress from the field list
// because they are rendered in dedicated sections (Related / Origins).
const SUPPRESS_IN_EXPLANATION = new Set([
  'known variants', 'confusable with', 'origin', 'variant note',
])

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
  #config         = null   // { lesson, sentenceText, language, dir, ttsTag, caps }
  #activeTab      = 0
  #visibleTabs    = []     // subset of ALL_TABS that are rendered
  #onSpeak        = null
  #onStudy        = null
  #previousFocus  = null
  #keydownHandler = null

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

  show({ lesson, sentenceText, language, dir, ttsTag, caps, onSpeak, onStudy }) {
    this.#config        = { lesson, sentenceText, language, dir: dir ?? 'ltr', ttsTag, caps }
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
      this.shadowRoot.querySelector('[role="tab"]')?.focus()
    })

    // Close on Escape.
    this.#keydownHandler = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        this.hide()
      }
    }
    document.addEventListener('keydown', this.#keydownHandler)
  }

  hide() {
    this.removeAttribute('data-open')
    this.setAttribute('inert', '')

    if (this.#keydownHandler) {
      document.removeEventListener('keydown', this.#keydownHandler)
      this.#keydownHandler = null
    }

    this.dispatchEvent(new CustomEvent('pane-close', { bubbles: true, composed: true }))
    this.#previousFocus?.focus?.()
  }

  // ── Rendering ───────────────────────────────────────────────────────────────

  _render() {
    const { lesson, sentenceText, language, dir } = this.#config
    const ld   = lesson.lesson_data ?? {}
    const type = lesson.type ?? 'vocabulary'
    const meta = TYPE_META[type] ?? TYPE_META.vocabulary

    // Which optional tabs have data?
    const hasOrigins = Boolean(ld.origin || ld.etymology)
    const hasRelated = Boolean(
      (Array.isArray(ld.variants)     && ld.variants.length > 1) ||
      (Array.isArray(ld.confusables)  && ld.confusables.length > 0)
    )

    this.#visibleTabs = MnemosyneDetailPane.ALL_TABS.filter(
      t => t.alwaysShow || (t.id === 'origins' && hasOrigins) || (t.id === 'related' && hasRelated)
    )

    const matchedVariant = ld.matched_variant || lesson.label || ''
    const canonical      = ld.canonical_form  || ''
    const isNonCanonical = canonical && matchedVariant &&
                           canonical.toLowerCase() !== matchedVariant.toLowerCase()

    // ── Assemble shadow DOM ──────────────────────────────────────────────────
    this.shadowRoot.innerHTML = /* html */`
      <style>${this._styles(meta)}</style>
      <aside class="pane" role="complementary" aria-labelledby="dp-heading">

        <div class="pane__drag-handle" aria-hidden="true"></div>

        <header class="pane__header">
          <div class="pane__badge" aria-hidden="true">${esc(meta.icon)} ${esc(meta.label)}</div>
          <h2 class="pane__title" id="dp-heading"></h2>
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
          ${this._htmlExplanationPanel(lesson, ld, matchedVariant)}
          ${hasOrigins  ? this._htmlOriginsPanel(isNonCanonical) : ''}
          ${this._htmlContextPanel(language, dir)}
          ${hasRelated  ? this._htmlRelatedPanel(ld, canonical, isNonCanonical) : ''}
        </div>

        <footer class="pane__footer">
          <button class="pane__study-btn" type="button">Study drills &#x2192;</button>
        </footer>

      </aside>
    `

    // ── Populate text content safely (never via innerHTML) ──────────────────

    // Header title
    const titleEl = this.shadowRoot.querySelector('#dp-heading')
    if (titleEl) titleEl.textContent = canonical || lesson.title || lesson.label || ''

    // Explanation prose
    const explanationEl = this.shadowRoot.querySelector('#dp-panel-explanation .pane__explanation')
    if (explanationEl) explanationEl.textContent = lesson.explanation || ''

    // Explanation fields (values only — labels were set in _htmlExplanationPanel)
    const fieldValues = Array.from(
      this.shadowRoot.querySelectorAll('#dp-panel-explanation .pane__field-value')
    )
    const displayFields = (lesson.fields ?? [])
      .filter(f => !SUPPRESS_IN_EXPLANATION.has(f.label.toLowerCase()))
    fieldValues.forEach((el, i) => {
      if (displayFields[i]) el.textContent = displayFields[i].value
    })

    // Origins text
    const originEl = this.shadowRoot.querySelector('#dp-panel-origins .pane__origin-text')
    if (originEl) originEl.textContent = ld.origin || ld.etymology || ''

    // In Context: highlighted sentence
    const contextEl = this.shadowRoot.querySelector('#dp-panel-context .pane__context-sentence')
    if (contextEl) {
      if (language) contextEl.setAttribute('lang', language)
      if (dir && dir !== 'ltr') contextEl.setAttribute('dir', dir)
      highlightPhrase(contextEl, sentenceText || '', matchedVariant)
    }

    // Related: variant items
    const variants = Array.isArray(ld.variants) ? ld.variants : []
    this.shadowRoot.querySelectorAll('#dp-panel-related .pane__variant-text').forEach((el, i) => {
      if (variants[i] != null) el.textContent = variants[i]
    })

    // Related: variant notes
    const variantNoteEls = this.shadowRoot.querySelectorAll('#dp-panel-related .pane__variant-note')
    // Notes are stored per-family in lesson_data.variant_notes (map: surface → note)
    // For now, show the lesson_data.variant_note on the matched variant only.
    // Future: enrich per-variant notes via expanded lesson_data.
    const variantNoteText = ld.variant_note || ''
    if (variantNoteEls.length > 0 && variantNoteText) {
      // Find index of matched variant in variants list
      const matchedIdx = variants.findIndex(v =>
        v.toLowerCase() === matchedVariant.toLowerCase()
      )
      if (matchedIdx >= 0 && variantNoteEls[matchedIdx]) {
        variantNoteEls[matchedIdx].textContent = variantNoteText
        variantNoteEls[matchedIdx].hidden = false
      }
    }

    // Related: confusable items
    const confusables = Array.isArray(ld.confusables) ? ld.confusables : []
    this.shadowRoot.querySelectorAll('#dp-panel-related .pane__confusable-id').forEach((el, i) => {
      if (confusables[i] != null) {
        // Convert slug → readable: "of_the_first_water" → "of the first water"
        el.textContent = String(confusables[i]).replace(/_/g, '\u00a0')
      }
    })

    // Set initial panel visibility
    this._applyTabState()

    // Wire all interactive events
    this._wireEvents(matchedVariant, canonical, sentenceText || '', isNonCanonical)
  }

  // ── HTML fragment builders ──────────────────────────────────────────────────

  _htmlExplanationPanel(lesson, ld, matchedVariant) {
    const displayFields = (lesson.fields ?? [])
      .filter(f => !SUPPRESS_IN_EXPLANATION.has(f.label.toLowerCase()))

    const fieldsHtml = displayFields.map(f => /* html */`
      <div class="pane__field">
        <dt class="pane__field-label">${esc(f.label)}</dt>
        <dd class="pane__field-value"></dd>
      </div>
    `).join('')

    const hasAudio = Boolean(matchedVariant)

    return /* html */`
      <section
        id="dp-panel-explanation"
        role="tabpanel"
        aria-labelledby="dp-tab-explanation"
        class="pane__panel"
      >
        <p class="pane__explanation"></p>
        ${displayFields.length ? `<dl class="pane__fields">${fieldsHtml}</dl>` : ''}
        ${hasAudio ? /* html */`
          <div class="pane__audio-row">
            <button class="pane__audio-btn" type="button" data-speak="phrase">
              <span aria-hidden="true">&#x1F50A;</span> Hear phrase
            </button>
          </div>
        ` : ''}
      </section>
    `
  }

  _htmlOriginsPanel(isNonCanonical) {
    return /* html */`
      <section
        id="dp-panel-origins"
        role="tabpanel"
        aria-labelledby="dp-tab-origins"
        class="pane__panel"
        hidden
      >
        <p class="pane__origin-text"></p>
        <div class="pane__audio-row">
          ${isNonCanonical ? /* html */`
            <button class="pane__audio-btn" type="button" data-speak="original">
              <span aria-hidden="true">&#x1F50A;</span> Hear original form
            </button>
            <button class="pane__audio-btn" type="button" data-speak="modern">
              <span aria-hidden="true">&#x1F50A;</span> Hear modern form
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
    const variants    = Array.isArray(ld.variants)    ? ld.variants    : []
    const confusables = Array.isArray(ld.confusables) ? ld.confusables : []

    const variantItems = variants.map(v => {
      const isCanon = canonical && v.toLowerCase() === canonical.toLowerCase()
      return /* html */`
        <li class="pane__variant-item${isCanon ? ' pane__variant-item--canonical' : ''}">
          <span class="pane__variant-text"></span>
          ${isCanon ? '<span class="pane__canonical-star" aria-label="canonical form">&#x2605;</span>' : ''}
          <span class="pane__variant-note" hidden></span>
        </li>
      `
    }).join('')

    const confusableItems = confusables.map(() => /* html */`
      <li class="pane__confusable-item">
        <span class="pane__confusable-id"></span>
      </li>
    `).join('')

    return /* html */`
      <section
        id="dp-panel-related"
        role="tabpanel"
        aria-labelledby="dp-tab-related"
        class="pane__panel"
        hidden
      >
        ${variants.length ? /* html */`
          <section class="pane__subsection" aria-labelledby="dp-variants-h">
            <h3 class="pane__section-heading" id="dp-variants-h">Variant forms</h3>
            <ul class="pane__variant-list">${variantItems}</ul>
          </section>
        ` : ''}
        ${confusables.length ? /* html */`
          <section class="pane__subsection" aria-labelledby="dp-confusables-h">
            <h3 class="pane__section-heading" id="dp-confusables-h">Confusable with</h3>
            <ul class="pane__confusable-list">${confusableItems}</ul>
          </section>
        ` : ''}
        ${isNonCanonical ? /* html */`
          <div class="pane__audio-row">
            <button class="pane__audio-btn" type="button" data-speak="modern">
              <span aria-hidden="true">&#x1F50A;</span> Hear modern form
            </button>
          </div>
        ` : ''}
      </section>
    `
  }

  // ── Event wiring ─────────────────────────────────────────────────────────────

  _wireEvents(matchedVariant, canonical, sentenceText, isNonCanonical) {
    const { language, ttsTag } = this.#config

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
          z-index: 200;
          max-block-size: 82dvh;
          /* Start off-screen; transition to translateY(0) when [data-open] set. */
          transform: translateY(110%);
          transition: transform 0.35s cubic-bezier(0.32, 0, 0.67, 0);
        }

        :host([data-open]) {
          transform: translateY(0);
          transition-timing-function: cubic-bezier(0.33, 1, 0.68, 1);
        }

        @media (prefers-reduced-motion: reduce) {
          :host         { transition: none; }
          :host([data-open]) { transform: translateY(0); }
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

      /* ── Drag handle (mobile visual affordance) ──────────────────────────── */
      .pane__drag-handle {
        display: none;
      }

      @media (max-width: 53.99rem) {
        .pane__drag-handle {
          display: block;
          inline-size: 2.5rem;
          block-size: 0.25rem;
          background: var(--border-input);
          border-radius: 999px;
          margin-inline: auto;
          margin-block: 0.55rem 0.25rem;
          flex-shrink: 0;
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

      /* ── Explanation prose ──────────────────────────────────────────────── */
      .pane__explanation {
        margin: 0;
        font-size: 0.9375rem;
        line-height: 1.6;
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
        align-items: baseline;
        gap: 0.4rem;
        padding-block: 0.35rem;
        border-block-end: 1px solid var(--border);
        font-size: 0.875rem;
        line-height: 1.4;
      }
      .pane__variant-item:last-child { border-block-end: none; }

      .pane__variant-text {
        flex: 1 1 0;
        min-inline-size: 0;
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
    `
  }
}

customElements.define('mnemosyne-detail-pane', MnemosyneDetailPane)
