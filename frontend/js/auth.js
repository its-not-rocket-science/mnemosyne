import { t } from './i18n.js'

/**
 * auth.js — JWT token storage and auth-state UI management.
 *
 * Token lifecycle
 * ───────────────
 * Stored in sessionStorage under AUTH_KEY.  sessionStorage is per-tab and
 * cleared when the tab is closed, which is the right trade-off for a language-
 * learning app: users stay signed in across refreshes in the same session but
 * a fresh tab requires a new sign-in.
 *
 * Exported API
 * ────────────
 * getToken()        → string | null
 * setToken(token, userId, email)  → void
 * clearToken()      → void
 * getAuthHeaders()  → { Authorization: string } | {}
 * isSignedIn()      → boolean
 * initAuth()        → void   (call once on page load)
 */

const AUTH_KEY   = 'mnemosyne_token'
const USER_KEY   = 'mnemosyne_user'   // { id, email }

// ── Token primitives ──────────────────────────────────────────────────────────

export function getToken() {
  return sessionStorage.getItem(AUTH_KEY)
}

export function isSignedIn() {
  return Boolean(getToken())
}

export function setToken(token, userId, email) {
  sessionStorage.setItem(AUTH_KEY, token)
  sessionStorage.setItem(USER_KEY, JSON.stringify({ id: userId, email }))
}

export function clearToken() {
  sessionStorage.removeItem(AUTH_KEY)
  sessionStorage.removeItem(USER_KEY)
}

export function getUser() {
  try {
    return JSON.parse(sessionStorage.getItem(USER_KEY) ?? 'null')
  } catch {
    return null
  }
}

/**
 * Return an object with the Authorization header when a token is present, or
 * an empty object otherwise.  Spread into your fetch headers:
 *
 *   fetch(url, { headers: { 'Content-Type': 'application/json', ...getAuthHeaders() } })
 */
export function getAuthHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

// ── DOM references ────────────────────────────────────────────────────────────

const authPanel         = document.querySelector('#auth-panel')
const mainContent       = document.querySelector('#main-content')
const userInfo          = document.querySelector('#user-info')
const userEmailEl       = document.querySelector('#user-email')
const logoutBtn         = document.querySelector('#logout-btn')
const deleteAccountBtn  = document.querySelector('#delete-account-btn')
const authStatus        = document.querySelector('#auth-status')

const loginTab       = document.querySelector('#login-tab')
const registerTab    = document.querySelector('#register-tab')
const tabSignIn      = document.querySelector('#tab-signin')
const tabRegister    = document.querySelector('#tab-register')

// login form
const loginForm     = document.querySelector('#login-form')
const loginEmail    = loginForm.querySelector('#login-email')
const loginPassword = loginForm.querySelector('#login-password')
const loginSubmit   = loginForm.querySelector('button[type="submit"]')

function updateLoginButtonState() {
  loginSubmit.disabled = !loginEmail.value.trim() || !loginPassword.value
}

loginEmail.addEventListener('input', updateLoginButtonState)
loginPassword .addEventListener('input', updateLoginButtonState)

updateLoginButtonState()

// registration form
const registerForm = document.querySelector('#register-form')
const registerEmail    = registerForm.querySelector('#reg-email')
const registerPassword = registerForm.querySelector('#reg-password')
const registerConfirm  = registerForm.querySelector('#reg-confirm')
const registerSubmit = registerForm.querySelector('button[type="submit"]')

function updateRegisterButtonState() {
  const emailValid    = registerEmail.value.trim() !== ''
  const passwordValid = registerPassword.value !== ''
  const confirmValid  = registerConfirm.value !== ''
  registerSubmit.disabled = !(emailValid && passwordValid && confirmValid)
}

registerEmail.addEventListener('input', updateRegisterButtonState)
registerPassword.addEventListener('input', updateRegisterButtonState)
registerConfirm.addEventListener('input', updateRegisterButtonState)

updateRegisterButtonState()

// ── Tab switching ─────────────────────────────────────────────────────────────

function switchTab(active) {
  // active: 'login' | 'register'
  const isLogin = active === 'login'

  tabSignIn.setAttribute('aria-selected',   String(isLogin))
  tabRegister.setAttribute('aria-selected', String(!isLogin))

  // Roving tabindex: only the selected tab is in the sequential focus order.
  // The unselected tab is reachable only via arrow keys.
  tabSignIn.tabIndex   = isLogin ? 0  : -1
  tabRegister.tabIndex = isLogin ? -1 : 0

  loginTab.hidden    = !isLogin
  registerTab.hidden = isLogin
  clearAuthStatus()
}

tabSignIn?.addEventListener('click',   () => switchTab('login'))
tabRegister?.addEventListener('click', () => switchTab('register'))

// Keyboard navigation inside the tablist (Left/Right arrows).
// Per ARIA APG tab pattern: arrow keys move between tabs, Tab leaves the group.
document.querySelector('#auth-tablist')?.addEventListener('keydown', (e) => {
  const tabs = [tabSignIn, tabRegister]
  const idx  = tabs.indexOf(document.activeElement)
  if (idx === -1) return
  if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
    e.preventDefault()
    const next = tabs[(idx + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length]
    next.focus()
    next.click()
  }
})

// ── Auth UI show / hide ───────────────────────────────────────────────────────

// moveFocus controls whether focus is explicitly moved.
// Pass true on user-triggered transitions (login, logout).
// Pass false on page-load restoration to avoid stealing initial focus.

function showApp(email, { moveFocus = false } = {}) {
  authPanel.hidden   = true
  mainContent.hidden = false
  if (userEmailEl) userEmailEl.textContent = email ?? ''
  if (userInfo)    userInfo.hidden = !email
  if (moveFocus) {
    // Move focus to the language select — first meaningful interactive element
    // in the app — so the keyboard user knows the app is now available.
    queueMicrotask(() => {
      const target = document.querySelector('#language') ??
                     document.querySelector('#main')
      target?.focus()
    })
  }
}

function showAuthPanel({ moveFocus = false } = {}) {
  authPanel.hidden   = false
  mainContent.hidden = true
  if (userInfo) userInfo.hidden = true
  if (moveFocus) {
    // Move focus to the email field on the active tab so the keyboard user
    // can immediately start typing without having to Tab into the form.
    queueMicrotask(() => {
      const emailInput = loginTab.hidden
        ? document.querySelector('#reg-email')
        : document.querySelector('#login-email')
      emailInput?.focus()
    })
  }
}

function setAuthStatus(message, state = 'idle') {
  if (!authStatus) return
  authStatus.textContent = ''
  queueMicrotask(() => {
    authStatus.textContent = message
    authStatus.dataset.state = state
  })
}

function clearAuthStatus() {
  if (!authStatus) return
  authStatus.textContent = ''
  authStatus.dataset.state = 'idle'
}

// ── Logout ────────────────────────────────────────────────────────────────────

logoutBtn?.addEventListener('click', () => {
  clearToken()
  switchTab('login')
  showAuthPanel({ moveFocus: true })
  loginForm?.reset()
  registerForm?.reset()
})

// ── Delete account ────────────────────────────────────────────────────────────

deleteAccountBtn?.addEventListener('click', async () => {
  // Native confirm is synchronous, accessible, and avoids building a custom
  // dialog for a destructive one-off action.
  if (!confirm(
    'Permanently delete your account and all learning data?\n\n' +
    'This cannot be undone.'
  )) return

  deleteAccountBtn.disabled = true

  try {
    const resp = await fetch(`${API_BASE}/users/me`, {
      method: 'DELETE',
      headers: { ...getAuthHeaders() },
    })
    if (!resp.ok && resp.status !== 204) {
      const data = await resp.json().catch(() => null)
      throw new Error(data?.detail ?? `Request failed (${resp.status})`)
    }
    clearToken()
    switchTab('login')
    showAuthPanel({ moveFocus: true })
    loginForm?.reset()
    registerForm?.reset()
  } catch (err) {
    alert(`Could not delete account: ${err.message}`)
    deleteAccountBtn.disabled = false
  }
})

// ── API helpers ───────────────────────────────────────────────────────────────

const API_BASE = 'http://localhost:8000'

async function callAuth(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(body),
  })
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    throw Object.assign(new Error(data?.detail ?? `Request failed (${response.status})`), { status: response.status })
  }
  return data
}

// ── Login form ────────────────────────────────────────────────────────────────

loginForm?.addEventListener('submit', async (e) => {
  e.preventDefault()
  const email    = loginEmail.value.trim()
  const password = loginPassword.value

  loginSubmit.disabled = true
  setAuthStatus(t('signing_in'), 'busy')

  try {
    const data = await callAuth('/auth/login', { email, password })
    setToken(data.access_token, data.user_id, email)
    loginForm.reset()
    showApp(email, { moveFocus: true })
  } catch (err) {
    setAuthStatus(getAuthErrorMessage(err), 'error')
  } finally {
    loginSubmit.disabled = false
  }
})

// ── Register form ─────────────────────────────────────────────────────────────

registerForm?.addEventListener('submit', async (e) => {
  e.preventDefault()
  const email    = registerEmail.value.trim()
  const password = registerPassword.value
  const confirm  = registerConfirm.value

  if (password !== confirm) {
    return setAuthStatus(t('passwords_do_not_match'), 'error')
  }

  registerSubmit.disabled = true
  setAuthStatus(t('creating_account'), 'busy')

  try {
    const data = await callAuth('/auth/register', { email, password })
    setToken(data.access_token, data.user_id, email)
    registerForm.reset()
    showApp(email, { moveFocus: true })
  } catch (err) {
    setAuthStatus(getAuthErrorMessage(err), 'error')
  } finally {
    registerSubmit.disabled = false
  }
})

function getAuthErrorMessage(err) {
  const detail = typeof err?.detail === 'string' ? err.detail : ''

  if (err?.status === 401) return t('invalid_credentials')
  if (err?.status === 409) return t('email_already_registered')
  if (err?.status === 422) return t('invalid_auth_request')
  if (err?.status === 429) return t('auth_rate_limited')
  if (err?.status === 503) return t('database_unavailable')
  if (err?.status >= 500) return t('database_unavailable')

  if (detail === 'Invalid email or password.') return t('invalid_credentials')
  if (detail === 'Email already registered.') return t('email_already_registered')
  if (detail === 'Database unavailable') return t('database_unavailable')

  return t('auth_failed')
}

// ── Init ──────────────────────────────────────────────────────────────────────

/**
 * Call once on page load.  Restores the session if a token exists, otherwise
 * shows the auth panel.
 */
export function initAuth() {
  if (isSignedIn()) {
    const user = getUser()
    showApp(user?.email ?? null)
  } else {
    showAuthPanel()
  }
}
