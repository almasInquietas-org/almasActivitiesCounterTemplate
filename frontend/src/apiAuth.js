/**
 * ACTIVUM — Frontend Auth Module
 *
 * Implements the two-step Bearer token auth flow using server-side HMAC signing:
 *
 * Step 1: POST /api/token (server-side proxy signs /auth/token with API_SIGNING_SECRET)
 * Step 2: GET / with Authorization: Bearer <token>
 *
 * Passthrough mode: if VITE_API_KEY is not set, requests are sent without
 * auth headers (matches API passthrough mode).
 *
 * Token caching: tokens are cached in sessionStorage with a 30-second
 * safety buffer before their actual expiry.
 */

const API_KEY = (import.meta.env.VITE_API_KEY || '').trim();
const SESSION_KEY = 'activum_auth_token';
const TTL_SAFETY_BUFFER_S = 30; // Refresh token 30s before it expires

// ---------------------------------------------------------------------------
// Auth mode detection
// ---------------------------------------------------------------------------

/**
 * Checks whether client-side API authentication is enabled based on `VITE_API_KEY`.
 *
 * @returns {boolean} True when `VITE_API_KEY` is configured, false for passthrough mode.
 */
export function isAuthEnabled() {
  return Boolean(API_KEY);
}

// ---------------------------------------------------------------------------
// Token caching
// ---------------------------------------------------------------------------

/**
 * Retrieves a valid cached Bearer token from `sessionStorage` if it has not
 * entered the pre-expiration safety buffer window.
 *
 * @returns {string|null} The cached Bearer token string, or null if missing/expired.
 */
function getCachedToken() {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const { token, expiresAt } = JSON.parse(raw);
    if (Date.now() < expiresAt - TTL_SAFETY_BUFFER_S * 1000) {
      return token;
    }
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  } catch {
    return null;
  }
}

/**
 * Stores a Bearer token and its computed expiration timestamp in `sessionStorage`.
 *
 * @param {string} token - The Bearer token issued by the API.
 * @param {number} ttlSeconds - Token time-to-live in seconds.
 * @returns {void}
 */
function cacheToken(token, ttlSeconds) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({
      token,
      expiresAt: Date.now() + ttlSeconds * 1000,
    }));
  } catch {
    // sessionStorage might be unavailable (e.g. private browsing)
  }
}

// ---------------------------------------------------------------------------
// Token request (delegates HMAC signing to server-side /api/token)
// ---------------------------------------------------------------------------

/**
 * Requests a short-lived Bearer token from the server-side `/api/token` proxy,
 * which signs the upstream `/auth/token` handshake using `API_SIGNING_SECRET`.
 *
 * @returns {Promise<{token: string, ttl: number}>} Issued token and TTL in seconds.
 */
async function fetchToken() {
  const response = await fetch('/api/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Api-Key': API_KEY,
    },
  });

  if (!response.ok) {
    throw new Error(`Auth failed: ${response.status}`);
  }

  const data = await response.json();
  return { token: data.token, ttl: data.ttl ?? 300 };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Returns the Authorization header value for a data request.
 * Handles token caching and refresh automatically.
 *
 * @returns {Promise<string|null>} "Bearer <token>" or null if auth is disabled.
 */
export async function getAuthHeader() {
  if (!isAuthEnabled()) return null;

  let token = getCachedToken();
  if (!token) {
    const result = await fetchToken();
    token = result.token;
    cacheToken(token, result.ttl);
  }

  return `Bearer ${token}`;
}
