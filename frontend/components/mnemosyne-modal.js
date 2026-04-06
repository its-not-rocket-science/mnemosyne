export class MnemosyneModal extends HTMLElement {
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
    const first = this.shadowRoot.querySelector('[data-autofocus]') || this.shadowRoot.querySelector('button')
    first?.focus()
  }

  close() {
    this.isOpen = false
    document.body.style.overflow = ''
    document.removeEventListener('keydown', this.onKeydown)
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
      const focusables = [...this.shadowRoot.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')]
        .filter((node) => !node.hasAttribute('disabled'))
      if (focusables.length === 0) return
      const first = focusables[0]
      const last = focusables[focusables.length - 1]
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
      this.shadowRoot.innerHTML = `<style>:host{display:block}</style>`
      return
    }

    this.shadowRoot.innerHTML = `
      <style>
        .overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.5);
          display: grid;
          place-items: center;
          padding: 1rem;
          z-index: 1000;
        }

        .dialog {
          inline-size: min(42rem, 100%);
          max-block-size: 90vh;
          overflow: auto;
          background: Canvas;
          color: CanvasText;
          border-radius: 1rem;
          padding: 1rem;
          box-shadow: 0 1rem 2rem rgba(0, 0, 0, 0.2);
        }

        .header {
          display: flex;
          justify-content: space-between;
          align-items: start;
          gap: 1rem;
        }

        .close {
          border: 1px solid rgba(0, 0, 0, 0.2);
          background: transparent;
          border-radius: 999px;
          padding: 0.5rem 0.8rem;
          cursor: pointer;
        }

        .actions,
        .ratings {
          display: flex;
          flex-wrap: wrap;
          gap: 0.5rem;
          margin-block-start: 1rem;
        }

        .ratings button,
        .actions button {
          border: 1px solid rgba(0, 0, 0, 0.2);
          background: transparent;
          border-radius: 999px;
          padding: 0.6rem 0.85rem;
          cursor: pointer;
        }

        .content {
          margin-block-start: 1rem;
        }

        .status {
          min-block-size: 1.5rem;
          color: GrayText;
          margin-block-start: 0.75rem;
        }
      </style>

      <div class="overlay">
        <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div class="header">
            <h2 id="modal-title">${state.title}</h2>
            <button type="button" class="close" data-close data-autofocus>Close</button>
          </div>

          <div class="content">${state.html}</div>

          <div class="actions">
            <button type="button" data-speak ${state.exampleText ? '' : 'disabled'}>Speak example</button>
          </div>

          <div class="ratings" aria-label="Rate recall">
            <button type="button" data-rate="1">Again</button>
            <button type="button" data-rate="2">Hard</button>
            <button type="button" data-rate="3">Good</button>
            <button type="button" data-rate="4">Easy</button>
          </div>

          <p class="status" aria-live="polite"></p>
        </div>
      </div>
    `

    this.shadowRoot.querySelector('[data-close]')?.addEventListener('click', () => this.close())
    this.shadowRoot.querySelector('[data-speak]')?.addEventListener('click', () => state.onSpeak?.(state.exampleText))
    this.shadowRoot.querySelectorAll('[data-rate]').forEach((button) => {
      button.addEventListener('click', async () => {
        const status = this.shadowRoot.querySelector('.status')
        status.textContent = 'Saving review…'
        try {
          const result = await state.onRate?.(state.objectId, Number(button.dataset.rate))
          if (result) {
            status.textContent = `Next review in ${result.next_interval_days} day(s).`
          } else {
            status.textContent = 'Review saved.'
          }
        } catch (error) {
          status.textContent = error instanceof Error ? error.message : 'Review failed.'
        }
      })
    })
  }
}

customElements.define('mnemosyne-modal', MnemosyneModal)
