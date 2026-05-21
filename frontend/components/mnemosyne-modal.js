import { t, ti } from '../js/i18n.js'

// Field labels (lower-cased) whose values are romanized / transliterated text.
// Used to assign data-layer="romanized" so the script-view toggle can hide them.
const ROMANIZED_LABELS = new Set(['romanized', 'readings'])

// Field labels whose values are source-script (native) text.
const NATIVE_LABELS = new Set(['native', 'character'])

// Field labels whose values are in the UI language (English) — do NOT apply
// the target lang/dir to these, or an Arabic gloss would render in RTL.
const UI_LANG_LABELS = new Set(['translation', 'gloss'])

export class MnemosyneModal extends HTMLElement {
  #inertedElements = []

  // Language context — set by open(), used by drill renderers.
  #language   = null
  #dir        = 'ltr'
  #ttsTag     = null
  // Modal-local script view: 'both' shows all layers by default.
  #scriptView = 'both'

  constructor() {
    super()
    this.attachShadow({ mode: 'open' })
    this.isOpen = false
    this.previouslyFocused = null
    this.onKeydown = this.onKeydown.bind(this)
  }

  connectedCallback() {
    this.render()
  }

  open({ lesson, objectId, caps, language, onRate, onSpeak, onCheckResult }) {
    // Resolve language metadata from caps with safe fallbacks.
    this.#language   = language ?? null
    this.#dir        = caps?.direction ?? 'ltr'
    this.#ttsTag     = caps?.tts_lang_tag ?? language ?? null
    this.#scriptView = 'both'

    this.isOpen = true
    this.previouslyFocused = document.activeElement
    this.render({ lesson, objectId, caps, language, onRate, onSpeak, onCheckResult })
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', this.onKeydown)

    this.#inertedElements = []
    for (const child of document.body.children) {
      if (child !== this && !child.hasAttribute('inert')) {
        child.setAttribute('inert', '')
        this.#inertedElements.push(child)
      }
    }

    this.shadowRoot.querySelector('[role="dialog"]')?.focus()
  }

  close() {
    this.isOpen = false
    document.body.style.overflow = ''
    document.removeEventListener('keydown', this.onKeydown)

    for (const el of this.#inertedElements) {
      el.removeAttribute('inert')
    }
    this.#inertedElements = []

    this.render()
    this.previouslyFocused?.focus?.()
  }

  onKeydown(event) {
    if (!this.isOpen) return

    if (event.key === 'Escape') {
      event.preventDefault()
      this.close()
      return
    }

    if (event.key === 'Tab') {
      const focusables = [
        ...this.shadowRoot.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), ' +
          'select:not([disabled]), textarea:not([disabled])'
        ),
      ]
      if (focusables.length === 0) return
      const first = focusables[0]
      const last  = focusables[focusables.length - 1]

      if (event.shiftKey && this.shadowRoot.activeElement === first) {
        event.preventDefault()
        last.focus()
      } else if (!event.shiftKey && this.shadowRoot.activeElement === last) {
        event.preventDefault()
        first.focus()
      }
    }
  }

  render(state = null) {
    if (!this.shadowRoot) return
    if (!state) {
      this.shadowRoot.innerHTML = `<style>:host { display: block }</style>`
      return
    }

    const { lesson, objectId, caps, onRate, onSpeak, onCheckResult } = state
    const canSpeak  = 'speechSynthesis' in window
    const hasTranslit = Boolean(caps?.transliteration_scheme)
    const exampleText = lesson.examples?.[0] ?? lesson.title

    this.shadowRoot.innerHTML = `
      <style>
        :host { color-scheme: light dark; }

        .overlay {
          position: fixed;
          inset: 0;
          background: color-mix(in srgb, black 55%, transparent);
          display: grid;
          place-items: center;
          padding: 1rem;
          z-index: 1000;
          overscroll-behavior: contain;
        }

        .dialog {
          inline-size: min(44rem, 100%);
          max-block-size: 90dvh;
          overflow-y: auto;
          background: Canvas;
          color: CanvasText;
          border-radius: 1rem;
          padding: clamp(1rem, 4vw, 1.5rem);
          box-shadow: 0 1rem 2rem color-mix(in srgb, black 25%, transparent);
        }

        .dialog:focus { outline: none; }

        /* Header always uses logical LTR layout — close button stays at
           inline-end regardless of the target language direction. */
        .header {
          display: flex;
          justify-content: space-between;
          align-items: start;
          gap: 1rem;
        }

        h2 {
          margin: 0;
          font-size: clamp(1rem, 2.5vw + 0.5rem, 1.25rem);
          /* Target-language title may wrap differently — let it. */
          overflow-wrap: break-word;
        }

        /* ── buttons ── */
        button {
          /* 45% CanvasText gives ≥ 3:1 against Canvas in light and dark mode — SC 1.4.11. */
          border: 1px solid color-mix(in srgb, CanvasText 45%, Canvas);
          background: transparent;
          border-radius: 999px;
          color: inherit;
          font: inherit;
          cursor: pointer;
          min-block-size: 2.75rem;
        }

        button:focus-visible {
          outline: 3px solid var(--accent, #3557ff);
          outline-offset: 3px;
        }

        button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        /* ── script view toggle ── */
        .script-toggle {
          display: flex;
          align-items: center;
          gap: 0.3rem;
          flex-wrap: wrap;
          margin-block: 0.75rem;
          font-size: 0.85rem;
        }

        .script-toggle__label {
          color: var(--muted, GrayText);
          font-size: 0.75rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          margin-inline-end: 0.15rem;
        }

        .script-toggle__btn {
          min-block-size: 2.75rem;
          padding-inline: 0.65rem;
          font-size: 0.8rem;
          /* Inherits the general button border (45% CanvasText). */
          border: 1px solid color-mix(in srgb, CanvasText 45%, Canvas);
          border-radius: 999px;
          background: transparent;
          color: inherit;
          cursor: pointer;
        }

        .script-toggle__btn:focus-visible {
          outline: 3px solid var(--accent, #3557ff);
          outline-offset: 2px;
        }

        .script-toggle__btn[aria-pressed="true"] {
          background: color-mix(in srgb, CanvasText 15%, Canvas);
          border-color: color-mix(in srgb, CanvasText 40%, Canvas);
        }

        /* ── layer visibility — controlled by data-script-view on .lesson-body ── */
        .lesson-body[data-script-view="native"]    [data-layer="romanized"] { display: none; }
        .lesson-body[data-script-view="romanized"] [data-layer="native"]    { display: none; }
        /* 'both' (default): both layers visible */

        /* ── lesson body ── */
        .lesson-body {
          margin-block-start: 0.5rem;
        }

        .explanation {
          margin: 0 0 0.75rem;
          line-height: 1.5;
        }

        .type-badge {
          display: inline-block;
          font-size: 0.75rem;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.06em;
          padding: 0.15em 0.6em;
          border-radius: 999px;
          border: 1px solid color-mix(in srgb, CanvasText 20%, transparent);
          margin-block-end: 0.25rem;
          color: var(--muted, GrayText);
        }

        /* Shown only in dictionary mode — honest signal to the learner. */
        .mode-note {
          font-size: 0.75rem;
          font-style: italic;
          color: var(--muted, GrayText);
          margin: 0 0 0.5rem;
        }

        /* ── fields ── */
        .fields {
          display: grid;
          grid-template-columns: auto 1fr;
          gap: 0.2rem 1rem;
          margin: 0 0 1rem;
          font-size: 0.9rem;
        }

        .field-label {
          color: var(--muted, GrayText);
          white-space: nowrap;
        }

        .field-value {
          font-weight: 500;
          overflow-wrap: break-word;
        }

        /* ── examples / speak ── */
        .examples {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          margin-block-end: 1.25rem;
          flex-wrap: wrap;
        }

        .example-text {
          font-size: 1.15rem;
          font-weight: 600;
          margin: 0;
          /* Prevent overflow for long CJK or unbreakable script strings. */
          overflow-wrap: break-word;
        }

        .btn-speak {
          padding-inline: 0.85rem;
          font-size: 0.85rem;
        }

        /* ── drills ── */
        .drills-section { margin-block-start: 1.25rem; }

        .drills-heading {
          font-size: 0.8rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: var(--muted, GrayText);
          margin: 0 0 0.75rem;
        }

        .drill {
          background: color-mix(in srgb, CanvasText 4%, transparent);
          border-radius: 0.5rem;
          padding: 0.85rem 1rem;
          margin-block-end: 0.6rem;
        }

        .drill[data-answered="true"] .drill-option { cursor: default; }

        .drill-prompt {
          margin: 0 0 0.6rem;
          font-size: 0.95rem;
          overflow-wrap: break-word;
        }

        .drill-text {
          font-size: 1.1rem;
          font-weight: 600;
          margin: 0 0 0.6rem;
          overflow-wrap: break-word;
        }

        /* RTL text elements — text-align:start resolves to right in RTL. */
        .drill-text[dir="rtl"],
        .drill-prompt[dir="rtl"],
        .example-text[dir="rtl"] {
          text-align: start;
        }

        .drill-options {
          display: flex;
          flex-wrap: wrap;
          gap: 0.4rem;
        }

        .drill-option {
          padding-inline: 0.85rem;
          font-size: 0.9rem;
        }

        .drill-option[data-state="correct"] {
          background: oklch(0.92 0.10 145);
          border-color: oklch(0.55 0.18 145);
          color: oklch(0.25 0.10 145);
        }

        @media (prefers-color-scheme: dark) {
          :host-context(:root[data-theme="auto"]) .drill-option[data-state="correct"] {
            background: oklch(0.30 0.10 145);
            border-color: oklch(0.55 0.18 145);
            color: oklch(0.85 0.08 145);
          }
        }

        :host-context(:root[data-theme="dark"]) .drill-option[data-state="correct"] {
          background: oklch(0.30 0.10 145);
          border-color: oklch(0.55 0.18 145);
          color: oklch(0.85 0.08 145);
        }

        .drill-option[data-state="wrong"] {
          background: color-mix(in srgb, var(--error-color, oklch(0.50 0.2 29)) 10%, transparent);
          border-color: var(--error-color, oklch(0.50 0.2 29));
          opacity: 0.7;
        }

        .drill-input-row {
          display: flex;
          gap: 0.5rem;
          flex-wrap: wrap;
          align-items: center;
        }

        .drill-input {
          border: 1px solid color-mix(in srgb, CanvasText 30%, transparent);
          border-radius: 0.375rem;
          background: Canvas;
          color: CanvasText;
          font: inherit;
          font-size: 0.95rem;
          padding: 0.4rem 0.6rem;
          /* flex: 1 lets the input fill available row space while min-inline-size: 0
             allows it to shrink below its intrinsic width when the row is tight. */
          flex: 1 1 0;
          min-inline-size: 8rem;
          block-size: 2.75rem;
        }

        /* RTL input: align cursor/caret to the inline-start (right) edge. */
        .drill-input[dir="rtl"] {
          text-align: start;
        }

        .drill-input:focus-visible {
          outline: 3px solid var(--accent, #3557ff);
          outline-offset: 2px;
        }

        .drill-check {
          padding-inline: 0.85rem;
          font-size: 0.9rem;
        }

        .drill-feedback {
          margin: 0.5rem 0 0;
          font-size: 0.875rem;
          font-weight: 500;
        }

        .drill-feedback[data-result="correct"] { color: oklch(0.45 0.15 145); }
        .drill-feedback[data-result="wrong"]   { color: var(--error-color, oklch(0.50 0.2 29)); }

        @media (prefers-color-scheme: dark) {
          :host-context(:root[data-theme="auto"]) .drill-feedback[data-result="correct"] { color: oklch(0.70 0.15 145); }
        }

        :host-context(:root[data-theme="dark"]) .drill-feedback[data-result="correct"] { color: oklch(0.70 0.15 145); }

        /* ── recall ratings ── */
        .ratings {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          margin-block-start: 1.25rem;
        }

        .ratings button { padding-inline: 0.85rem; }

        .close {
          padding-inline: 0.9rem;
          flex-shrink: 0;
        }

        /* ── status regions ── */
        .status, .status-error { min-block-size: 1.5rem; margin-block-start: 0.75rem; }
        .status       { color: var(--muted, GrayText); }
        .status-error { color: var(--error-color, oklch(0.50 0.2 29)); }
        .status-error:empty { display: none; }

        /* ── enrichment sections ── */
        .enrichment-section {
          margin-block-start: 1rem;
          font-size: 0.875rem;
        }

        .enrichment-heading {
          font-size: 0.7rem;
          font-weight: 700;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: var(--muted, GrayText);
          margin: 0 0 0.5rem;
        }

        .paradigm-wrap {
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
          margin-block-end: 0.75rem;
        }

        .paradigm-wrap summary {
          cursor: pointer;
          font-size: 0.8rem;
          color: var(--muted, GrayText);
          padding-block: 0.25rem;
          user-select: none;
        }

        .paradigm-table {
          border-collapse: collapse;
          font-size: 0.8rem;
          margin-block-start: 0.4rem;
        }

        .paradigm-table th,
        .paradigm-table td {
          border: 1px solid color-mix(in srgb, CanvasText 20%, Canvas);
          padding: 0.3rem 0.5rem;
          text-align: center;
          vertical-align: top;
        }

        .paradigm-table th {
          font-weight: 700;
          font-size: 0.65rem;
          text-transform: uppercase;
          letter-spacing: 0.05em;
          color: var(--muted, GrayText);
          background: color-mix(in srgb, CanvasText 4%, Canvas);
        }

        .paradigm-cell--current {
          background: color-mix(in srgb, var(--accent, #3557ff) 14%, Canvas);
          font-weight: 600;
          outline: 2px solid color-mix(in srgb, var(--accent, #3557ff) 50%, Canvas);
          outline-offset: -2px;
        }

        .equiv-card {
          border-inline-start: 3px solid color-mix(in srgb, var(--accent, #3557ff) 50%, transparent);
          padding-inline-start: 0.6rem;
          margin-block-end: 0.4rem;
        }

        .equiv-construction {
          font-weight: 600;
          overflow-wrap: break-word;
        }

        .equiv-note {
          font-size: 0.8rem;
          color: var(--muted, GrayText);
          margin: 0;
        }

        .contrast-card {
          background: color-mix(in srgb, oklch(0.72 0.18 55) 8%, Canvas);
          border: 1px solid color-mix(in srgb, oklch(0.72 0.18 55) 30%, Canvas);
          border-radius: 0.4rem;
          padding: 0.4rem 0.6rem;
          margin-block-end: 0.35rem;
          font-size: 0.8125rem;
        }

        .contrast-forms {
          font-weight: 600;
          margin-block-end: 0.2rem;
        }

        .contrast-vs {
          font-weight: 400;
          color: var(--muted, GrayText);
          margin-inline: 0.25rem;
          font-size: 0.75rem;
        }

        .contrast-note {
          margin: 0;
          line-height: 1.5;
        }

        .vocab-list {
          list-style: none;
          margin: 0;
          padding: 0;
          display: flex;
          flex-direction: column;
          gap: 0.2rem;
        }

        .vocab-item {
          display: flex;
          align-items: baseline;
          gap: 0.4rem;
          flex-wrap: wrap;
          padding-block: 0.2rem;
          border-block-end: 1px solid color-mix(in srgb, CanvasText 10%, Canvas);
          font-size: 0.875rem;
        }
        .vocab-item:last-child { border-block-end: none; }

        .vocab-form  { font-weight: 600; overflow-wrap: break-word; }
        .vocab-lemma { font-size: 0.8rem; color: var(--muted, GrayText); }
        .vocab-gloss { font-size: 0.8rem; color: var(--muted, GrayText); }

        /* ── Narrow-screen overrides (≤ 320 px viewport) ── */
        @media (max-width: 20rem) {
          /* Switch the definition list from a two-column grid to a stacked layout
             so long field labels (e.g. "Separable prefix") don't crowd the value
             column on the narrowest Android and iPhone SE displays. */
          .fields {
            grid-template-columns: 1fr;
            gap: 0.1rem 0;
          }

          .field-label {
            margin-block-start: 0.6rem;
            font-size: 0.8rem;
          }

          /* Tighten drill padding to reclaim horizontal space. */
          .drill {
            padding: 0.65rem 0.75rem;
          }
        }

        @media (prefers-reduced-motion: reduce) {
          .status { transition: none !important; }
        }

        @media (forced-colors: active) {
          .drill-option[data-state="correct"] { outline: 3px solid Highlight; }
          .drill-option[data-state="wrong"]   { outline: 3px solid Mark; }
        }
      </style>

      <div class="overlay" data-overlay>
        <div class="dialog" role="dialog" aria-modal="true"
             aria-labelledby="modal-title" tabindex="-1">

          <div class="header">
            <h2 id="modal-title"></h2>
            <button type="button" class="close" data-close>${t('close_btn_aria')}</button>
          </div>

          ${hasTranslit ? `
          <div class="script-toggle" role="group" aria-label="${t('aria_script_view_group')}">
            <span class="script-toggle__label" aria-hidden="true">${t('script_view_label')}</span>
            <button type="button" class="script-toggle__btn" data-view="native">${t('script_native')}</button>
            <button type="button" class="script-toggle__btn" data-view="romanized">${t('script_romanized')}</button>
            <button type="button" class="script-toggle__btn" data-view="both">${t('script_both')}</button>
          </div>` : ''}

          <div class="lesson-body">
            <span class="type-badge"></span>
            <p class="mode-note" hidden></p>
            <p class="explanation"></p>

            <dl class="fields"></dl>

            <div class="examples">
              <p class="example-text"></p>
              <button type="button" class="btn-speak"
                aria-label="${t('modal_aria_speak_example')}"
                ${!canSpeak ? 'disabled' : ''}>${t('modal_btn_speak')}</button>
            </div>

            <section class="drills-section" aria-label="${t('modal_aria_practice')}">
              <p class="drills-heading" aria-hidden="true">${t('modal_drills_heading')}</p>
              <div class="drills-list"></div>
            </section>
          </div>

          <div class="ratings" role="group" aria-label="${t('modal_aria_rate')}">
            <button type="button" data-rate="1">${t('modal_btn_rate_1')} <span class="sr-only">${t('modal_btn_rate_1_sr')}</span></button>
            <button type="button" data-rate="2">${t('modal_btn_rate_2')} <span class="sr-only">${t('modal_btn_rate_2_sr')}</span></button>
            <button type="button" data-rate="3">${t('modal_btn_rate_3')} <span class="sr-only">${t('modal_btn_rate_3_sr')}</span></button>
            <button type="button" data-rate="4">${t('modal_btn_rate_4')} <span class="sr-only">${t('modal_btn_rate_4_sr')}</span></button>
          </div>

          <p class="status"       role="status" aria-atomic="true"></p>
          <p class="status-error" role="alert"  aria-atomic="true"></p>
        </div>
      </div>
    `

    // ── Populate text safely via DOM (never innerHTML for API data) ───────────
    const sr  = this.shadowRoot
    const dir = this.#dir

    // Title — target-language word/phrase.
    const titleEl = sr.querySelector('#modal-title')
    titleEl.textContent = lesson.title
    this.#applyTargetLang(titleEl)

    sr.querySelector('.type-badge').textContent = lesson.type.replace('_', ' ')

    // Dictionary-mode signal — shown when the lesson was built from a
    // dictionary-depth plugin.  Informs the learner that no full parse was
    // performed without hiding any of the lesson content.
    const modeNote = sr.querySelector('.mode-note')
    if (lesson.lesson_mode === 'dictionary') {
      modeNote.textContent = t('modal_dict_mode_note')
      modeNote.removeAttribute('hidden')
    }

    // Explanation is always UI-language (English) — no lang/dir override.
    sr.querySelector('.explanation').textContent = lesson.explanation

    // Fields — definition list.
    // Labels from the backend identify whether each value is native script,
    // romanized, or a UI-language gloss, so we annotate accordingly.
    const dl = sr.querySelector('.fields')
    for (const field of lesson.fields ?? []) {
      const labelLower = field.label.toLowerCase()
      const layer = NATIVE_LABELS.has(labelLower)    ? 'native'
                  : ROMANIZED_LABELS.has(labelLower)  ? 'romanized'
                  : null

      const dt = document.createElement('dt')
      dt.className = 'field-label'
      dt.textContent = field.label

      const dd = document.createElement('dd')
      dd.className = 'field-value'
      dd.textContent = field.value

      if (layer) {
        // Annotate both label and value so the toggle hides the whole row.
        dt.dataset.layer = layer
        dd.dataset.layer = layer
      }

      // Apply target lang/dir to the value unless it's a known UI-language field.
      if (!UI_LANG_LABELS.has(labelLower)) {
        this.#applyTargetLang(dd)
      }

      dl.append(dt, dd)
    }

    // Example text — always target-language.
    const exampleEl = sr.querySelector('.example-text')
    exampleEl.textContent = exampleText
    this.#applyTargetLang(exampleEl)

    sr.querySelector('.btn-speak').addEventListener('click', () => {
      onSpeak?.(exampleText)
    })

    // Drills.
    const drillsContainer = sr.querySelector('.drills-list')
    for (let i = 0; i < (lesson.drills ?? []).length; i++) {
      const drillEl = this.#renderDrill(lesson.drills[i], i, onSpeak, onCheckResult)
      if (drillEl) drillsContainer.appendChild(drillEl)
    }

    // ── Enrichment sections (appended after drills) ────────────────────────────
    const lessonBody = sr.querySelector('.lesson-body')

    // Morphology axes — append as a compact definition section if present.
    const axes = lesson.morphology_axes ?? []
    if (axes.length) {
      const sec = document.createElement('section')
      sec.className = 'enrichment-section'
      const h = document.createElement('p')
      h.className = 'enrichment-heading'
      h.setAttribute('aria-hidden', 'true')
      h.textContent = t('modal_morphology_heading') || 'Morphology'
      const dl = document.createElement('dl')
      dl.className = 'fields'
      for (const ax of axes) {
        const dt = document.createElement('dt')
        dt.className = 'field-label'
        dt.textContent = ax.axis
        const dd = document.createElement('dd')
        dd.className = 'field-value'
        dd.textContent = ax.label || ax.value
        if (ax.gloss) {
          const small = document.createElement('small')
          small.style.color = 'var(--muted, GrayText)'
          small.style.display = 'block'
          small.style.fontSize = '0.75em'
          small.textContent = ax.gloss
          dd.appendChild(small)
        }
        dl.append(dt, dd)
      }
      sec.append(h, dl)
      lessonBody.appendChild(sec)
    }

    // Paradigms — each as a collapsible table.
    const paradigms = lesson.paradigms ?? []
    if (paradigms.length) {
      const sec = document.createElement('section')
      sec.className = 'enrichment-section'
      const h = document.createElement('p')
      h.className = 'enrichment-heading'
      h.setAttribute('aria-hidden', 'true')
      h.textContent = t('modal_paradigms_heading') || 'Paradigm'
      sec.appendChild(h)
      for (const p of paradigms) {
        const details = document.createElement('details')
        details.className = 'paradigm-wrap'
        const summary = document.createElement('summary')
        summary.textContent = p.title || (t('modal_paradigm_show') || 'Show paradigm')
        details.appendChild(summary)
        const cells = Array.isArray(p.cells) ? p.cells : []
        const rowAxis = p.row_axis
        const colAxis = p.col_axis
        if (rowAxis && colAxis && cells.length) {
          const rowVals = [], colVals = []
          for (const cell of cells) {
            const rv = cell.axes?.[rowAxis] || ''
            const cv = cell.axes?.[colAxis] || ''
            if (rv && !rowVals.includes(rv)) rowVals.push(rv)
            if (cv && !colVals.includes(cv)) colVals.push(cv)
          }
          const lookup = new Map(cells.map(c => [`${c.axes?.[rowAxis] || ''}|${c.axes?.[colAxis] || ''}`, c]))
          const table = document.createElement('table')
          table.className = 'paradigm-table'
          const thead = table.createTHead()
          const headRow = thead.insertRow()
          headRow.insertCell().scope = 'col'
          for (const cv of colVals) {
            const th = document.createElement('th')
            th.scope = 'col'
            th.textContent = cv
            headRow.appendChild(th)
          }
          const tbody = table.createTBody()
          for (const rv of rowVals) {
            const tr = tbody.insertRow()
            const rowHead = document.createElement('th')
            rowHead.scope = 'row'
            rowHead.textContent = rv
            tr.appendChild(rowHead)
            for (const cv of colVals) {
              const cell = lookup.get(`${rv}|${cv}`)
              const td = tr.insertCell()
              if (!cell) {
                td.textContent = '—'
              } else {
                td.className = cell.is_highlighted ? 'paradigm-cell--current' : ''
                const span = document.createElement('span')
                span.textContent = cell.form
                this.#applyTargetLang(span)
                td.appendChild(span)
                if (cell.is_highlighted) {
                  const sr2 = document.createElement('span')
                  sr2.setAttribute('style', 'position:absolute;inline-size:1px;block-size:1px;overflow:hidden;clip-path:inset(50%)')
                  sr2.textContent = ` (${t('modal_current_form') || 'current form'})`
                  td.appendChild(sr2)
                }
              }
            }
          }
          details.appendChild(table)
        }
        sec.appendChild(details)
      }
      lessonBody.appendChild(sec)
    }

    // Equivalents — compact list.
    const equivalents = lesson.equivalents ?? []
    if (equivalents.length) {
      const sec = document.createElement('section')
      sec.className = 'enrichment-section'
      const h = document.createElement('p')
      h.className = 'enrichment-heading'
      h.setAttribute('aria-hidden', 'true')
      h.textContent = t('modal_equivalents_heading') || 'Also expressed as'
      sec.appendChild(h)
      for (const eq of equivalents) {
        const card = document.createElement('div')
        card.className = 'equiv-card'
        const con = document.createElement('p')
        con.className = 'equiv-construction'
        con.textContent = eq.construction
        const langCode = eq.language_code || this.#language
        if (langCode) con.setAttribute('lang', langCode)
        card.appendChild(con)
        if (eq.note) {
          const note = document.createElement('p')
          note.className = 'equiv-note'
          note.textContent = eq.note
          card.appendChild(note)
        }
        sec.appendChild(card)
      }
      lessonBody.appendChild(sec)
    }

    // Contrasts — "don't confuse" warning cards.
    const contrasts = lesson.contrasts ?? []
    if (contrasts.length) {
      const sec = document.createElement('section')
      sec.className = 'enrichment-section'
      const h = document.createElement('p')
      h.className = 'enrichment-heading'
      h.setAttribute('aria-hidden', 'true')
      h.textContent = t('modal_contrasts_heading') || "Don't confuse with"
      sec.appendChild(h)
      for (const c of contrasts) {
        const card = document.createElement('div')
        card.className = 'contrast-card'
        const forms = document.createElement('div')
        forms.className = 'contrast-forms'
        const fa = document.createElement('bdi')
        fa.textContent = c.form_a
        this.#applyTargetLang(fa)
        const vs = document.createElement('span')
        vs.className = 'contrast-vs'
        vs.setAttribute('aria-hidden', 'true')
        vs.textContent = 'vs'
        const fb = document.createElement('bdi')
        fb.textContent = c.form_b
        this.#applyTargetLang(fb)
        forms.append(fa, vs, fb)
        const note = document.createElement('p')
        note.className = 'contrast-note'
        note.textContent = c.note
        card.append(forms, note)
        sec.appendChild(card)
      }
      lessonBody.appendChild(sec)
    }

    // Encountered vocabulary — compact gloss list.
    const encVocab = lesson.encountered_vocabulary ?? []
    if (encVocab.length) {
      const sec = document.createElement('section')
      sec.className = 'enrichment-section'
      const h = document.createElement('p')
      h.className = 'enrichment-heading'
      h.setAttribute('aria-hidden', 'true')
      h.textContent = t('modal_vocab_heading') || 'Context vocabulary'
      sec.appendChild(h)
      const ul = document.createElement('ul')
      ul.className = 'vocab-list'
      ul.setAttribute('aria-label', t('modal_vocab_heading') || 'Context vocabulary')
      for (const v of encVocab) {
        const li = document.createElement('li')
        li.className = 'vocab-item'
        const form = document.createElement('span')
        form.className = 'vocab-form'
        form.textContent = v.form
        this.#applyTargetLang(form)
        li.appendChild(form)
        if (v.lemma && v.lemma !== v.form) {
          const lemma = document.createElement('span')
          lemma.className = 'vocab-lemma'
          lemma.textContent = `(${v.lemma})`
          this.#applyTargetLang(lemma)
          li.appendChild(lemma)
        }
        if (v.gloss) {
          const gloss = document.createElement('span')
          gloss.className = 'vocab-gloss'
          gloss.textContent = `– ${v.gloss}`
          li.appendChild(gloss)
        }
        ul.appendChild(li)
      }
      sec.appendChild(ul)
      lessonBody.appendChild(sec)
    }

    // ── Script view toggle wiring ─────────────────────────────────────────────
    if (hasTranslit) {
      const lessonBody = sr.querySelector('.lesson-body')
      lessonBody.dataset.scriptView = this.#scriptView

      sr.querySelectorAll('.script-toggle__btn').forEach((btn) => {
        const active = btn.dataset.view === this.#scriptView
        btn.setAttribute('aria-pressed', String(active))
        btn.addEventListener('click', () => {
          this.#scriptView = btn.dataset.view
          lessonBody.dataset.scriptView = this.#scriptView
          sr.querySelectorAll('.script-toggle__btn').forEach((b) => {
            b.setAttribute('aria-pressed', String(b.dataset.view === this.#scriptView))
          })
        })
      })
    }

    // ── Overlay click closes ──────────────────────────────────────────────────
    sr.querySelector('[data-overlay]').addEventListener('click', (event) => {
      if (event.target === event.currentTarget) this.close()
    })

    sr.querySelector('[data-close]').addEventListener('click', () => this.close())

    // ── Recall rating buttons ─────────────────────────────────────────────────
    sr.querySelectorAll('[data-rate]').forEach((button) => {
      button.addEventListener('click', async () => {
        const statusEl      = sr.querySelector('.status')
        const errorEl       = sr.querySelector('.status-error')
        const ratingButtons = [...sr.querySelectorAll('[data-rate]')]

        ratingButtons.forEach((b) => { b.disabled = true })
        errorEl.textContent  = ''
        statusEl.textContent = ''
        queueMicrotask(() => { statusEl.textContent = t('job_saving') })

        try {
          const result = await onRate?.(objectId, Number(button.dataset.rate))
          const msg = result
            ? ti('modal_review_saved_next', { n: result.next_interval_days })
            : t('modal_review_saved')
          statusEl.textContent = ''
          queueMicrotask(() => { statusEl.textContent = msg })
        } catch (error) {
          statusEl.textContent = ''
          const msg = error instanceof Error ? error.message : t('modal_review_failed')
          errorEl.textContent  = ''
          queueMicrotask(() => { errorEl.textContent = msg })
        } finally {
          ratingButtons.forEach((b) => { b.disabled = false })
        }
      })
    })

    // sr-only inline style — shadow DOM cannot reach light-DOM utility classes.
    const srOnlyStyle = `
      position: absolute;
      inline-size: 1px; block-size: 1px;
      padding: 0; margin: -1px;
      overflow: hidden; clip-path: inset(50%);
      white-space: nowrap; border: 0;
    `
    sr.querySelectorAll('.sr-only').forEach((el) => el.setAttribute('style', srOnlyStyle))
  }

  // ── Language helpers ────────────────────────────────────────────────────────

  /** Apply lang + dir to an element that displays target-language text. */
  #applyTargetLang(el) {
    if (this.#language) el.setAttribute('lang', this.#language)
    if (this.#dir !== 'ltr') el.setAttribute('dir', this.#dir)
  }

  // ── Drill renderers ─────────────────────────────────────────────────────────
  // Answer data (answer_index, answer, correct) is kept in JS closure —
  // never embedded in data-attributes to avoid trivial DOM inspection.

  #renderDrill(drill, index, onSpeak, onCheckResult) {
    switch (drill.type) {
      case 'shadowing':       return this.#renderShadowing(drill, index, onSpeak)
      case 'multiple_choice': return this.#renderMultipleChoice(drill, index, onCheckResult)
      case 'fill_blank':      return this.#renderFillBlank(drill, index, onCheckResult)
      case 'recognition':     return this.#renderRecognition(drill, index, onCheckResult)
      default:                return null
    }
  }

  #renderShadowing(drill, index, onSpeak) {
    const canSpeak = 'speechSynthesis' in window
    const el = document.createElement('div')
    el.className = 'drill drill--shadowing'
    el.setAttribute('aria-label', ti('modal_aria_drill_shadowing', { n: index + 1 }))

    const prompt = document.createElement('p')
    prompt.className = 'drill-prompt'
    prompt.textContent = t('modal_say_aloud')

    const text = document.createElement('p')
    text.className = 'drill-text'
    text.textContent = drill.text
    // Shadowing text is always target-language.
    this.#applyTargetLang(text)

    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'btn-speak'
    btn.disabled = !canSpeak
    btn.textContent = t('modal_btn_speak')
    btn.setAttribute('aria-label', t('modal_aria_speak_drill'))
    btn.addEventListener('click', () => onSpeak?.(drill.text))

    el.append(prompt, text, btn)
    return el
  }

  #renderMultipleChoice(drill, index, onCheckResult) {
    const el = document.createElement('div')
    el.className = 'drill drill--mc'
    el.setAttribute('aria-label', ti('modal_aria_drill_mc', { n: index + 1 }))

    const prompt = document.createElement('p')
    prompt.className = 'drill-prompt'
    prompt.textContent = drill.prompt
    // MC prompts often contain target-language text (e.g. "What does X mean?").
    this.#applyTargetLang(prompt)

    const group = document.createElement('div')
    group.className = 'drill-options'
    group.setAttribute('role', 'group')
    group.setAttribute('aria-label', t('modal_aria_choose_one'))

    const feedback = document.createElement('p')
    feedback.className = 'drill-feedback'
    feedback.setAttribute('aria-live', 'polite')
    feedback.setAttribute('aria-atomic', 'true')

    let answered = false
    drill.options.forEach((optionText, i) => {
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.className = 'drill-option'
      btn.textContent = optionText
      btn.addEventListener('click', () => {
        if (answered) return
        answered = true
        const isCorrect = i === drill.answer_index

        group.querySelectorAll('.drill-option').forEach((b, j) => {
          b.disabled = true
          if (j === drill.answer_index) b.dataset.state = 'correct'
          else if (j === i && !isCorrect) b.dataset.state = 'wrong'
        })

        feedback.dataset.result = isCorrect ? 'correct' : 'wrong'
        if (isCorrect) {
          feedback.textContent = t('modal_feedback_correct')
        } else {
          // Wrap the answer in <bdi> so the Unicode bidi algorithm treats it
          // as an isolated run — prevents RTL answers from pushing the
          // surrounding LTR punctuation (quotes, period) to wrong positions.
          const bdi = document.createElement('bdi')
          bdi.textContent = drill.options[drill.answer_index]
          feedback.textContent = ''
          feedback.append(t('modal_feedback_wrong_intro'), bdi, t('modal_feedback_wrong_outro'))
        }
        onCheckResult?.({ index, type: 'multiple_choice', correct: isCorrect, answeredAt: new Date().toISOString() })
      })
      group.appendChild(btn)
    })

    el.append(prompt, group, feedback)
    return el
  }

  #renderFillBlank(drill, index, onCheckResult) {
    const el = document.createElement('div')
    el.className = 'drill drill--fill'
    el.setAttribute('aria-label', ti('modal_aria_drill_fill', { n: index + 1 }))

    const promptId = `drill-prompt-${index}`
    const prompt = document.createElement('p')
    prompt.id = promptId
    prompt.className = 'drill-prompt'
    // Replace ___ with an em-dash run for visual clarity.
    prompt.textContent = drill.prompt.replace('___', '\u2014\u2014\u2014')
    this.#applyTargetLang(prompt)

    const row = document.createElement('div')
    row.className = 'drill-input-row'

    const inputId = `drill-input-${index}`
    const input = document.createElement('input')
    input.type = 'text'
    input.id = inputId
    input.className = 'drill-input'
    // aria-labelledby associates the fill-blank prompt as the accessible name
    // for this input (SC 1.3.1 / 4.1.2).
    input.setAttribute('aria-labelledby', promptId)
    input.setAttribute('placeholder', t('modal_input_placeholder'))
    input.setAttribute('autocomplete', 'off')
    input.setAttribute('autocorrect', 'off')
    input.setAttribute('spellcheck', 'false')
    // Apply lang so the OS/IME offers the correct keyboard/input method.
    this.#applyTargetLang(input)

    const checkBtn = document.createElement('button')
    checkBtn.type = 'button'
    checkBtn.className = 'drill-check'
    checkBtn.textContent = t('modal_btn_check')

    const hint = document.createElement('p')
    hint.className = 'drill-feedback'
    hint.setAttribute('aria-live', 'polite')
    hint.setAttribute('aria-atomic', 'true')

    if (drill.hint) {
      const hintEl = document.createElement('p')
      hintEl.className = 'drill-feedback'
      hintEl.style.color = 'var(--muted, GrayText)'
      hintEl.textContent = `Hint: ${drill.hint}`
      row.appendChild(hintEl)
    }

    let answered = false
    const check = () => {
      if (answered) return
      const value = input.value.trim()
      if (!value) return
      answered = true
      input.disabled = true
      checkBtn.disabled = true

      const isCorrect = value.toLowerCase() === drill.answer.toLowerCase()
      hint.dataset.result = isCorrect ? 'correct' : 'wrong'
      if (isCorrect) {
        hint.textContent = t('modal_feedback_correct')
      } else {
        // <bdi> isolates the target-language answer from the LTR wrapper so
        // typographic quotes don't flip sides for RTL answer strings.
        const bdi = document.createElement('bdi')
        bdi.textContent = drill.answer
        hint.textContent = ''
        hint.append(t('modal_feedback_wrong_intro'), bdi, t('modal_feedback_wrong_outro'))
      }
      onCheckResult?.({ index, type: 'fill_blank', correct: isCorrect, answeredAt: new Date().toISOString() })
    }

    checkBtn.addEventListener('click', check)
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); check() }
    })

    row.append(input, checkBtn)
    el.append(prompt, row, hint)
    return el
  }

  #renderRecognition(drill, index, onCheckResult) {
    const el = document.createElement('div')
    el.className = 'drill drill--rec'
    el.setAttribute('aria-label', ti('modal_aria_drill_recognition', { n: index + 1 }))

    const prompt = document.createElement('p')
    prompt.className = 'drill-prompt'
    prompt.textContent = drill.statement
    this.#applyTargetLang(prompt)

    const group = document.createElement('div')
    group.className = 'drill-options'
    group.setAttribute('role', 'group')
    group.setAttribute('aria-label', t('modal_aria_true_false'))

    const feedback = document.createElement('p')
    feedback.className = 'drill-feedback'
    feedback.setAttribute('aria-live', 'polite')
    feedback.setAttribute('aria-atomic', 'true')

    let answered = false
    ;[{ label: t('modal_true'), value: true }, { label: t('modal_false'), value: false }].forEach(({ label, value }) => {
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.className = 'drill-option'
      btn.textContent = label
      btn.dataset.boolValue = String(value)
      btn.addEventListener('click', () => {
        if (answered) return
        answered = true
        const isCorrect = value === drill.correct

        group.querySelectorAll('.drill-option').forEach((b) => {
          b.disabled = true
          const btnValue = b.dataset.boolValue === 'true'
          if (btnValue === drill.correct) b.dataset.state = 'correct'
          else if (btnValue === value && !isCorrect) b.dataset.state = 'wrong'
        })

        feedback.dataset.result = isCorrect ? 'correct' : 'wrong'
        feedback.textContent = isCorrect
          ? t('modal_feedback_correct')
          : (drill.correct ? t('modal_feedback_rec_true') : t('modal_feedback_rec_false'))
        onCheckResult?.({ index, type: 'recognition', correct: isCorrect, answeredAt: new Date().toISOString() })
      })
      group.appendChild(btn)
    })

    el.append(prompt, group, feedback)
    return el
  }
}

customElements.define('mnemosyne-modal', MnemosyneModal)
