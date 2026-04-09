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
    // delegatesFocus: true — focusing the host (e.g. on modal close) delegates
    // to the shadow button automatically.
    this.attachShadow({ mode: 'open', delegatesFocus: true })
    this.handleClick = this.handleClick.bind(this)
  }

  connectedCallback() {
    this.render()
  }

  attributeChangedCallback(name, oldValue, newValue) {
    // During HTML parsing, attributeChangedCallback fires for each attribute
    // before connectedCallback.  Guard here so we don't render into a detached
    // shadow root before the element is live in the document.
    if (!this.isConnected) return
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

    // Build the shadow DOM structure.  aria-label is NOT interpolated into
    // the innerHTML string — setAttribute handles all escaping and avoids
    // any risk of breaking the attribute if `text` contains quote characters.
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
          /* 2.75rem ≈ 44 CSS px — WCAG 2.5.8 minimum touch target */
          min-block-size: 2.75rem;
          padding-inline: 0.8rem;
          background: color-mix(in oklch, ${meta.ref} 18%, Canvas);
          color: CanvasText;
          font: inherit;
          cursor: pointer;
        }

        /* Solid focus ring — semi-transparent outline fails WCAG 2.4.11 3:1
           non-text contrast requirement against adjacent colors. */
        button:focus-visible {
          outline: 3px solid color-mix(in oklch, ${meta.ref} 90%, CanvasText);
          outline-offset: 3px;
        }

        .icon {
          inline-size: 1.2rem;
          text-align: center;
        }

        /* Visible non-color type indicator: type is signalled by icon shape,
           badge text, AND background tint — never by color alone.
           aria-hidden keeps it out of the AT name computation; the button's
           aria-label is the canonical accessible name. */
        .type-badge {
          font-size: 0.68em;
          font-weight: 700;
          letter-spacing: 0.04em;
          text-transform: uppercase;
          opacity: 0.65;
          padding-inline-start: 0.1rem;
        }
      </style>
      <button type="button">
        <span class="icon" aria-hidden="true">${meta.icon}</span>
        <span>${meta.badge}</span>
        <span aria-hidden="true">·</span>
        <span>${text}</span>
      </button>
    `

    // Set aria-label via setAttribute so the browser handles escaping.
    // Interpolating user-supplied `text` directly into innerHTML would break
    // if the value contains quote characters.
    const btn = this.shadowRoot.querySelector('button')
    btn.setAttribute('aria-label', `${meta.label} lesson: ${text}`)
    btn.addEventListener('click', this.handleClick)
  }
}

customElements.define('mnemosyne-pill', MnemosynePill)
