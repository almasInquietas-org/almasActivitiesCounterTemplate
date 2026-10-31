/**
 * Server-side token proxy (/api/token) for Vercel Serverless & Vite Dev/Preview.
 *
 * Signs POST /auth/token requests using the server-only API_SIGNING_SECRET
 * so the HMAC secret is never exposed in the Vite client bundle.
 */
import crypto from 'node:crypto';

/**
 * Resolves and validates the upstream /auth/token URL strictly from trusted
 * server configuration, preventing caller-controlled SSRF targets.
 *
 * @param {string} [configuredApiUrl] - Trusted server-configured base API URL.
 * @returns {string|null} The full upstream `/auth/token` URL, or null if invalid/unset.
 */
export function resolveUpstreamTokenUrl(configuredApiUrl) {
  const rawBaseUrl = (
    configuredApiUrl ||
    process.env.API_URL ||
    process.env.VITE_API_URL ||
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
    parsed.pathname = `${basePath}/auth/token`;
    parsed.search = '';
    parsed.hash = '';
    return parsed.toString();
  } catch {
    return null;
  }
}

/**
 * Signs and forwards a token handshake request to the configured upstream `/auth/token` endpoint.
 *
 * @param {object} [options] - Trusted server-side configuration options.
 * @param {string} [options.configuredApiUrl] - Server-configured base API URL.
 * @param {string} [options.apiKey] - API key from header or server environment.
 * @param {string} [options.signingSecret] - HMAC signing secret from server environment.
 * @returns {Promise<{status: number, body: object}>} HTTP status code and JSON response body.
 */
export async function requestSignedToken({ configuredApiUrl, apiKey, signingSecret } = {}) {
  const upstreamTokenUrl = resolveUpstreamTokenUrl(configuredApiUrl);
  const resolvedApiKey = (apiKey || process.env.API_KEY || process.env.VITE_API_KEY || '').trim();
  const resolvedSecret = (signingSecret || process.env.API_SIGNING_SECRET || '').trim();

  if (!upstreamTokenUrl) {
    return { status: 500, body: { error: 'Missing or invalid server-configured target API URL' } };
  }

  if (!resolvedApiKey && !resolvedSecret) {
    return { status: 200, body: { token: 'passthrough', ttl: 999999 } };
  }

  if (!resolvedApiKey || !resolvedSecret) {
    return {
      status: 500,
      body: {
        error:
          'Incomplete server authentication configuration: both API_KEY and API_SIGNING_SECRET must be set, or both omitted for passthrough mode.',
      },
    };
  }

  const timestamp = String(Math.floor(Date.now() / 1000));
  const nonce = crypto.randomUUID();
  const signature = crypto
    .createHmac('sha256', resolvedSecret)
    .update(`${timestamp}.${nonce}`)
    .digest('hex');

  const upstreamResponse = await fetch(upstreamTokenUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Api-Key': resolvedApiKey,
      'X-Timestamp': timestamp,
      'X-Nonce': nonce,
      'X-Signature': signature,
    },
  });

  const data = await upstreamResponse.json().catch(() => ({}));
  return {
    status: upstreamResponse.status,
    body: upstreamResponse.ok
      ? { token: data.token, ttl: data.ttl ?? 300 }
      : { error: data.error || `Upstream auth failed: ${upstreamResponse.status}` },
  };
}

/**
 * Vercel Serverless Function handler for POST /api/token.
 *
 * @param {object} req - Incoming HTTP request object.
 * @param {object} res - Outgoing HTTP response object.
 * @returns {Promise<void>}
 */
export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method Not Allowed' });
    return;
  }

  try {
    const result = await requestSignedToken({
      apiKey: req.headers['x-api-key'],
    });
    res.status(result.status).json(result.body);
  } catch (err) {
    res.status(500).json({ error: err.message || 'Internal Server Error' });
  }
}
