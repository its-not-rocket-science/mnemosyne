export function computeAdaptiveProfile(input = {}) {
  const level = String(input.level || '').toUpperCase()
  const memory = input.memory || { weak: 0, fading: 0, strong: 0, total: 0 }
  const reviews = input.reviews || { total: 0, accuracy: 0.5 }
  const usage = Number.isFinite(input.annotationUsage) ? input.annotationUsage : 0
  const total = Math.max(1, memory.total || 0)
  const weakShare = (memory.weak || 0) / total
  const strongShare = (memory.strong || 0) / total

  const profile = {
    annotationDensity: 'balanced',
    vocabularyHints: 'adaptive',
    grammarExplanations: 'adaptive',
    translationVisibility: 'adaptive',
    exampleDifficulty: 'adaptive',
    reviewPromptCadence: 'adaptive',
    reasons: [],
    defaulting: false,
  }

  if ((memory.total || 0) === 0 && (reviews.total || 0) === 0) {
    profile.defaulting = true
    profile.annotationDensity = 'guided'
    profile.vocabularyHints = 'expanded'
    profile.grammarExplanations = 'expanded'
    profile.translationVisibility = 'sentence'
    profile.exampleDifficulty = 'beginner'
    profile.reviewPromptCadence = 'light'
    profile.reasons.push('no_history_default')
    return profile
  }

  if (level === 'A1' || level === 'A2') {
    profile.annotationDensity = 'guided'
    profile.vocabularyHints = 'expanded'
    profile.grammarExplanations = 'expanded'
    profile.translationVisibility = 'sentence'
    profile.exampleDifficulty = 'beginner'
    profile.reviewPromptCadence = 'frequent'
    profile.reasons.push('beginner_level')
  } else if (level === 'B1' || level === 'B2') {
    profile.annotationDensity = 'balanced'
    profile.vocabularyHints = 'adaptive'
    profile.grammarExplanations = 'key-only'
    profile.translationVisibility = 'phrase'
    profile.exampleDifficulty = 'intermediate'
    profile.reviewPromptCadence = 'normal'
    profile.reasons.push('intermediate_level')
  } else if (level === 'C1' || level === 'C2') {
    profile.annotationDensity = 'light'
    profile.vocabularyHints = 'on-demand'
    profile.grammarExplanations = 'on-demand'
    profile.translationVisibility = 'hidden'
    profile.exampleDifficulty = 'advanced'
    profile.reviewPromptCadence = 'sparse'
    profile.reasons.push('advanced_level')
  }

  if (weakShare >= 0.45 || reviews.accuracy < 0.6) {
    profile.annotationDensity = 'guided'
    profile.translationVisibility = 'sentence'
    profile.reviewPromptCadence = 'frequent'
    profile.reasons.push('struggling_recently')
  } else if (strongShare >= 0.65 && reviews.accuracy >= 0.8) {
    profile.annotationDensity = 'light'
    profile.translationVisibility = 'hidden'
    profile.reasons.push('stable_mastery')
  }

  if (usage >= 10) profile.reasons.push('high_annotation_usage')
  return profile
}
