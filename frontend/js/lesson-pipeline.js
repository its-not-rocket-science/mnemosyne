/**
 * Lesson pipeline payload shape guards.
 */

function assertString(value, name) {
  if (typeof value !== 'string') throw new TypeError(`${name} must be a string`)
}

function assertArray(value, name) {
  if (!Array.isArray(value)) throw new TypeError(`${name} must be an array`)
}

export function validateLessonPipelinePayload(payload) {
  if (!payload || typeof payload !== 'object') throw new TypeError('payload must be an object')
  assertString(payload.sourceText, 'sourceText')
  assertString(payload.normalizedText, 'normalizedText')
  assertArray(payload.sentences, 'sentences')
  assertArray(payload.tokens, 'tokens')
  assertArray(payload.highlightedTerms, 'highlightedTerms')
  assertArray(payload.annotations, 'annotations')

  if (payload.suggestedNextPassage != null && typeof payload.suggestedNextPassage !== 'object') {
    throw new TypeError('suggestedNextPassage must be an object or null')
  }

  for (const sentence of payload.sentences) {
    if (!sentence || typeof sentence !== 'object') throw new TypeError('sentences entries must be objects')
    assertString(sentence.text ?? '', 'sentences[].text')
    if (!Array.isArray(sentence.learnable_objects)) throw new TypeError('sentences[].learnable_objects must be an array')
  }

  return payload
}

export function buildLessonPipelinePayload({ sourceText, normalizedText, parseData, suggestedNextPassage = null }) {
  const sentences = Array.isArray(parseData?.sentences) ? parseData.sentences : []
  const annotations = sentences.flatMap(s => Array.isArray(s.learnable_objects) ? s.learnable_objects : [])
  const highlightedTerms = annotations.map(item => item?.label).filter(Boolean)
  const tokens = sentences.flatMap(s => String(s?.text || '').split(/\s+/).filter(Boolean))

  return validateLessonPipelinePayload({
    sourceText: String(sourceText || ''),
    normalizedText: String(normalizedText || ''),
    sentences,
    tokens,
    highlightedTerms,
    annotations,
    suggestedNextPassage,
  })
}
