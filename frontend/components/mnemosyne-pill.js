const TYPE_META = {
  vocabulary: { icon: '📗', label: 'Vocabulary', bg: '#dff7df' },
  conjugation: { icon: '🔧', label: 'Verb', bg: '#dbeafe' },
  agreement: { icon: '🧩', label: 'Agreement', bg: '#ffe8cc' },
  idiom: { icon: '💬', label: 'Idiom', bg: '#f3e8ff' },
  grammar: { icon: '📐', label: 'Grammar', bg: '#fff3bf' },
  nuance: { icon: '🎭', label: 'Nuance', bg: '#ffd6d6' },
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
          border: 1px solid rgba(0, 0, 0, 0.15);
          border-radius: 999px;
          padding: 0.45rem 0.8rem;
          background: ${meta.bg};
          color: #111;
          font: inherit;
          cursor: pointer;
        }

        button:focus-visible {
          outline: 3px solid rgba(53, 87, 255, 0.4);
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
