/*
  Help popover utility.

  makeHelpButton(textKey) — returns a small "?" button that, when clicked,
  opens a positioned popover explaining the surrounding UI section.

  Uses the native Popover API (Chrome 114+, Firefox 125+, Safari 17+).
  Falls back silently to a no-op on older browsers.
*/

import { t } from './i18n.js'

const registry = new Map()   // textKey → { popover, listeners }

function positionNear(popover, btn) {
  const rect = btn.getBoundingClientRect()
  const GAP = 6
  popover.style.top = `${rect.bottom + GAP}px`
  popover.style.left = `${rect.left}px`
  requestAnimationFrame(() => {
    const pr = popover.getBoundingClientRect()
    const vpW = window.innerWidth
    if (pr.right > vpW - 8) {
      popover.style.left = `${Math.max(8, vpW - pr.width - 8)}px`
    }
  })
}

export function makeHelpButton(textKey) {
  const supportsPopover = 'popover' in HTMLElement.prototype

  let entry = registry.get(textKey)
  let popover

  if (!entry) {
    popover = document.createElement('div')
    popover.id = `help-pop-${textKey.replaceAll('_', '-')}`
    popover.className = 'help-popover'
    if (supportsPopover) popover.setAttribute('popover', '')
    popover.textContent = t(textKey)
    document.body.appendChild(popover)

    entry = { popover }
    registry.set(textKey, entry)
  } else {
    popover = entry.popover
  }

  const btn = document.createElement('button')
  btn.type = 'button'
  btn.className = 'help-btn'
  btn.textContent = '?'
  btn.setAttribute('aria-label', t('help_btn_aria'))
  if (supportsPopover) btn.setAttribute('popovertarget', popover.id)

  if (supportsPopover) {
    popover.addEventListener('beforetoggle', event => {
      if (event.newState === 'open') positionNear(popover, btn)
    })
  } else {
    // Minimal fallback: toggle a visibility class
    btn.addEventListener('click', () => {
      const open = popover.classList.toggle('help-popover--open')
      if (open) positionNear(popover, btn)
    })
    document.addEventListener('click', e => {
      if (!popover.contains(e.target) && e.target !== btn) {
        popover.classList.remove('help-popover--open')
      }
    }, { capture: true })
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape') popover.classList.remove('help-popover--open')
    })
  }

  document.addEventListener('mnemosyne:language-changed', () => {
    btn.setAttribute('aria-label', t('help_btn_aria'))
    popover.textContent = t(textKey)
  })

  return btn
}
