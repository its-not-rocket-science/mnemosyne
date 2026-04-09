// One OKLCH reference color per type.
// color-mix blends it with the system Canvas color so pills adapt to
// both light and dark mode without any media-query duplication.
const TYPE_META = {
  vocabulary:  { icon: '📗', label: 'Vocabulary', badge: 'vocab', ref: 'oklch(0.50 0.20 142)' },
  conjugation: { icon: '🔧', label: 'Verb',        badge: 'verb',  ref: 'oklch(0.50 0.20 240)' },
  agreement:   { icon: '🧩', label: 'Agreement',   badge: 'agr',   ref: 'oklch(0.50 0.15  50)' },
  idiom:       { icon: '💬', label: 'Idiom',        badge: 'idiom', ref: 'oklch(0.50 0.20 300)' },
  grammar:     { icon: '📐', label: 'Grammar',      badge: 'gram',  ref: 'oklch(0.50 0.15  90)' },
  nuance:      { icon: '🎭', label: 'Nuance',       badge: 'nuance',ref: 'oklch(0.50 0.20  20)' },
}

export class MnemosynePill extends HTMLElement {
  static observedAttributes = ['type', 'label', 'object-id', 'language']

  constructor() {
    super()
    // delegatesFocus: true — focusing the host element (e.g. after modal close)
    // delegates to the first focusable child in the shadow tree.
    this.attachShadow({ mode: 'open', delegatesFocus: true })
    this.handleClick = this.handleClick.bind(this)
  }

  connectedCallback() {
    this.render()
  }

  attributeChangedCallback(name, oldValue, newValue) {
    // Skip no-op attribute updates to avoid spurious re-renders.
    if (oldValue === newValue) return
    this.render()
  }

  handleClick() {
    this.dispatchEvent(new CustomEvent('lesson-open', {
      bubbles: true,
      composed: true,
      detail: {
        objectId: this.getAttribute('object-id'),
        language: this.getAttribute('language'),
        type:     this.getAttribute('type'),
        label:    this.getAttribute('label'),
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
          gap: 0.4rem;
          border: 1px solid color-mix(in oklch, ${meta.ref} 35%, Canvas);
          border-radius: 999px;
          padding: 0.45rem 0.8rem;
          background: color-mix(in oklch, ${meta.ref} 18%, Canvas);
          color: CanvasText;
          font: inherit;
          cursor: pointer;
        }

        /* Solid focus ring — color-mix with transparent fails WCAG 2.4.11 */
        button:focus-visible {
          outline: 3px solid color-mix(in oklch, ${meta.ref} 90%, CanvasText);
          outline-offset: 3px;
        }

        .icon {
          inline-size: 1.2rem;
          text-align: center;
        }

        /* Visible non-color type indicator so type is never communicated by
           color or icon alone.  Visually small; not aria-hidden so that it
           supplements the button's aria-label for AT users who may override
           label computation.  The button aria-label is the primary AT signal. */
        .type-badge {
          font-size: 0.68em;
          font-weight: 700;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          opacity: 0.65;
          padding-inline-start: 0.15rem;
        }
      </style>
      <button type="button" aria-label="${meta.label} lesson: ${text}">
        <span class="icon" aria-hidden="true">${meta.icon}</span>
        <span>${text}</span>
        <span class="type-badge" aria-hidden="true">${meta.badge}</span>
      </button>
    `
    this.shadowRoot.querySelector('button')?.addEventListener('click', this.handleClick)
  }
}

customElements.define('mnemosyne-pill', MnemosynePill)
