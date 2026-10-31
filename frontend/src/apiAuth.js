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

export function isAuthEnabled() {
  return Boolean(API_KEY);
}

// ---------------------------------------------------------------------------
// Token caching
// ---------------------------------------------------------------------------

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

async function fetchToken(apiUrl) {
  const response = await fetch('/api/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Api-Key': API_KEY,
    },
    body: JSON.stringify({ apiUrl }),
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
 * @param {string} apiUrl - The base API URL
 * @returns {Promise<string|null>} "Bearer <token>" or null if auth is disabled
 */
export async function getAuthHeader(apiUrl) {
  if (!isAuthEnabled()) return null;

  let token = getCachedToken();
  if (!token) {
    const result = await fetchToken(apiUrl);
    token = result.token;
    cacheToken(token, result.ttl);
  }

  return `Bearer ${token}`;
}
