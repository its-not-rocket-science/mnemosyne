export class MnemosyneModal extends HTMLElement {
  #inertedElements = []

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

  open({ lesson, objectId, onRate, onSpeak }) {
    this.isOpen = true
    this.previouslyFocused = document.activeElement
    this.render({ lesson, objectId, onRate, onSpeak })
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

    const { lesson, objectId, onRate, onSpeak } = state
    const canSpeak = 'speechSynthesis' in window
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

        .header {
          display: flex;
          justify-content: space-between;
          align-items: start;
          gap: 1rem;
        }

        h2 {
          margin: 0;
          font-size: clamp(1rem, 2.5vw + 0.5rem, 1.25rem);
        }

        /* ── buttons ── */
        button {
          border: 1px solid color-mix(in srgb, CanvasText 25%, transparent);
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

        /* ── lesson body ── */
        .lesson-body {
          margin-block-start: 1rem;
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
          margin-block-end: 0.75rem;
          color: var(--muted, GrayText);
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
        }

        .drill-text {
          font-size: 1.1rem;
          font-weight: 600;
          margin: 0 0 0.6rem;
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
          .drill-option[data-state="correct"] {
            background: oklch(0.30 0.10 145);
            border-color: oklch(0.55 0.18 145);
            color: oklch(0.85 0.08 145);
          }
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
          min-inline-size: 8rem;
          block-size: 2.75rem;
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
          .drill-feedback[data-result="correct"] { color: oklch(0.70 0.15 145); }
        }

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

        @media (prefers-reduced-motion: reduce) {
          .status { transition: none !important; }
        }
      </style>

      <div class="overlay" data-overlay>
        <div class="dialog" role="dialog" aria-modal="true"
             aria-labelledby="modal-title" tabindex="-1">

          <div class="header">
            <h2 id="modal-title"></h2>
            <button type="button" class="close" data-close>Close</button>
          </div>

          <div class="lesson-body">
            <span class="type-badge"></span>
            <p class="explanation"></p>

            <dl class="fields"></dl>

            <div class="examples">
              <p class="example-text"></p>
              <button type="button" class="btn-speak"
                ${!canSpeak ? 'disabled' : ''}>Speak</button>
            </div>

            <section class="drills-section" aria-label="Practice drills">
              <p class="drills-heading" aria-hidden="true">Practice</p>
              <div class="drills-list"></div>
            </section>
          </div>

          <div class="ratings" role="group" aria-label="Rate your recall">
            <button type="button" data-rate="1">Again <span class="sr-only">(did not remember)</span></button>
            <button type="button" data-rate="2">Hard  <span class="sr-only">(remembered with difficulty)</span></button>
            <button type="button" data-rate="3">Good  <span class="sr-only">(remembered correctly)</span></button>
            <button type="button" data-rate="4">Easy  <span class="sr-only">(remembered effortlessly)</span></button>
          </div>

          <p class="status"      role="status" aria-atomic="true"></p>
          <p class="status-error" role="alert"  aria-atomic="true"></p>
        </div>
      </div>
    `

    // ── Populate text safely via DOM (never innerHTML for API data) ───────────
    const sr = this.shadowRoot

    sr.querySelector('#modal-title').textContent = lesson.title
    sr.querySelector('.type-badge').textContent  = lesson.type.replace('_', ' ')
    sr.querySelector('.explanation').textContent = lesson.explanation

    // Fields — definition list
    const dl = sr.querySelector('.fields')
    for (const field of lesson.fields ?? []) {
      const dt = document.createElement('dt')
      dt.className = 'field-label'
      dt.textContent = field.label
      const dd = document.createElement('dd')
      dd.className = 'field-value'
      dd.textContent = field.value
      dl.append(dt, dd)
    }

    // Example text + speak
    sr.querySelector('.example-text').textContent = exampleText
    sr.querySelector('.btn-speak').addEventListener('click', () => {
      onSpeak?.(exampleText)
    })

    // Drills
    const drillsContainer = sr.querySelector('.drills-list')
    for (let i = 0; i < (lesson.drills ?? []).length; i++) {
      const drillEl = this.#renderDrill(lesson.drills[i], i, onSpeak)
      if (drillEl) drillsContainer.appendChild(drillEl)
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
        queueMicrotask(() => { statusEl.textContent = 'Saving\u2026' })

        try {
          const result = await onRate?.(objectId, Number(button.dataset.rate))
          const msg = result
            ? `Saved. Next review in ${result.next_interval_days} day(s).`
            : 'Review saved.'
          statusEl.textContent = ''
          queueMicrotask(() => { statusEl.textContent = msg })
        } catch (error) {
          statusEl.textContent = ''
          const msg = error instanceof Error ? error.message : 'Review failed.'
          errorEl.textContent  = ''
          queueMicrotask(() => { errorEl.textContent = msg })
        } finally {
          ratingButtons.forEach((b) => { b.disabled = false })
        }
      })
    })

    // sr-only inline style — shadow DOM cannot reach light-DOM utility classes
    const srOnlyStyle = `
      position: absolute;
      inline-size: 1px; block-size: 1px;
      padding: 0; margin: -1px;
      overflow: hidden; clip-path: inset(50%);
      white-space: nowrap; border: 0;
    `
    sr.querySelectorAll('.sr-only').forEach((el) => el.setAttribute('style', srOnlyStyle))
  }

  // ── Drill renderers ─────────────────────────────────────────────────────────
  // Each renderer creates DOM nodes and attaches event listeners.
  // Note: answer data (answer_index, answer, correct) is kept in JS closure —
  // it is NOT embedded in data-attributes to avoid trivial DOM inspection.
  // For a self-study tool this is still visible in memory, which is fine.

  #renderDrill(drill, index, onSpeak) {
    switch (drill.type) {
      case 'shadowing':      return this.#renderShadowing(drill, index, onSpeak)
      case 'multiple_choice': return this.#renderMultipleChoice(drill, index)
      case 'fill_blank':     return this.#renderFillBlank(drill, index)
      case 'recognition':    return this.#renderRecognition(drill, index)
      default:               return null
    }
  }

  #renderShadowing(drill, index, onSpeak) {
    const canSpeak = 'speechSynthesis' in window
    const el = document.createElement('div')
    el.className = 'drill drill--shadowing'
    el.setAttribute('aria-label', `Practice drill ${index + 1}: shadowing`)

    const prompt = document.createElement('p')
    prompt.className = 'drill-prompt'
    prompt.textContent = 'Say aloud:'

    const text = document.createElement('p')
    text.className = 'drill-text'
    text.textContent = drill.text

    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'btn-speak'
    btn.disabled = !canSpeak
    btn.textContent = 'Speak'
    btn.addEventListener('click', () => onSpeak?.(drill.text))

    el.append(prompt, text, btn)
    return el
  }

  #renderMultipleChoice(drill, index) {
    const el = document.createElement('div')
    el.className = 'drill drill--mc'
    el.setAttribute('aria-label', `Practice drill ${index + 1}: multiple choice`)

    const prompt = document.createElement('p')
    prompt.className = 'drill-prompt'
    prompt.textContent = drill.prompt

    const group = document.createElement('div')
    group.className = 'drill-options'
    group.setAttribute('role', 'group')
    group.setAttribute('aria-label', 'Choose one')

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

        // Mark each option as correct/wrong/neutral
        group.querySelectorAll('.drill-option').forEach((b, j) => {
          b.disabled = true
          if (j === drill.answer_index) b.dataset.state = 'correct'
          else if (j === i && !isCorrect) b.dataset.state = 'wrong'
        })

        feedback.dataset.result = isCorrect ? 'correct' : 'wrong'
        feedback.textContent = isCorrect
          ? '\u2713 Correct!'
          : `\u2717 The answer is \u201c${drill.options[drill.answer_index]}\u201d.`
      })
      group.appendChild(btn)
    })

    el.append(prompt, group, feedback)
    return el
  }

  #renderFillBlank(drill, index) {
    const el = document.createElement('div')
    el.className = 'drill drill--fill'
    el.setAttribute('aria-label', `Practice drill ${index + 1}: fill in the blank`)

    const prompt = document.createElement('p')
    prompt.className = 'drill-prompt'
    // Replace ___ with a visible blank marker
    prompt.textContent = drill.prompt.replace('___', '\u2014\u2014\u2014')

    const row = document.createElement('div')
    row.className = 'drill-input-row'

    const inputId = `drill-input-${index}`
    const input = document.createElement('input')
    input.type = 'text'
    input.id = inputId
    input.className = 'drill-input'
    input.setAttribute('placeholder', 'Type your answer')
    input.setAttribute('autocomplete', 'off')
    input.setAttribute('autocorrect', 'off')
    input.setAttribute('spellcheck', 'false')

    const checkBtn = document.createElement('button')
    checkBtn.type = 'button'
    checkBtn.className = 'drill-check'
    checkBtn.textContent = 'Check'

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
      hint.textContent = isCorrect
        ? '\u2713 Correct!'
        : `\u2717 The answer is \u201c${drill.answer}\u201d.`
    }

    checkBtn.addEventListener('click', check)
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); check() }
    })

    row.append(input, checkBtn)
    el.append(prompt, row, hint)
    return el
  }

  #renderRecognition(drill, index) {
    const el = document.createElement('div')
    el.className = 'drill drill--rec'
    el.setAttribute('aria-label', `Practice drill ${index + 1}: true or false`)

    const prompt = document.createElement('p')
    prompt.className = 'drill-prompt'
    prompt.textContent = drill.statement

    const group = document.createElement('div')
    group.className = 'drill-options'
    group.setAttribute('role', 'group')
    group.setAttribute('aria-label', 'True or false?')

    const feedback = document.createElement('p')
    feedback.className = 'drill-feedback'
    feedback.setAttribute('aria-live', 'polite')
    feedback.setAttribute('aria-atomic', 'true')

    let answered = false
    ;[{ label: 'True', value: true }, { label: 'False', value: false }].forEach(({ label, value }) => {
      const btn = document.createElement('button')
      btn.type = 'button'
      btn.className = 'drill-option'
      btn.textContent = label
      btn.addEventListener('click', () => {
        if (answered) return
        answered = true
        const isCorrect = value === drill.correct

        group.querySelectorAll('.drill-option').forEach((b) => {
          b.disabled = true
          const btnValue = b.textContent === 'True'
          if (btnValue === drill.correct) b.dataset.state = 'correct'
          else if (btnValue === value && !isCorrect) b.dataset.state = 'wrong'
        })

        feedback.dataset.result = isCorrect ? 'correct' : 'wrong'
        feedback.textContent = isCorrect
          ? '\u2713 Correct!'
          : `\u2717 That\u2019s ${drill.correct ? 'true' : 'false'}.`
      })
      group.appendChild(btn)
    })

    el.append(prompt, group, feedback)
    return el
  }
}

customElements.define('mnemosyne-modal', MnemosyneModal)
