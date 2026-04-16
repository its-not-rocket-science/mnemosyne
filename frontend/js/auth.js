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

function getUser() {
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

const authPanel    = document.querySelector('#auth-panel')
const mainContent  = document.querySelector('#main-content')
const userInfo     = document.querySelector('#user-info')
const userEmailEl  = document.querySelector('#user-email')
const logoutBtn    = document.querySelector('#logout-btn')
const authStatus   = document.querySelector('#auth-status')

const loginTab       = document.querySelector('#login-tab')
const registerTab    = document.querySelector('#register-tab')
const tabSignIn      = document.querySelector('#tab-signin')
const tabRegister    = document.querySelector('#tab-register')

const loginForm    = document.querySelector('#login-form')
const registerForm = document.querySelector('#register-form')

// ── Tab switching ─────────────────────────────────────────────────────────────

function switchTab(active) {
  // active: 'login' | 'register'
  const isLogin = active === 'login'

  tabSignIn.setAttribute('aria-selected',   String(isLogin))
  tabRegister.setAttribute('aria-selected', String(!isLogin))

  loginTab.hidden    = !isLogin
  registerTab.hidden = isLogin
  clearAuthStatus()
}

tabSignIn?.addEventListener('click',   () => switchTab('login'))
tabRegister?.addEventListener('click', () => switchTab('register'))

// Keyboard navigation inside the tablist (Left/Right arrows).
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

function showApp(email) {
  authPanel.hidden   = true
  mainContent.hidden = false
  if (userEmailEl) userEmailEl.textContent = email ?? ''
  if (userInfo)    userInfo.hidden = !email
}

function showAuthPanel() {
  authPanel.hidden   = false
  mainContent.hidden = true
  if (userInfo) userInfo.hidden = true
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
  showAuthPanel()
  loginForm?.reset()
  registerForm?.reset()
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
  const email    = loginForm.querySelector('#login-email').value.trim()
  const password = loginForm.querySelector('#login-password').value

  const btn = loginForm.querySelector('button[type="submit"]')
  btn.disabled = true
  setAuthStatus('Signing in\u2026', 'busy')

  try {
    const data = await callAuth('/auth/login', { email, password })
    setToken(data.access_token, data.user_id, email)
    loginForm.reset()
    showApp(email)
  } catch (err) {
    setAuthStatus(err.message, 'error')
  } finally {
    btn.disabled = false
  }
})

// ── Register form ─────────────────────────────────────────────────────────────

registerForm?.addEventListener('submit', async (e) => {
  e.preventDefault()
  const email    = registerForm.querySelector('#reg-email').value.trim()
  const password = registerForm.querySelector('#reg-password').value
  const confirm  = registerForm.querySelector('#reg-confirm').value

  if (password !== confirm) {
    setAuthStatus('Passwords do not match.', 'error')
    return
  }

  const btn = registerForm.querySelector('button[type="submit"]')
  btn.disabled = true
  setAuthStatus('Creating account\u2026', 'busy')

  try {
    const data = await callAuth('/auth/register', { email, password })
    setToken(data.access_token, data.user_id, email)
    registerForm.reset()
    showApp(email)
  } catch (err) {
    setAuthStatus(err.message, 'error')
  } finally {
    btn.disabled = false
  }
})

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
