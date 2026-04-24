/**
 * @fileoverview Shared JSDoc type declarations for Mnemosyne frontend.
 *
 * No runtime code — import this module only for type checking in IDEs /
 * TypeScript-style JSDoc tooling.  All other modules reference these types
 * via `@type {import('./types.js').Foo}` or by co-locating their own
 * narrower typedefs.
 */

// ── Phrase-family data model ──────────────────────────────────────────────────

/**
 * Relationship between a matched surface form and the canonical phrase.
 * Mirrors `MatchType` in `backend/dictionary/phrase_families.py`.
 *
 * @typedef {'exact'
 *   | 'orthographic_variant'
 *   | 'modernized_variant'
 *   | 'inflectional_variant'
 *   | 'misquotation'
 *   | 'blend'
 *   | 'allusion'
 *   | 'confusable_not_same'
 * } MatchType
 */

/**
 * One surface form from the variants list (serialised from PhraseVariant).
 * Confusable-not-same variants are separated into `PhraseFamilyLessonData.confusable_forms`.
 *
 * @typedef {Object} PhraseVariantDict
 * @property {string}    surface     - Display surface form.
 * @property {MatchType} match_type  - Relationship to canonical form.
 * @property {string}    note        - Empty string when absent (never null in API).
 */

/**
 * Within-family confusable entry (match_type === 'confusable_not_same').
 * These are separated from `variants` so the UI can apply warning styling.
 *
 * @typedef {Object} ConfusableFormDict
 * @property {string} surface
 * @property {string} note
 */

/**
 * `lesson_data` payload for a `phrase_family` lesson object.
 * Set by `phrase_families._family_to_candidate()`.
 *
 * @typedef {Object} PhraseFamilyLessonData
 * @property {string}                family_id        - Stable slug (e.g. "all_that_glitters").
 * @property {string}                canonical_form   - Most widely cited surface form.
 * @property {string}                matched_variant  - Surface span as it appeared in text.
 * @property {MatchType}             match_type       - How the matched span relates to canonical.
 * @property {string}               [match_type_note] - Inline annotation for this specific variant.
 * @property {string}                meaning          - Phrase meaning.
 * @property {string}                register         - "neutral" | "literary" | "formal" | "informal" | "archaic"
 * @property {string}               [origin]          - Historical / etymological prose.
 * @property {string}               [source_text]     - Primary attribution / citation line.
 * @property {string}               [why_it_matters]  - Learner-facing significance.
 * @property {PhraseVariantDict[]}   variants         - All non-confusable variants.
 * @property {ConfusableFormDict[]} [confusable_forms] - Within-family confusable surfaces.
 * @property {string[]}             [confusables]     - IDs of cross-family confusable families.
 * @property {string[]}             [tags]            - Taxonomy tags.
 */

// ── Lesson response ───────────────────────────────────────────────────────────

/**
 * One field row in a lesson panel.
 *
 * @typedef {Object} LessonField
 * @property {string} label
 * @property {string} value
 */

/**
 * @typedef {'multiple_choice'|'fill_blank'|'recognition'|'shadowing'} DrillType
 */

/**
 * Base drill shape (discriminate on `type` to get the full shape).
 *
 * @typedef {Object} Drill
 * @property {DrillType} type
 * @property {string}   [prompt]
 */

/**
 * Full structured lesson response from `GET /api/lesson/{id}`.
 *
 * @typedef {Object} LessonResponse
 * @property {string}       id
 * @property {string}       type              - LearnableType value.
 * @property {string}       title
 * @property {string}       explanation
 * @property {LessonField[]} fields
 * @property {string[]}     examples
 * @property {Drill[]}      drills
 * @property {string}       lesson_mode       - LessonTemplate value.
 * @property {string}      [language_code]
 * @property {string}      [script_direction]
 * @property {Object}      [lesson_data]      - Raw lesson_data blob (type-specific).
 */

// ── Playback system ───────────────────────────────────────────────────────────

/**
 * @typedef {'idle'|'playing'|'paused'} PlaybackState
 */

/**
 * @typedef {'sentence'|'full-text'|'phrase'} PlaybackScope
 */

/**
 * @typedef {'web-speech'|'none'} TTSProvider
 */

/**
 * A resolved Web Speech API voice with the fields Mnemosyne uses.
 *
 * @typedef {Object} TTSVoice
 * @property {string}  lang
 * @property {string}  name
 * @property {boolean} localService
 * @property {boolean} default
 */

/**
 * One item in the playback queue.
 *
 * @typedef {Object} TTSRequest
 * @property {string}        text          - Text to speak.
 * @property {string}        langTag       - BCP-47 tag (e.g. "en", "en-GB").
 * @property {PlaybackScope} scope         - Granularity of the utterance.
 * @property {number}        index         - Sentence index; -1 for non-sentence scopes.
 */

/**
 * Payload of the `state-change` CustomEvent dispatched by PlaybackEngine.
 *
 * @typedef {Object} PlaybackStateEvent
 * @property {PlaybackState}   state    - Current engine state.
 * @property {TTSRequest|null} current  - Active queue item, or null when idle.
 * @property {number}          index    - Current queue position (0-based); -1 when idle.
 * @property {number}          total    - Total items in queue.
 */

export {}
