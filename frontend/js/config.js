/**
 * config.js — Runtime API base URL.
 *
 * Production: FastAPI serves the frontend and API on the same origin, so an
 * empty string lets all fetch() calls resolve against the current origin.
 *
 * Local dev with a separate file server (e.g. `npx serve`, live-server on
 * port 8080): the frontend origin differs from the API origin (port 8000), so
 * we construct the API base explicitly rather than letting requests 404 against
 * the file server.
 */
const { hostname, port } = window.location

export const API_BASE =
  (hostname === 'localhost' || hostname === '127.0.0.1') && port !== '8000'
    ? `http://${hostname}:8000`
    : ''

// Email of the app owner — gates the "Save lesson" flow to a single account
// until multi-user lesson ownership exists.
export const OWNER_EMAIL = 'paul_schleifer@hotmail.com'
