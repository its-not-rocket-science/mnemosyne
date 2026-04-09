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

    // Inert all sibling body children so background content is unreachable
    // by AT virtual cursor and keyboard.  aria-modal alone is insufficient
    // across all screen reader / browser combinations.
    this.#inertedElements = []
    for (const child of document.body.children) {
      if (child !== this && !child.hasAttribute('inert')) {
        child.setAttribute('inert', '')
        this.#inertedElements.push(child)
      }
    }

    // Focus the dialog container (tabindex="-1") so the screen reader
    // announces "dialog, <title>" immediately on open.  Users then Tab
    // to reach the first interactive button.
    this.shadowRoot.querySelector('[role="dialog"]')?.focus()
  }

  close() {
    this.isOpen = false
    document.body.style.overflow = ''
    document.removeEventListener('keydown', this.onKeydown)

    // Restore background accessibility before returning focus, so the
    // focus target is reachable if it was previously inerted.
    for (const el of this.#inertedElements) {
      el.removeAttribute('inert')
    }
    this.#inertedElements = []

    this.render()

    // previouslyFocused is often a mnemosyne-pill host with delegatesFocus:true,
    // so calling .focus() on the host delegates into the shadow button.
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
      // Collect only enabled interactive elements; exclude the dialog container
      // itself (tabindex="-1") since it is not in the natural tab sequence.
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
          /* Prevent scroll-chaining to the page body on mobile. */
          overscroll-behavior: contain;
        }

        .dialog {
          inline-size: min(42rem, 100%);
          max-block-size: 90dvh;
          overflow-y: auto;
          background: Canvas;
          color: CanvasText;
          border-radius: 1rem;
          /* clamp keeps padding comfortable on narrow screens / 200% zoom. */
          padding: clamp(1rem, 4vw, 1.5rem);
          box-shadow: 0 1rem 2rem color-mix(in srgb, black 25%, transparent);
        }

        /* tabindex="-1" makes the dialog focusable for the AT announcement on
           open; suppress the visible ring since this is a programmatic focus. */
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
          font-size: clamp(1rem, 2.5vw + 0.5rem, 1.25rem);
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
          /* 2.75rem ≈ 44 CSS px touch target per WCAG 2.5.8 */
          min-block-size: 2.75rem;
        }

        .close {
          padding-inline: 0.9rem;
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
          padding-inline: 0.85rem;
        }

        .actions button {
          padding-inline: 0.85rem;
        }

        .content {
          margin-block-start: 1rem;
          overflow-wrap: break-word;
        }

        /*
         * Two live regions handle different urgency levels:
         *
         * .status   role="status"  — polite, for progress and success.
         * .status-error  role="alert"   — assertive, for failures.
         *
         * Both are always present so the browser registers them before any
         * announcement is needed (live regions must exist in the DOM first).
         */
        .status,
        .status-error {
          min-block-size: 1.5rem;
          margin-block-start: 0.75rem;
        }

        .status {
          color: var(--muted, GrayText);
        }

        .status-error {
          /* Visible even when empty to keep layout stable. */
          color: var(--error-color, oklch(0.50 0.2 29));
        }

        .status-error:empty {
          display: none;
        }
      </style>

      <div class="overlay" data-overlay>
        <div class="dialog" role="dialog" aria-modal="true"
             aria-labelledby="modal-title" tabindex="-1">

          <div class="header">
            <h2 id="modal-title"></h2>
            <button type="button" class="close" data-close>Close</button>
          </div>

          <div class="content">${state.html}</div>

          <div class="actions">
            <button type="button" data-speak
              ${!canSpeak || !state.exampleText ? 'disabled' : ''}>
              Speak example
            </button>
          </div>

          <div class="ratings" role="group" aria-label="Rate your recall">
            <button type="button" data-rate="1">Again <span class="sr-only">(did not remember)</span></button>
            <button type="button" data-rate="2">Hard  <span class="sr-only">(remembered with difficulty)</span></button>
            <button type="button" data-rate="3">Good  <span class="sr-only">(remembered correctly)</span></button>
            <button type="button" data-rate="4">Easy  <span class="sr-only">(remembered effortlessly)</span></button>
          </div>

          <!-- role="status": polite announcements (progress, success) -->
          <p class="status" role="status" aria-atomic="true"></p>
          <!-- role="alert": assertive announcements (errors) -->
          <p class="status-error" role="alert" aria-atomic="true"></p>
        </div>
      </div>
    `

    // Set title via textContent — never innerHTML — to avoid XSS from API strings.
    this.shadowRoot.querySelector('#modal-title').textContent = state.title

    // Clicking the backdrop (overlay) but not the dialog closes the modal.
    this.shadowRoot.querySelector('[data-overlay]')?.addEventListener('click', (event) => {
      if (event.target === event.currentTarget) this.close()
    })

    this.shadowRoot.querySelector('[data-close]')?.addEventListener('click', () => this.close())

    this.shadowRoot.querySelector('[data-speak]')?.addEventListener('click', () => {
      state.onSpeak?.(state.exampleText)
    })

    this.shadowRoot.querySelectorAll('[data-rate]').forEach((button) => {
      button.addEventListener('click', async () => {
        const statusEl      = this.shadowRoot.querySelector('.status')
        const errorEl       = this.shadowRoot.querySelector('.status-error')
        const ratingButtons = [...this.shadowRoot.querySelectorAll('[data-rate]')]

        // Disable all rating buttons while the save is in flight.
        ratingButtons.forEach((b) => { b.disabled = true })

        // Clear both regions, then set the progress message in the polite one.
        errorEl.textContent  = ''
        statusEl.textContent = ''
        queueMicrotask(() => { statusEl.textContent = 'Saving…' })

        try {
          const result = await state.onRate?.(state.objectId, Number(button.dataset.rate))
          const msg = result
            ? `Saved. Next review in ${result.next_interval_days} day(s).`
            : 'Review saved.'
          statusEl.textContent = ''
          queueMicrotask(() => { statusEl.textContent = msg })
        } catch (error) {
          // Route errors to the assertive region so they interrupt the user.
          statusEl.textContent = ''
          const msg = error instanceof Error ? error.message : 'Review failed.'
          errorEl.textContent = ''
          queueMicrotask(() => { errorEl.textContent = msg })
        } finally {
          ratingButtons.forEach((b) => { b.disabled = false })
        }
      })
    })

    // Inline sr-only style — the component is self-contained and cannot rely
    // on the light-DOM .sr-only utility class reaching into the shadow tree.
    const srOnlyStyle = `
      position: absolute;
      inline-size: 1px; block-size: 1px;
      padding: 0; margin: -1px;
      overflow: hidden; clip-path: inset(50%);
      white-space: nowrap; border: 0;
    `
    this.shadowRoot.querySelectorAll('.sr-only').forEach((el) => {
      el.setAttribute('style', srOnlyStyle)
    })
  }
}

customElements.define('mnemosyne-modal', MnemosyneModal)
