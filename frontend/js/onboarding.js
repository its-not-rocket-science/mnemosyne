/*
  First-session onboarding and trust flow.

  Renders an inline welcome panel above the parse section on first visit.
  Dismissed via CTA or close button — stored in localStorage.
*/

const ONBOARDING_KEY = 'mnemosyne.onboarding.seen.v2'
const COACH_KEY = 'mnemosyne.firstRun.coach.dismissed'

let chooseTextBtn, languageSelect, pickerSampleBtn, pickerUseBtn, results, a11yLive
let coachStep = 0
let spotlit = null

function announce(message) {
  if (!a11yLive) return
  a11yLive.textContent = ''
  queueMicrotask(() => { a11yLive.textContent = message })
}

function hasSeenOnboarding() {
  return localStorage.getItem(ONBOARDING_KEY) === 'true'
}

function markSeen() {
  localStorage.setItem(ONBOARDING_KEY, 'true')
}

function preferredDemoLanguage() {
  const available = Array.from(languageSelect?.options || []).map(opt => opt.value)
  return available.includes('es') ? 'es' : available.find(Boolean) || ''
}

function setDemoLanguage() {
  if (!languageSelect || languageSelect.value) return
  const demoLang = preferredDemoLanguage()
  if (!demoLang) return
  languageSelect.value = demoLang
  languageSelect.dispatchEvent(new Event('change', { bubbles: true }))
}

function dismissPanel() {
  const panel = document.querySelector('.mnemosyne-onboarding')
  if (!panel) return
  panel.setAttribute('aria-hidden', 'true')
  panel.classList.add('mnemosyne-onboarding--dismissed')
  panel.addEventListener('animationend', () => panel.remove(), { once: true })
  // Remove immediately if reduced-motion
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) panel.remove()
}

function spotlightAnnotation(el) {
  spotlit?.classList.remove('onboarding-spotlight')
  spotlit = el
  el.classList.add('onboarding-spotlight')
  el.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
}

function clearSpotlight() {
  spotlit?.classList.remove('onboarding-spotlight')
  spotlit = null
}

function dismissCoach() {
  document.querySelector('#mnemosyne-first-run-coach')?.remove()
  clearSpotlight()
  localStorage.setItem(COACH_KEY, 'true')
}

function openDemo() {
  markSeen()
  dismissPanel()
  setDemoLanguage()
  chooseTextBtn?.click()
  setTimeout(() => {
    pickerSampleBtn?.click()
    setTimeout(() => {
      pickerUseBtn?.click()
      announce('Sample loading. Highlighted words will appear — tap one to explore it.')
    }, 150)
  }, 200)
}

function startWithOwnText() {
  markSeen()
  dismissPanel()
  chooseTextBtn?.click()
  announce('Paste your own text to begin.')
}

function ensureOnboarding() {
  if (hasSeenOnboarding()) return

  const wrap = document.querySelector('#main .wrap')
  if (!wrap) return

  const panel = document.createElement('section')
  panel.className = 'mnemosyne-onboarding panel'
  panel.setAttribute('aria-labelledby', 'mnemosyne-onboarding-title')
  panel.innerHTML = `
    <div class="mnemosyne-onboarding__header">
      <p class="mnemosyne-onboarding__eyebrow">Get started</p>
      <button type="button" class="dialog-close-btn mnemosyne-onboarding__close" aria-label="Dismiss introduction">&#x2715;</button>
    </div>
    <h2 id="mnemosyne-onboarding-title" class="mnemosyne-onboarding__headline">Read. Tap a word. Learn.</h2>
    <p class="mnemosyne-onboarding__lede">Tap any highlighted word — Mnemosyne tracks what you know and adapts as you go.</p>
    <div class="mnemosyne-onboarding__actions button-row">
      <button class="button-primary" id="onboarding-demo">Start with a sample →</button>
      <button class="ghost-button" id="onboarding-own-text">Use my own text</button>
    </div>
  `

  wrap.insertBefore(panel, wrap.firstElementChild)

  panel.querySelector('.mnemosyne-onboarding__close')?.addEventListener('click', () => {
    markSeen()
    dismissPanel()
  })
  panel.querySelector('#onboarding-demo')?.addEventListener('click', openDemo)
  panel.querySelector('#onboarding-own-text')?.addEventListener('click', startWithOwnText)
}

function showCoachStep({ title, body, target, step }) {
  if (localStorage.getItem(COACH_KEY) === 'true') return

  let coach = document.querySelector('#mnemosyne-first-run-coach')
  if (!coach) {
    coach = document.createElement('aside')
    coach.id = 'mnemosyne-first-run-coach'
    coach.className = 'mnemosyne-first-run-coach'
    coach.setAttribute('role', 'status')
    coach.innerHTML = `
      <button type="button" class="mnemosyne-first-run-coach__close" aria-label="Dismiss guide">&#x2715;</button>
      <h4></h4>
      <p></p>
    `
    document.body.appendChild(coach)
    coach.querySelector('.mnemosyne-first-run-coach__close')?.addEventListener('click', dismissCoach)
  }

  coach.querySelector('h4').textContent = title
  coach.querySelector('p').textContent = body
  if (step != null) coach.dataset.step = String(step)

  if (target?.getBoundingClientRect) {
    const rect = target.getBoundingClientRect()
    const margin = 16
    const coachW = 320
    const top = rect.bottom + 14
    const left = Math.max(margin, Math.min(rect.left, window.innerWidth - coachW - margin))
    coach.style.setProperty('--coach-top', `${Math.max(margin, top)}px`)
    coach.style.setProperty('--coach-left', `${left}px`)
  }

  announce(`${title}. ${body}`)
}

function observePreviewOpen() {
  if (!results) return
  const observer = new MutationObserver(() => {
    const preview = results.querySelector('.reader-inline-preview')
    if (!preview) return
    observer.disconnect()
    if (coachStep !== 1) return
    coachStep = 2
    showCoachStep({
      title: 'Rate this word',
      body: 'Weak · Learning · Known — one tap and Mnemosyne remembers it.',
      target: preview,
      step: 2,
    })
    // Dismiss after first rating tap
    preview.addEventListener('click', event => {
      if (event.target.closest('.reader-memory-btn')) {
        coachStep = 3
        setTimeout(dismissCoach, 500)
      }
    })
  })
  observer.observe(results, { childList: true, subtree: true })
}

function observeFirstLesson() {
  if (!results) return
  const observer = new MutationObserver(() => {
    const firstAnnotation = results.querySelector('.reader-annotation')
    if (!firstAnnotation) return
    observer.disconnect()
    if (localStorage.getItem(COACH_KEY) === 'true') return

    coachStep = 1
    spotlightAnnotation(firstAnnotation)
    showCoachStep({
      title: 'Tap any highlighted word',
      body: 'Color shows the type — vocab, grammar, idiom. Tap to explore it.',
      target: firstAnnotation,
      step: 1,
    })
    observePreviewOpen()

    // Clear spotlight on any annotation interaction
    results.addEventListener('click', event => {
      if (event.target.closest('.reader-annotation')) clearSpotlight()
    }, { once: true })
  })
  observer.observe(results, { childList: true, subtree: true })
}

function init() {
  chooseTextBtn  = document.querySelector('#choose-text-btn')
  languageSelect = document.querySelector('#language')
  pickerSampleBtn = document.querySelector('#picker-sample-btn')
  pickerUseBtn   = document.querySelector('#picker-use-btn')
  results        = document.querySelector('#results')
  a11yLive       = document.querySelector('#a11y-live')

  // #main-content is hidden until auth completes — wait for it to become visible.
  const mainContent = document.querySelector('#main-content')
  if (!mainContent) return

  if (!mainContent.hidden) {
    ensureOnboarding()
    observeFirstLesson()
    return
  }

  const visibilityObserver = new MutationObserver(() => {
    if (!mainContent.hidden) {
      visibilityObserver.disconnect()
      ensureOnboarding()
      observeFirstLesson()
    }
  })
  visibilityObserver.observe(mainContent, { attributes: true, attributeFilter: ['hidden'] })
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
