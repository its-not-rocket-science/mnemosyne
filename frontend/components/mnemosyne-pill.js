// One OKLCH reference color per type.
// color-mix blends it with the system Canvas color so pills adapt to
// both light and dark mode without any media-query duplication.
const TYPE_META = {
  vocabulary:  { icon: '📗', label: 'Vocabulary', ref: 'oklch(0.50 0.20 142)' },
  conjugation: { icon: '🔧', label: 'Verb',        ref: 'oklch(0.50 0.20 240)' },
  agreement:   { icon: '🧩', label: 'Agreement',   ref: 'oklch(0.50 0.15  50)' },
  idiom:       { icon: '💬', label: 'Idiom',        ref: 'oklch(0.50 0.20 300)' },
  grammar:     { icon: '📐', label: 'Grammar',      ref: 'oklch(0.50 0.15  90)' },
  nuance:      { icon: '🎭', label: 'Nuance',       ref: 'oklch(0.50 0.20  20)' },
}

export class MnemosynePill extends HTMLElement {
  static observedAttributes = ['type', 'label', 'object-id', 'language']

  constructor() {
    super()
    this.attachShadow({ mode: 'open' })
    this.handleClick = this.handleClick.bind(this)
  }

  connectedCallback() {
    this.render()
  }

  attributeChangedCallback() {
    this.render()
  }

  handleClick() {
    this.dispatchEvent(new CustomEvent('lesson-open', {
      bubbles: true,
      composed: true,
      detail: {
        objectId: this.getAttribute('object-id'),
        language: this.getAttribute('language'),
        type: this.getAttribute('type'),
        label: this.getAttribute('label'),
      },
    }))
  }

  render() {
    if (!this.shadowRoot) return
    const type = this.getAttribute('type') || 'vocabulary'
    const text = this.getAttribute('label') || ''
    const meta = TYPE_META[type] || TYPE_META.vocabulary

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: inline-block;
        }

        button {
          display: inline-flex;
          align-items: center;
          gap: 0.45rem;
          border: 1px solid color-mix(in oklch, ${meta.ref} 35%, Canvas);
          border-radius: 999px;
          padding: 0.45rem 0.8rem;
          background: color-mix(in oklch, ${meta.ref} 18%, Canvas);
          color: CanvasText;
          font: inherit;
          cursor: pointer;
        }

        button:focus-visible {
          outline: 3px solid color-mix(in oklch, ${meta.ref} 55%, transparent);
          outline-offset: 2px;
        }

        .icon {
          inline-size: 1.2rem;
          text-align: center;
        }
      </style>
      <button type="button" aria-label="${meta.label} lesson: ${text}">
        <span class="icon" aria-hidden="true">${meta.icon}</span>
        <span>${text}</span>
      </button>
    `
    this.shadowRoot.querySelector('button')?.addEventListener('click', this.handleClick)
  }
}

customElements.define('mnemosyne-pill', MnemosynePill)
