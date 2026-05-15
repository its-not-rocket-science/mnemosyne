import assert from 'node:assert/strict'
import { buildLessonPipelinePayload, validateLessonPipelinePayload } from '../js/lesson-pipeline.js'

// ── helpers ──────────────────────────────────────────────────────────────────

function makeAnnotation(label, type = 'vocabulary') {
  return { id: `obj-${label}`, label, type, canonical_form: label.toLowerCase(), confidence: 0.85 }
}

function makeParseData(sentences) {
  return { sentences }
}

// ── Spanish sample ────────────────────────────────────────────────────────────
// Regression: source text must never be replaced by extracted term labels.
// The Spanish bug: NLP over-split produced "sol montañas viajeros" per card
// instead of the full original sentence.

const SPANISH_S1 = 'El sol brillaba sobre las montañas mientras los viajeros descansaban.'
const SPANISH_S2 = 'El agua fría refrescaba sus pies cansados después de un largo camino.'
const SPANISH_SOURCE = `${SPANISH_S1} ${SPANISH_S2}`

const spanishParseData = makeParseData([
  { text: SPANISH_S1, learnable_objects: [makeAnnotation('sol'), makeAnnotation('montañas'), makeAnnotation('viajeros')] },
  { text: SPANISH_S2, learnable_objects: [makeAnnotation('agua'), makeAnnotation('pies')] },
])

const spanishPayload = buildLessonPipelinePayload({
  sourceText: SPANISH_SOURCE,
  normalizedText: SPANISH_SOURCE,
  parseData: spanishParseData,
})

// Source text is the original passage — not a word salad of extracted terms.
assert.equal(spanishPayload.sourceText, SPANISH_SOURCE)
assert.notEqual(spanishPayload.sourceText, spanishPayload.highlightedTerms.join(' '))

// Sentence texts preserved verbatim from parseData — NOT replaced by term labels.
assert.equal(spanishPayload.sentences[0].text, SPANISH_S1)
assert.equal(spanishPayload.sentences[1].text, SPANISH_S2)
assert.notEqual(spanishPayload.sentences[0].text, 'sol montañas viajeros')

// Highlighted terms are term labels, NOT sentence texts.
assert.deepEqual(spanishPayload.highlightedTerms, ['sol', 'montañas', 'viajeros', 'agua', 'pies'])
assert.ok(!spanishPayload.highlightedTerms.includes(SPANISH_S1))
assert.ok(!spanishPayload.highlightedTerms.includes(SPANISH_S2))

// All highlighted terms appear in sourceText (no phantom terms).
for (const term of spanishPayload.highlightedTerms) {
  assert.ok(SPANISH_SOURCE.toLowerCase().includes(term.toLowerCase()), `term "${term}" missing from sourceText`)
}

// Tokens come from sentence.text whitespace-split — NOT from highlightedTerms.
const termSet = new Set(spanishPayload.highlightedTerms)
const tokenSet = new Set(spanishPayload.tokens)
assert.ok(tokenSet.has('El'))        // article preserved in tokens
assert.ok(tokenSet.has('brillaba'))  // non-annotated word preserved
assert.ok(tokenSet.has('sol'))       // annotated word also in tokens
// Tokens include non-term words — they are not just the term list.
assert.ok(tokenSet.size > termSet.size)

// ── French sample ─────────────────────────────────────────────────────────────

const FRENCH_S1 = 'Presque tout a disparu dans la nuit sombre et froide.'
const FRENCH_S2 = 'Les étoiles brillaient seules au-dessus des collines.'
const FRENCH_SOURCE = `${FRENCH_S1} ${FRENCH_S2}`

const frenchPayload = buildLessonPipelinePayload({
  sourceText: FRENCH_SOURCE,
  normalizedText: FRENCH_SOURCE,
  parseData: makeParseData([
    { text: FRENCH_S1, learnable_objects: [makeAnnotation('nuit'), makeAnnotation('froide')] },
    { text: FRENCH_S2, learnable_objects: [makeAnnotation('étoiles'), makeAnnotation('collines')] },
  ]),
})

assert.equal(frenchPayload.sourceText, FRENCH_SOURCE)
assert.equal(frenchPayload.sentences[0].text, FRENCH_S1)
assert.equal(frenchPayload.sentences[1].text, FRENCH_S2)
assert.deepEqual(frenchPayload.highlightedTerms, ['nuit', 'froide', 'étoiles', 'collines'])
for (const term of frenchPayload.highlightedTerms) {
  assert.ok(FRENCH_SOURCE.toLowerCase().includes(term.toLowerCase()), `fr term "${term}" missing from sourceText`)
}

// ── English sample ────────────────────────────────────────────────────────────

const ENGLISH_S1 = 'The quick brown fox jumps over the lazy dog.'
const ENGLISH_S2 = 'Pack my box with five dozen liquor jugs.'
const ENGLISH_SOURCE = `${ENGLISH_S1} ${ENGLISH_S2}`

const englishPayload = buildLessonPipelinePayload({
  sourceText: ENGLISH_SOURCE,
  normalizedText: ENGLISH_SOURCE,
  parseData: makeParseData([
    { text: ENGLISH_S1, learnable_objects: [makeAnnotation('fox'), makeAnnotation('jumps')] },
    { text: ENGLISH_S2, learnable_objects: [makeAnnotation('liquor'), makeAnnotation('jugs')] },
  ]),
})

assert.equal(englishPayload.sourceText, ENGLISH_SOURCE)
assert.equal(englishPayload.sentences[0].text, ENGLISH_S1)
assert.deepEqual(englishPayload.highlightedTerms, ['fox', 'jumps', 'liquor', 'jugs'])

// ── URL in source text ────────────────────────────────────────────────────────
// URLs in the source passage must not corrupt highlightedTerms or
// cause sourceText to be replaced by domain tokens.

const URL_SOURCE = 'Visit https://www.example.com/hablar for more info about the verb hablar.'
const urlPayload = buildLessonPipelinePayload({
  sourceText: URL_SOURCE,
  normalizedText: URL_SOURCE,
  parseData: makeParseData([
    {
      text: URL_SOURCE,
      learnable_objects: [makeAnnotation('hablar')],
    },
  ]),
})

// sourceText is the full original string including the URL.
assert.equal(urlPayload.sourceText, URL_SOURCE)
assert.ok(urlPayload.sourceText.includes('https://www.example.com/hablar'))

// highlightedTerms contains only the annotated term, not URL fragments.
assert.deepEqual(urlPayload.highlightedTerms, ['hablar'])
assert.ok(!urlPayload.highlightedTerms.some(t => t.includes('://')))
assert.ok(!urlPayload.highlightedTerms.some(t => t.includes('example.com')))

// tokens include the URL as a token (from sentence text split), not sanitised away.
assert.ok(urlPayload.tokens.some(t => t.includes('example.com')))

// ── sourceText is independent of annotations ──────────────────────────────────
// Changing annotations must not affect sourceText or sentence texts.

const baseSource = 'Una frase de ejemplo para la prueba.'
const noAnns = buildLessonPipelinePayload({
  sourceText: baseSource,
  normalizedText: baseSource,
  parseData: makeParseData([{ text: baseSource, learnable_objects: [] }]),
})
const withAnns = buildLessonPipelinePayload({
  sourceText: baseSource,
  normalizedText: baseSource,
  parseData: makeParseData([
    { text: baseSource, learnable_objects: [makeAnnotation('frase'), makeAnnotation('ejemplo')] },
  ]),
})
assert.equal(noAnns.sourceText, withAnns.sourceText)
assert.equal(noAnns.sentences[0].text, withAnns.sentences[0].text)

// ── suggestedNextPassage propagation ─────────────────────────────────────────

const withNext = buildLessonPipelinePayload({
  sourceText: SPANISH_SOURCE,
  normalizedText: SPANISH_SOURCE,
  parseData: spanishParseData,
  suggestedNextPassage: { language: 'es', text: 'Siguiente pasaje de práctica.' },
})
assert.equal(withNext.suggestedNextPassage.language, 'es')
assert.equal(withNext.suggestedNextPassage.text, 'Siguiente pasaje de práctica.')

// Null suggestedNextPassage is allowed.
const withNull = buildLessonPipelinePayload({
  sourceText: SPANISH_SOURCE,
  normalizedText: SPANISH_SOURCE,
  parseData: spanishParseData,
  suggestedNextPassage: null,
})
assert.equal(withNull.suggestedNextPassage, null)

// Non-object suggestedNextPassage must throw.
assert.throws(
  () => validateLessonPipelinePayload({ ...spanishPayload, suggestedNextPassage: 'es' }),
  /suggestedNextPassage must be an object/,
)

// ── Pill attribute shape: annotations carry type/label/language ───────────────
// Pill components read `type`, `label`, `language` from annotation objects.
// Verify annotations on the payload carry these fields through.

const pillAnns = [
  { id: 'a1', label: 'hablar', type: 'vocabulary', language: 'es', confidence: 0.9, canonical_form: 'hablar' },
  { id: 'a2', label: 'habla', type: 'conjugation', language: 'es', confidence: 0.85, canonical_form: 'hablar:present:3sg' },
]
const pillPayload = buildLessonPipelinePayload({
  sourceText: 'Pedro habla bien. Le gusta hablar.',
  normalizedText: 'Pedro habla bien. Le gusta hablar.',
  parseData: makeParseData([
    { text: 'Pedro habla bien. Le gusta hablar.', learnable_objects: pillAnns },
  ]),
})
assert.equal(pillPayload.annotations.length, 2)
assert.equal(pillPayload.annotations[0].type, 'vocabulary')
assert.equal(pillPayload.annotations[0].label, 'hablar')
assert.equal(pillPayload.annotations[1].type, 'conjugation')
assert.equal(pillPayload.annotations[1].label, 'habla')

// ── Validation rejects malformed payloads ─────────────────────────────────────

assert.throws(
  () => validateLessonPipelinePayload({ ...spanishPayload, sentences: spanishPayload.highlightedTerms }),
  /sentences entries must be objects/,
)
assert.throws(
  () => validateLessonPipelinePayload({ ...spanishPayload, sourceText: 42 }),
  /sourceText must be a string/,
)
assert.throws(
  () => validateLessonPipelinePayload({ ...spanishPayload, annotations: 'bad' }),
  /annotations must be an array/,
)

// ── Graceful degradation: missing or null parseData ───────────────────────────

const emptyPayload = buildLessonPipelinePayload({
  sourceText: 'Texto sin analizar.',
  normalizedText: 'Texto sin analizar.',
  parseData: null,
})
assert.equal(emptyPayload.sourceText, 'Texto sin analizar.')
assert.deepEqual(emptyPayload.sentences, [])
assert.deepEqual(emptyPayload.tokens, [])
assert.deepEqual(emptyPayload.highlightedTerms, [])
assert.deepEqual(emptyPayload.annotations, [])

console.log('lesson pipeline separation tests passed')
