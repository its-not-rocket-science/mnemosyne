// One OKLCH reference color per type.
// color-mix blends it with the system Canvas color so pills adapt to
// both light and dark mode without any media-query duplication.
const TYPE_META = {
  vocabulary:       { icon: '📗', label: 'Vocabulary',      badge: 'vocab',  ref: 'oklch(0.50 0.20 142)' },
  conjugation:      { icon: '🔧', label: 'Verb',             badge: 'verb',   ref: 'oklch(0.50 0.20 240)' },
  agreement:        { icon: '🧩', label: 'Agreement',        badge: 'agr',    ref: 'oklch(0.50 0.15  50)' },
  idiom:            { icon: '💬', label: 'Idiom',             badge: 'idiom',  ref: 'oklch(0.50 0.20 300)' },
  grammar:          { icon: '📐', label: 'Grammar',           badge: 'gram',   ref: 'oklch(0.50 0.15  90)' },
  nuance:           { icon: '🎭', label: 'Nuance',            badge: 'nuance', ref: 'oklch(0.50 0.20  20)' },
  // v2 types
  script:           { icon: '✍️', label: 'Script',           badge: 'script',  ref: 'oklch(0.50 0.18 200)' },
  transliteration:  { icon: '🔤', label: 'Transliteration',  badge: 'roma',    ref: 'oklch(0.50 0.15 170)' },
  // v4 types
  phrase_family:    { icon: '🔗', label: 'Phrase family',    badge: 'phrase',  ref: 'oklch(0.50 0.20 330)' },
}

export class MnemosynePill extends HTMLElement {
  static observedAttributes = ['type', 'label', 'object-id', 'language', 'dir', 'confidence']

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
    const type       = this.getAttribute('type')       || 'vocabulary'
    const text       = this.getAttribute('label')      || ''
    const language   = this.getAttribute('language')   || ''
    const dir        = this.getAttribute('dir')        || null
    const confidence = parseFloat(this.getAttribute('confidence') ?? '1')
    const meta       = TYPE_META[type] || TYPE_META.vocabulary

    // Confidence tiers used for visual de-emphasis:
    //   low      < 0.72  — dashed border, reduced opacity
    //   moderate 0.72–0.87 — slightly reduced opacity
    //   high     ≥ 0.88  — full display (default)
    const confTier = confidence < 0.72 ? 'low' : confidence < 0.88 ? 'moderate' : 'high'
    const opacity  = confTier === 'low' ? '0.65' : confTier === 'moderate' ? '0.82' : '1'
    const borderStyle = confTier === 'low' ? 'dashed' : 'solid'

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
          /* 60% reference color gives noticeably more contrast against Canvas
             than the prior 35%; exact ratio varies by type color and OS
             Canvas value — verify in browser for each type. SC 1.4.11. */
          border: 1px ${borderStyle} color-mix(in oklch, ${meta.ref} 60%, Canvas);
          border-radius: 999px;
          /* 2.75rem ≈ 44 CSS px — WCAG 2.5.8 minimum touch target */
          min-block-size: 2.75rem;
          padding-inline: 0.8rem;
          background: color-mix(in oklch, ${meta.ref} 18%, Canvas);
          color: CanvasText;
          font: inherit;
          cursor: pointer;
          opacity: ${opacity};
        }

        /* Solid focus ring — semi-transparent outline fails WCAG 2.4.11 3:1
           non-text contrast requirement against adjacent colors. */
        button:focus-visible {
          outline: 3px solid color-mix(in oklch, ${meta.ref} 90%, CanvasText);
          outline-offset: 3px;
          /* Restore full opacity on focus so the ring is clearly visible. */
          opacity: 1;
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

        /* The label span inherits the button's direction.  We keep the
           button itself LTR so the icon/badge/separator stay in a consistent
           left-to-right order regardless of language; only the label text is
           marked as the target language so the bidi algorithm handles it. */
        .pill-label { unicode-bidi: isolate; }
      </style>
      <button type="button">
        <span class="icon" aria-hidden="true">${meta.icon}</span>
        <span>${meta.badge}</span>
        <span aria-hidden="true">·</span>
        <span class="pill-label"></span>
      </button>
    `

    const btn      = this.shadowRoot.querySelector('button')
    const labelEl  = this.shadowRoot.querySelector('.pill-label')

    // Set text content and aria-label via DOM (never via innerHTML) to avoid
    // any risk of injection if the label value contains markup characters.
    labelEl.textContent = text
    btn.setAttribute('aria-label', `${meta.label} lesson: ${text}`)

    // lang on the button so AT announces the accessible name in the correct
    // language / with the correct TTS voice.
    if (language) btn.setAttribute('lang', language)

    // dir on the label span only — NOT on the whole button — so the
    // icon / badge / separator retain their LTR order in RTL languages.
    // unicode-bidi:isolate (set in CSS above) ensures the label's bidi
    // context is isolated from the surrounding flex layout.
    if (dir && dir !== 'ltr') labelEl.setAttribute('dir', dir)

    btn.addEventListener('click', this.handleClick)
  }
}

customElements.define('mnemosyne-pill', MnemosynePill)
