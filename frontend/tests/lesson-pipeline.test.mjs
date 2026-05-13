import assert from 'node:assert/strict'
import { buildLessonPipelinePayload, validateLessonPipelinePayload } from '../js/lesson-pipeline.js'

const parseData = {
  sentences: [
    {
      text: 'Hola mundo completo.',
      learnable_objects: [{ id: '1', label: 'Hola', type: 'vocabulary' }],
    },
  ],
}

const payload = buildLessonPipelinePayload({
  sourceText: 'Hola mundo completo.',
  normalizedText: 'Hola mundo completo.',
  parseData,
  suggestedNextPassage: { language: 'es', text: 'Siguiente pasaje' },
})

assert.equal(payload.sourceText, 'Hola mundo completo.')
assert.equal(payload.sentences[0].text, 'Hola mundo completo.')
assert.deepEqual(payload.highlightedTerms, ['Hola'])
assert.equal(payload.suggestedNextPassage.language, 'es')

assert.throws(() => validateLessonPipelinePayload({
  ...payload,
  sentences: payload.highlightedTerms,
}), /sentences entries must be objects/)

console.log('lesson pipeline separation tests passed')
