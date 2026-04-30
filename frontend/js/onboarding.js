/*
  First-session onboarding and trust flow.

  Renders an inline welcome panel above the parse section on first visit.
  Dismissed via CTA or close button — stored in localStorage.
*/

const ONBOARDING_KEY = 'mnemosyne.onboarding.seen.v2'
const COACH_KEY = 'mnemosyne.firstRun.coach.dismissed'

let chooseTextBtn, languageSelect, pickerSampleBtn, pickerUseBtn, results, a11yLive

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

function openDemo() {
  markSeen()
  dismissPanel()
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
  dismissPanel()
  chooseTextBtn?.click()
  announce('Paste your own text to begin.')
}

function ensureOnboarding() {
  if (hasSeenOnboarding()) return

  // Insert above the parse section, inside the authenticated content column.
  const wrap = document.querySelector('#main .wrap')
  if (!wrap) return

  const panel = document.createElement('section')
  panel.className = 'mnemosyne-onboarding panel'
  panel.setAttribute('aria-labelledby', 'mnemosyne-onboarding-title')
  panel.innerHTML = `
    <div class="mnemosyne-onboarding__header">
      <p class="mnemosyne-onboarding__eyebrow">First 30 seconds</p>
      <button type="button" class="dialog-close-btn mnemosyne-onboarding__close" aria-label="Dismiss introduction">&#x2715;</button>
    </div>
    <h2 id="mnemosyne-onboarding-title" class="mnemosyne-onboarding__headline">Just read. Mnemosyne handles the rest.</h2>
    <ol class="mnemosyne-onboarding__list">
      <li><strong>Memory</strong> — what you know and what is fading.</li>
      <li><strong>Difficulty</strong> — whether the next passage should be easier or harder.</li>
      <li><strong>Pace</strong> — whether you are flowing, tired, or overloaded.</li>
    </ol>
    <p class="mnemosyne-onboarding__promise">You stay in the text. The system adjusts around you.</p>
    <div class="mnemosyne-onboarding__actions button-row">
      <button class="button-primary" id="onboarding-demo">Try a 30-second demo</button>
      <button class="ghost-button" id="onboarding-own-text">Use my own text</button>
    </div>
  `

  // Insert before the first child of .wrap (before the parse panel).
  wrap.insertBefore(panel, wrap.firstElementChild)

  panel.querySelector('.mnemosyne-onboarding__close')?.addEventListener('click', () => {
    markSeen()
    dismissPanel()
  })
  panel.querySelector('#onboarding-demo')?.addEventListener('click', openDemo)
  panel.querySelector('#onboarding-own-text')?.addEventListener('click', startWithOwnText)
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
      <button type="button" class="mnemosyne-first-run-coach__close" aria-label="Dismiss guide">&#x2715;</button>
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
