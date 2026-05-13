import assert from 'node:assert/strict'
import fs from 'node:fs'
import vm from 'node:vm'

const source = fs.readFileSync(new URL('../js/recommended-reading.js', import.meta.url), 'utf8')
const canUseMatch = source.match(/function canUseRecommendationItem\(item, language\) \{[\s\S]*?\n\}/)
if (!canUseMatch) throw new Error('canUseRecommendationItem not found')

const ctx = { result: null }
vm.createContext(ctx)
vm.runInContext(`${canUseMatch[0]}\nresult = canUseRecommendationItem`, ctx)
const canUseRecommendationItem = ctx.result

assert.equal(canUseRecommendationItem({ text: 'Presque tout a disparu.', language: 'fr' }, 'es'), false)
assert.equal(canUseRecommendationItem({ text: 'Casi todo ha desaparecido.', language: 'es' }, 'es'), true)
assert.equal(canUseRecommendationItem({ text: 'Casi todo ha desaparecido.' }, 'es'), true)

console.log('recommended-reading language guard tests passed')
