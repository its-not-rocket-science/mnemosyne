export class MnemosyneModal extends HTMLElement {
  // Tracks elements that were made inert on modal open so we can restore them.
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

  open({ title, html, objectId, exampleText, onRate, onSpeak }) {
    this.isOpen = true
    this.previouslyFocused = document.activeElement
    this.render({ title, html, objectId, exampleText, onRate, onSpeak })
    document.body.style.overflow = 'hidden'
    document.addEventListener('keydown', this.onKeydown)

    // Inert all sibling body children so AT cannot reach background content.
    this.#inertedElements = []
    for (const child of document.body.children) {
      if (child !== this && !child.hasAttribute('inert')) {
        child.setAttribute('inert', '')
        this.#inertedElements.push(child)
      }
    }

    // Focus the dialog container so AT announces "dialog, <title>".
    // Users then Tab to reach the first interactive button.
    this.shadowRoot.querySelector('[role="dialog"]')?.focus()
  }

  close() {
    this.isOpen = false
    document.body.style.overflow = ''
    document.removeEventListener('keydown', this.onKeydown)

    // Restore background accessibility.
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
      // Only interactive buttons (not the dialog container itself) cycle.
      const focusables = [
        ...this.shadowRoot.querySelectorAll(
          'button:not([disabled]), [href], input:not([disabled]), ' +
          'select:not([disabled]), textarea:not([disabled]), ' +
          '[tabindex]:not([tabindex="-1"])'
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

    const canSpeak = 'speechSynthesis' in window

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          color-scheme: light dark;
        }

        .overlay {
          position: fixed;
          inset: 0;
          background: color-mix(in srgb, black 55%, transparent);
          display: grid;
          place-items: center;
          padding: 1rem;
          z-index: 1000;
        }

        .dialog {
          inline-size: min(42rem, 100%);
          max-block-size: 90dvh;
          overflow: auto;
          background: Canvas;
          color: CanvasText;
          border-radius: 1rem;
          padding: 1.5rem;
          box-shadow: 0 1rem 2rem color-mix(in srgb, black 25%, transparent);
        }

        /* tabindex="-1" makes the dialog focusable for initial AT announcement
           without putting it in the natural tab sequence. */
        .dialog:focus {
          outline: none;
        }

        .header {
          display: flex;
          justify-content: space-between;
          align-items: start;
          gap: 1rem;
        }

        h2 {
          margin: 0;
          font-size: 1.25rem;
        }

        .close,
        .actions button,
        .ratings button {
          border: 1px solid color-mix(in srgb, CanvasText 25%, transparent);
          background: transparent;
          border-radius: 999px;
          color: inherit;
          font: inherit;
          cursor: pointer;
        }

        .close {
          padding: 0.5rem 0.8rem;
          flex-shrink: 0;
        }

        .close:focus-visible,
        .actions button:focus-visible,
        .ratings button:focus-visible {
          outline: 3px solid var(--accent, #3557ff);
          outline-offset: 3px;
        }

        .close:disabled,
        .actions button:disabled,
        .ratings button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .actions,
        .ratings {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          margin-block-start: 1rem;
        }

        .ratings button {
          padding: 0.6rem 0.85rem;
        }

        .actions button {
          padding: 0.6rem 0.85rem;
        }

        .content {
          margin-block-start: 1rem;
        }

        /* role="status" implies aria-live="polite" and aria-atomic="true".
           aria-atomic is set explicitly to match the main page status pattern. */
        .status {
          min-block-size: 1.5rem;
          color: GrayText;
          margin-block-start: 0.75rem;
        }
      </style>

      <div class="overlay" data-overlay>
        <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="modal-title" tabindex="-1">
          <div class="header">
            <h2 id="modal-title"></h2>
            <button type="button" class="close" data-close>Close</button>
          </div>

          <div class="content">${state.html}</div>

          <div class="actions">
            <button type="button" data-speak ${!canSpeak || !state.exampleText ? 'disabled' : ''}>
              Speak example
            </button>
          </div>

          <div class="ratings" role="group" aria-label="Rate recall">
            <button type="button" data-rate="1">Again</button>
            <button type="button" data-rate="2">Hard</button>
            <button type="button" data-rate="3">Good</button>
            <button type="button" data-rate="4">Easy</button>
          </div>

          <p class="status" role="status" aria-atomic="true"></p>
        </div>
      </div>
    `

    // Use textContent to avoid XSS from API-sourced strings.
    this.shadowRoot.querySelector('#modal-title').textContent = state.title

    // Overlay click closes the modal; clicks inside .dialog do not propagate.
    this.shadowRoot.querySelector('.overlay')?.addEventListener('click', (event) => {
      if (event.target === event.currentTarget) this.close()
    })

    this.shadowRoot.querySelector('[data-close]')?.addEventListener('click', () => this.close())
    this.shadowRoot.querySelector('[data-speak]')?.addEventListener('click', () => {
      state.onSpeak?.(state.exampleText)
    })

    this.shadowRoot.querySelectorAll('[data-rate]').forEach((button) => {
      button.addEventListener('click', async () => {
        const statusEl      = this.shadowRoot.querySelector('.status')
        const ratingButtons = [...this.shadowRoot.querySelectorAll('[data-rate]')]

        // Disable buttons while save is in flight so double-submit is impossible.
        ratingButtons.forEach((b) => { b.disabled = true })
        statusEl.textContent = ''
        queueMicrotask(() => { statusEl.textContent = 'Saving review…' })

        try {
          const result = await state.onRate?.(state.objectId, Number(button.dataset.rate))
          const msg = result
            ? `Review saved. Next review in ${result.next_interval_days} day(s).`
            : 'Review saved.'
          statusEl.textContent = ''
          queueMicrotask(() => { statusEl.textContent = msg })
        } catch (error) {
          const msg = error instanceof Error ? error.message : 'Review failed.'
          statusEl.textContent = ''
          queueMicrotask(() => { statusEl.textContent = msg })
        } finally {
          ratingButtons.forEach((b) => { b.disabled = false })
        }
      })
    })
  }
}

customElements.define('mnemosyne-modal', MnemosyneModal)
