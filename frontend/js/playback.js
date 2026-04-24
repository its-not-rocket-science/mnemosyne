/**
 * playback.js — centralised TTS playback engine and voice selection.
 *
 * Canonical type declarations live in `./types.js`:
 *   PlaybackState, PlaybackScope, TTSProvider, TTSVoice, TTSRequest, PlaybackStateEvent
 *
 * @see ./types.js
 */

/** @typedef {import('./types.js').PlaybackState}    PlaybackState    */
/** @typedef {import('./types.js').PlaybackScope}    PlaybackScope    */
/** @typedef {import('./types.js').TTSProvider}      TTSProvider      */
/** @typedef {import('./types.js').TTSRequest}       TTSRequest       */
/** @typedef {import('./types.js').PlaybackStateEvent} PlaybackStateEvent */

/**
 * Pick the best available Web Speech voice for a BCP-47 language tag.
 * Prefers exact language match and native (non-Google/Microsoft) voices.
 * @param {string} langTag
 * @returns {SpeechSynthesisVoice|null}
 */
export function pickVoice(langTag) {
  const voices = window.speechSynthesis.getVoices()
  if (!voices.length) return null

  const lower  = langTag.toLowerCase()
  const prefix = lower.split('-')[0]

  const quality = v => {
    const n = v.name.toLowerCase()
    if (n.includes('google') || n.includes('microsoft')) return 0
    return 1
  }

  const candidates = voices
    .filter(v => v.lang.toLowerCase().startsWith(prefix))
    .sort((a, b) => {
      const aExact = a.lang.toLowerCase() === lower ? 0 : 1
      const bExact = b.lang.toLowerCase() === lower ? 0 : 1
      if (aExact !== bExact) return aExact - bExact
      return quality(a) - quality(b)
    })

  return candidates[0] ?? null
}

export class PlaybackEngine extends EventTarget {
  /** @type {PlaybackState}          */ #state = 'idle'
  /** @type {TTSRequest[]}           */ #queue = []
  /** @type {number}                 */ #index = -1
  /** @type {number}                 */ #rate  = 1.0
  /** @type {SpeechSynthesisVoice|null} */ #preferredVoice = null

  get rate() { return this.#rate }
  set rate(v) { this.#rate = Math.max(0.1, Math.min(10, Number(v) || 1.0)) }

  /** @param {SpeechSynthesisVoice|null} voice */
  setPreferredVoice(voice) { this.#preferredVoice = voice }

  /** @returns {PlaybackState} */
  get state()  { return this.#state }
  /** @returns {number} */
  get index()  { return this.#index }
  /** @returns {TTSRequest|null} */
  get current(){ return this.#queue[this.#index] ?? null }
  /** @returns {number} */
  get total()  { return this.#queue.length }

  /**
   * Speak a single item immediately, replacing any current queue.
   * @param {string} text
   * @param {string} langTag
   * @param {PlaybackScope} [scope='phrase']
   * @param {number} [sentenceIndex=-1]
   */
  speak(text, langTag, scope = 'phrase', sentenceIndex = -1) {
    this.#queue = [{ text, langTag, scope, index: sentenceIndex }]
    this.#index = 0
    this.#startCurrent()
  }

  /**
   * Queue and play all sentences sequentially.
   * @param {Array<{text:string,langTag:string}>} sentences
   */
  playAll(sentences) {
    if (!sentences.length) return
    this.#queue = sentences.map((s, i) => ({
      text:    s.text,
      langTag: s.langTag,
      scope:   'full-text',
      index:   i,
    }))
    this.#index = 0
    this.#startCurrent()
  }

  pause() {
    if (this.#state !== 'playing') return
    window.speechSynthesis.pause()
    this.#setState('paused')
  }

  resume() {
    if (this.#state !== 'paused') return
    window.speechSynthesis.resume()
    this.#setState('playing')
  }

  stop() {
    window.speechSynthesis.cancel()
    this.#queue = []
    this.#index = -1
    this.#setState('idle')
  }

  next() {
    window.speechSynthesis.cancel()
    if (this.#index < this.#queue.length - 1) {
      this.#index++
      this.#startCurrent()
    } else {
      this.#queue = []
      this.#index = -1
      this.#setState('idle')
    }
  }

  prev() {
    window.speechSynthesis.cancel()
    if (this.#index > 0) this.#index--
    this.#startCurrent()
  }

  togglePause() {
    if (this.#state === 'playing')      this.pause()
    else if (this.#state === 'paused')  this.resume()
  }

  /**
   * Update state and dispatch to all listeners.
   * @param {PlaybackState} newState
   * @fires PlaybackEngine#state-change {PlaybackStateEvent}
   */
  #setState(newState) {
    this.#state = newState
    this.dispatchEvent(new CustomEvent('state-change', {
      detail: {
        state:   newState,
        current: this.current,
        index:   this.#index,
        total:   this.#queue.length,
      },
    }))
  }

  #startCurrent() {
    const req = this.#queue[this.#index]
    if (!req || !('speechSynthesis' in window)) {
      this.#setState('idle')
      return
    }

    const go = () => {
      const utt  = new SpeechSynthesisUtterance(req.text)
      utt.lang   = req.langTag
      utt.rate   = this.#rate
      const voice = this.#preferredVoice ?? pickVoice(req.langTag)
      if (voice) utt.voice = voice

      utt.onend = () => {
        if (this.#index < this.#queue.length - 1) {
          this.#index++
          this.#startCurrent()
        } else {
          this.#queue = []
          this.#index = -1
          this.#setState('idle')
        }
      }

      utt.onerror = (e) => {
        if (e.error === 'interrupted' || e.error === 'canceled') return
        this.#queue = []
        this.#index = -1
        this.#setState('idle')
      }

      window.speechSynthesis.cancel()
      window.speechSynthesis.speak(utt)
      this.#setState('playing')
    }

    if (window.speechSynthesis.getVoices().length > 0) {
      go()
    } else {
      window.speechSynthesis.addEventListener('voiceschanged', go, { once: true })
    }
  }
}

export const playbackEngine = new PlaybackEngine()
