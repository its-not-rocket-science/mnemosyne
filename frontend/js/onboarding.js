/*
  First-session onboarding and 30-second trust flow.

  Goals:
  - explain the adaptive system in one screen
  - give users a safe first action
  - guide them to the sample-text path already supported by main.js
  - reinforce trust after the first lesson appears
*/

const ONBOARDING_KEY = 'mnemosyne.onboarding.seen.v2'
const COACH_KEY = 'mnemosyne.firstRun.coach.dismissed'

const chooseTextBtn = document.querySelector('#choose-text-btn')
const languageSelect = document.querySelector('#language')
const textPicker = document.querySelector('#text-picker')
const pickerSampleBtn = document.querySelector('#picker-sample-btn')
const pickerUseBtn = document.querySelector('#picker-use-btn')
const results = document.querySelector('#results')
const a11yLive = document.querySelector('#a11y-live')

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

function openDemo() {
  markSeen()
  document.querySelector('.mnemosyne-onboarding')?.remove()
  setDemoLanguage()
  chooseTextBtn?.click()
  setTimeout(() => {
    pickerSampleBtn?.click()
    pickerUseBtn?.focus()
    announce('Sample text loaded. Press Use this text to see your first adaptive lesson.')
    showCoachStep({
      title: 'One click from the first lesson',
      body: 'The sample is loaded. Use this text, then Mnemosyne will highlight what can be learned and adapt from there.',
      target: pickerUseBtn,
    })
  }, 250)
}

function startWithOwnText() {
  markSeen()
  document.querySelector('.mnemosyne-onboarding')?.remove()
  chooseTextBtn?.click()
  announce('Paste your own text to begin.')
}

function ensureOnboarding() {
  if (hasSeenOnboarding()) return

  const panel = document.createElement('aside')
  panel.className = 'mnemosyne-onboarding'
  panel.setAttribute('role', 'dialog')
  panel.setAttribute('aria-modal', 'true')
  panel.setAttribute('aria-labelledby', 'mnemosyne-onboarding-title')
  panel.innerHTML = `
    <div class="mnemosyne-onboarding__card">
      <p class="mnemosyne-onboarding__eyebrow">First 30 seconds</p>
      <h3 id="mnemosyne-onboarding-title">Just read. Mnemosyne handles the rest.</h3>
      <p>Mnemosyne quietly watches three things:</p>
      <ol>
        <li><strong>Memory</strong> — what you know and what is fading.</li>
        <li><strong>Difficulty</strong> — whether the next passage should be easier or harder.</li>
        <li><strong>Pace</strong> — whether you are flowing, tired, or overloaded.</li>
      </ol>
      <p class="mnemosyne-onboarding__promise">You stay in the text. The system adjusts around you.</p>
      <div class="mnemosyne-onboarding__actions">
        <button class="button-primary" id="onboarding-demo">Try a 30-second demo</button>
        <button class="ghost-button" id="onboarding-own-text">Use my own text</button>
      </div>
    </div>
  `

  document.body.appendChild(panel)
  document.querySelector('#onboarding-demo')?.addEventListener('click', openDemo)
  document.querySelector('#onboarding-own-text')?.addEventListener('click', startWithOwnText)
  document.querySelector('#onboarding-demo')?.focus()
}

function showCoachStep({ title, body, target }) {
  if (localStorage.getItem(COACH_KEY) === 'true') return

  let coach = document.querySelector('#mnemosyne-first-run-coach')
  if (!coach) {
    coach = document.createElement('aside')
    coach.id = 'mnemosyne-first-run-coach'
    coach.className = 'mnemosyne-first-run-coach'
    coach.setAttribute('role', 'status')
    coach.innerHTML = `
      <button type="button" class="mnemosyne-first-run-coach__close" aria-label="Dismiss first-run guide">×</button>
      <h4></h4>
      <p></p>
    `
    document.body.appendChild(coach)
    coach.querySelector('.mnemosyne-first-run-coach__close')?.addEventListener('click', () => {
      localStorage.setItem(COACH_KEY, 'true')
      coach.remove()
    })
  }

  coach.querySelector('h4').textContent = title
  coach.querySelector('p').textContent = body

  if (target?.getBoundingClientRect) {
    const rect = target.getBoundingClientRect()
    coach.style.setProperty('--coach-top', `${Math.max(16, rect.bottom + 12)}px`)
    coach.style.setProperty('--coach-left', `${Math.max(16, Math.min(rect.left, window.innerWidth - 360))}px`)
  }
}

function observeFirstLesson() {
  if (!results) return
  const observer = new MutationObserver(() => {
    const firstAnnotation = results.querySelector('.reader-annotation')
    if (!firstAnnotation) return
    showCoachStep({
      title: 'This is the adaptive moment',
      body: 'Click a highlighted word or phrase. Mark it weak, learning, or known. Mnemosyne uses that signal to reshape future text.',
      target: firstAnnotation,
    })
    observer.disconnect()
  })
  observer.observe(results, { childList: true, subtree: true })
}

function init() {
  ensureOnboarding()
  observeFirstLesson()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
