/**
 * reading-state.js — Reading-session state shared across mode coordinators.
 *
 * main.js previously kept all of this as bare module-level `let`/`const`
 * bindings that every section read and wrote directly. Splitting main.js
 * into separate coordinator modules means this state needs a home that
 * isn't owned by any single coordinator's DOM, since explorer.js, lesson.js,
 * review.js and shared.js all read or write parts of it. Plain values are
 * exposed as accessor functions (not raw `let` exports) because ES module
 * bindings are read-only from the importer's side — an importer can observe
 * live updates but cannot assign through the binding itself.
 *
 * This is pure state, not DOM. Each coordinator continues to query its own
 * DOM elements independently; only the underlying values live here.
 */

// ── Annotation depth (subtle / learning / deep) ───────────────────────────────

export const ANNOTATION_DEPTH_KEY = 'mn-annotation-depth'
export const DEPTH_FALLBACK = 'learning'

export const ANNOTATION_DEPTH_MODEL = {
  subtle: new Set(['vocabulary']),
  learning: new Set(['vocabulary', 'conjugation', 'agreement', 'inflection', 'grammar']),
  deep: new Set([
    'vocabulary',
    'conjugation',
    'agreement',
    'inflection',
    'grammar',
    'script',
    'transliteration',
    'idiom',
    'nuance',
    'phrase_family',
    'etymology',
    'memory_map',
    'cultural_note',
  ]),
}

let _currentDepth = localStorage.getItem(ANNOTATION_DEPTH_KEY) || DEPTH_FALLBACK
if (!ANNOTATION_DEPTH_MODEL[_currentDepth]) _currentDepth = DEPTH_FALLBACK

export function currentDepth() { return _currentDepth }
export function setCurrentDepth(depth) { _currentDepth = depth }

// ── Annotation filters (session filter pills + search) ────────────────────────

export const FILTER_CYCLE = [null, 'vocab', 'grammar', 'idioms', 'literary', 'etymology']

let _activeFilterTypes      = null  // Set<string> when filtered, null = show all
let _activeFilterCategories = null  // Set<string> of active category IDs, null = all
let _activeLockedTypes      = new Set(
  JSON.parse(localStorage.getItem('mn-cat-lock-types') || '[]')
)
let _activeLockedCatIds     = JSON.parse(localStorage.getItem('mn-cat-locks') || '[]')
let _activeSearchTerm       = ''   // lowercase string; '' = no search filter
let _filterCycleIdx         = 0    // index into FILTER_CYCLE; 0 = show all

export function activeFilterTypes() { return _activeFilterTypes }
export function setActiveFilterTypes(v) { _activeFilterTypes = v }
export function activeFilterCategories() { return _activeFilterCategories }
export function setActiveFilterCategories(v) { _activeFilterCategories = v }
export function activeLockedTypes() { return _activeLockedTypes }
export function setActiveLockedTypes(v) { _activeLockedTypes = v }
export function activeLockedCatIds() { return _activeLockedCatIds }
export function setActiveLockedCatIds(v) { _activeLockedCatIds = v }
export function activeSearchTerm() { return _activeSearchTerm }
export function setActiveSearchTerm(v) { _activeSearchTerm = v }
export function filterCycleIndex() { return _filterCycleIdx }
export function setFilterCycleIndex(v) { _filterCycleIdx = v }

// ── Follow-along (auto-scroll active sentence during playback) ────────────────

let _isFollowAlongEnabled = false

export function isFollowAlongEnabled() { return _isFollowAlongEnabled }
export function setFollowAlongEnabled(v) { _isFollowAlongEnabled = v }

// ── Current rendered sentences (set on parse/load, read by playback + drills) ─

let _currentSentences = []
let _currentTtsTag    = ''

export function currentSentences() { return _currentSentences }
export function setCurrentSentences(v) { _currentSentences = v }
export function currentTtsTag() { return _currentTtsTag }
export function setCurrentTtsTag(v) { _currentTtsTag = v }

// ── Currently open sentence (set when a lesson/annotation is opened) ──────────

let _currentSentenceIdx = -1

export function currentSentenceIndex() { return _currentSentenceIdx }
export function setCurrentSentenceIndex(v) { _currentSentenceIdx = v }

// ── Language capabilities (populated by explorer.js's loadLanguages()) ────────

export const languageCapabilities = new Map()

let _currentCaps = null
export function currentCaps() { return _currentCaps }
export function setCurrentCaps(v) { _currentCaps = v }

// ── Current document title/eyebrow (set by explorer.js's picker confirm and
// library.js's _loadSource; read by lesson.js's renderResults) ────────────────

let _currentDocumentTitle   = null
let _currentDocumentEyebrow = null

export function currentDocumentTitle() { return _currentDocumentTitle }
export function setCurrentDocumentTitle(v) { _currentDocumentTitle = v }
export function currentDocumentEyebrow() { return _currentDocumentEyebrow }
export function setCurrentDocumentEyebrow(v) { _currentDocumentEyebrow = v }

// ── Current source URL / filename (set by explorer.js's picker intake; read
// by lesson.js for the now-playing track title) ───────────────────────────────

let _currentSourceUrl = null
let _currentFilename  = null

export function currentSourceUrl() { return _currentSourceUrl }
export function setCurrentSourceUrl(v) { _currentSourceUrl = v }
export function currentFilename() { return _currentFilename }
export function setCurrentFilename(v) { _currentFilename = v }
