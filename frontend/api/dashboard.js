/**
 * Server-side BFF endpoint (/api/dashboard) for Vercel Serverless & Vite Dev/Preview.
 *
 * Performs server-to-server HMAC-SHA256 / Bearer authentication with the upstream
 * AWS Lambda API so credentials and tokens never reach the browser, forwards only
 * the `?club=` query parameter, enforces an 8s upstream timeout, and emits CDN
 * cache headers for successful responses.
 */
import crypto from 'node:crypto';

const DEFAULT_TIMEOUT_MS = 8000;
const TOKEN_SAFETY_BUFFER_MS = 30_000;
const SUCCESS_CACHE_CONTROL = 'public, s-maxage=30, stale-while-revalidate=60';
const NO_STORE_CACHE_CONTROL = 'no-store';

/** @type {Map<string, { token: string, expiresAt: number }>} */
const _tokenCache = new Map();

/**
 * Clears the server-side Bearer token cache (for unit tests).
 *
 * @returns {void}
 */
export function clearServerTokenCache() {
  _tokenCache.clear();
}

/**
 * Resolves and validates upstream Lambda URLs from trusted server configuration.
 *
 * @param {string} [configuredApiUrl] - Trusted server-configured base API URL.
 * @returns {{ dashboardBaseUrl: string, tokenUrl: string }|null} Normalized URLs or null if invalid/unset.
 */
export function resolveUpstreamUrls(configuredApiUrl) {
  const rawBaseUrl = (
    configuredApiUrl ??
    process.env.API_URL ??
    process.env.VITE_API_URL ??
    ''
  ).trim();

  if (!rawBaseUrl) {
    return null;
  }

  try {
    const parsed = new URL(rawBaseUrl);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return null;
    }
    const basePath = parsed.pathname.replace(/\/+$/, '');

    const dashboardUrl = new URL(parsed.toString());
    dashboardUrl.pathname = `${basePath}/`;
    dashboardUrl.search = '';
    dashboardUrl.hash = '';

    const tokenUrl = new URL(parsed.toString());
    tokenUrl.pathname = `${basePath}/auth/token`;
    tokenUrl.search = '';
    tokenUrl.hash = '';

    return {
      dashboardBaseUrl: dashboardUrl.toString(),
      tokenUrl: tokenUrl.toString(),
    };
  } catch {
    return null;
  }
}

/**
 * Extracts only the `club` query parameter from a Vercel/Node request object.
 *
 * @param {object} req - Incoming HTTP request object.
 * @returns {string} Trimmed club filter or empty string.
 */
export function extractClubParam(req) {
  const queryClub = req?.query?.club;
  if (queryClub !== undefined && queryClub !== null) {
    const value = Array.isArray(queryClub) ? queryClub[0] : queryClub;
    return typeof value === 'string' ? value.trim() : '';
  }

  if (typeof req?.url === 'string' && req.url.length > 0) {
    try {
      const parsed = new URL(req.url, 'http://localhost');
      return (parsed.searchParams.get('club') || '').trim();
    } catch {
      return '';
    }
  }

  return '';
}

/**
 * Requests a short-lived Bearer token from the upstream `/auth/token` endpoint
 * using HMAC-SHA256 request signing.
 *
 * @param {object} options
 * @param {string} options.tokenUrl
 * @param {string} options.apiKey
 * @param {string} options.signingSecret
 * @param {number} options.timeoutMs
 * @param {typeof fetch} options.fetchImpl
 * @returns {Promise<{ token: string, ttl: number }>}
 */
async function requestUpstreamToken({ tokenUrl, apiKey, signingSecret, timeoutMs, fetchImpl }) {
  const timestamp = String(Math.floor(Date.now() / 1000));
  const nonce = crypto.randomUUID();
  const signature = crypto
    .createHmac('sha256', signingSecret)
    .update(`${timestamp}.${nonce}`)
    .digest('hex');

  const response = await fetchImpl(tokenUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Api-Key': apiKey,
      'X-Timestamp': timestamp,
      'X-Nonce': nonce,
      'X-Signature': signature,
    },
    signal: AbortSignal.timeout(timeoutMs),
  });

  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data?.token) {
    const err = new Error(`Upstream auth failed with status ${response.status}`);
    err.upstreamStatus = response.status;
    throw err;
  }

  const parsedTtl = Number(data.ttl);
  return {
    token: String(data.token),
    ttl: Number.isFinite(parsedTtl) && parsedTtl > 0 ? parsedTtl : 300,
  };
}

/**
 * Fetches dashboard data from the upstream Lambda API using server-only credentials.
 *
 * @param {object} [options]
 * @param {string} [options.configuredApiUrl] - Trusted server-configured base API URL.
 * @param {string} [options.apiKey] - Server-side API key.
 * @param {string} [options.signingSecret] - Server-side HMAC signing secret.
 * @param {string} [options.club] - Optional club filter forwarded as `?club=`.
 * @param {number} [options.timeoutMs] - Upstream request timeout in milliseconds.
 * @param {typeof fetch} [options.fetchImpl] - Fetch implementation (injectable for tests).
 * @returns {Promise<{ status: number, headers: Record<string, string>, body: object }>}
 */
export async function fetchDashboardData({
  configuredApiUrl,
  apiKey,
  signingSecret,
  club,
  timeoutMs = DEFAULT_TIMEOUT_MS,
  fetchImpl = fetch,
} = {}) {
  const upstream = resolveUpstreamUrls(configuredApiUrl);
  if (!upstream) {
    console.error('[api/dashboard] Missing or invalid server-configured API_URL');
    return {
      status: 500,
      headers: { 'Cache-Control': NO_STORE_CACHE_CONTROL },
      body: { error: 'Server configuration error' },
    };
  }

  const resolvedApiKey = (apiKey ?? process.env.API_KEY ?? process.env.VITE_API_KEY ?? '').trim();
  const resolvedSecret = (signingSecret ?? process.env.API_SIGNING_SECRET ?? '').trim();

  if (Boolean(resolvedApiKey) !== Boolean(resolvedSecret)) {
    console.error('[api/dashboard] Incomplete server auth config: API_KEY and API_SIGNING_SECRET must both be set or both omitted');
    return {
      status: 500,
      headers: { 'Cache-Control': NO_STORE_CACHE_CONTROL },
      body: { error: 'Server configuration error' },
    };
  }

  const targetUrl = new URL(upstream.dashboardBaseUrl);
  if (typeof club === 'string' && club.trim()) {
    targetUrl.searchParams.set('club', club.trim());
  }

  const fetchUpstreamDashboard = (bearerToken) =>
    fetchImpl(targetUrl.toString(), {
      method: 'GET',
      headers: bearerToken
        ? { Accept: 'application/json', Authorization: `Bearer ${bearerToken}` }
        : { Accept: 'application/json' },
      signal: AbortSignal.timeout(timeoutMs),
    });

  let upstreamResponse;
  try {
    if (resolvedApiKey && resolvedSecret) {
      const cacheKey = `${upstream.tokenUrl}|${resolvedApiKey}`;
      const cached = _tokenCache.get(cacheKey);
      let token = cached && Date.now() < cached.expiresAt - TOKEN_SAFETY_BUFFER_MS ? cached.token : null;

      if (!token) {
        const minted = await requestUpstreamToken({
          tokenUrl: upstream.tokenUrl,
          apiKey: resolvedApiKey,
          signingSecret: resolvedSecret,
          timeoutMs,
          fetchImpl,
        });
        token = minted.token;
        _tokenCache.set(cacheKey, {
          token,
          expiresAt: Date.now() + minted.ttl * 1000,
        });
      }

      upstreamResponse = await fetchUpstreamDashboard(token);

      if (upstreamResponse.status === 401) {
        _tokenCache.delete(cacheKey);
        const refreshed = await requestUpstreamToken({
          tokenUrl: upstream.tokenUrl,
          apiKey: resolvedApiKey,
          signingSecret: resolvedSecret,
          timeoutMs,
          fetchImpl,
        });
        _tokenCache.set(cacheKey, {
          token: refreshed.token,
          expiresAt: Date.now() + refreshed.ttl * 1000,
        });
        upstreamResponse = await fetchUpstreamDashboard(refreshed.token);
      }
    } else {
      upstreamResponse = await fetchUpstreamDashboard(null);
    }
  } catch (err) {
    if (err?.name === 'TimeoutError' || err?.name === 'AbortError') {
      console.error('[api/dashboard] Upstream request timed out:', err);
      return {
        status: 504,
        headers: { 'Cache-Control': NO_STORE_CACHE_CONTROL },
        body: { error: 'Upstream request timed out' },
      };
    }

    console.error('[api/dashboard] Upstream request failed:', err);
    return {
      status: 502,
      headers: { 'Cache-Control': NO_STORE_CACHE_CONTROL },
      body: { error: 'Upstream service unavailable' },
    };
  }

  const payload = await upstreamResponse.json().catch(() => null);

  if (upstreamResponse.ok && payload && typeof payload === 'object') {
    return {
      status: 200,
      headers: { 'Cache-Control': SUCCESS_CACHE_CONTROL },
      body: payload,
    };
  }

  if (upstreamResponse.status >= 500 || !payload) {
    return {
      status: 502,
      headers: { 'Cache-Control': NO_STORE_CACHE_CONTROL },
      body: { error: 'Upstream service error' },
    };
  }

  return {
    status: upstreamResponse.status,
    headers: { 'Cache-Control': NO_STORE_CACHE_CONTROL },
    body: { error: payload.error || `Upstream request failed: ${upstreamResponse.status}` },
  };
}

/**
 * Vercel Serverless Function handler for GET /api/dashboard.
 *
 * @param {object} req - Incoming HTTP request object.
 * @param {object} res - Outgoing HTTP response object.
 * @returns {Promise<void>}
 */
export default async function handler(req, res) {
  if (req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    res.setHeader('Cache-Control', NO_STORE_CACHE_CONTROL);
    res.status(405).json({ error: 'Method Not Allowed' });
    return;
  }

  try {
    const result = await fetchDashboardData({
      club: extractClubParam(req),
    });
    for (const [headerName, headerValue] of Object.entries(result.headers)) {
      res.setHeader(headerName, headerValue);
    }
    res.status(result.status).json(result.body);
  } catch (err) {
    console.error('[api/dashboard] Unexpected error:', err);
    res.setHeader('Cache-Control', NO_STORE_CACHE_CONTROL);
    res.status(500).json({ error: 'Internal Server Error' });
  }
}
