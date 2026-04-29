/*
  First-session onboarding (trust layer)
*/

const KEY = 'mnemosyne.onboarding.seen'

function ensureOnboarding() {
  if (localStorage.getItem(KEY)) return

  const panel = document.createElement('aside')
  panel.className = 'mnemosyne-onboarding'
  panel.innerHTML = `
    <div class="mnemosyne-onboarding__card">
      <h3>Welcome to Mnemosyne</h3>
      <p>This system adapts to you automatically:</p>
      <ul>
        <li>It shows what you’re about to forget</li>
        <li>It adjusts difficulty in real time</li>
        <li>It slows down if you struggle</li>
      </ul>
      <p><strong>You don’t need to configure anything.</strong></p>
      <button class="button-primary" id="onboarding-start">Start reading</button>
    </div>
  `

  document.body.appendChild(panel)

  document.querySelector('#onboarding-start')?.addEventListener('click', () => {
    panel.remove()
    localStorage.setItem(KEY, 'true')
  })
}

function init() {
  ensureOnboarding()
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init, { once: true })
} else {
  init()
}
