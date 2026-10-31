/**
 * Server-side token proxy (/api/token) for Vercel Serverless & Vite Dev.
 *
 * Signs POST /auth/token requests using the server-only API_SIGNING_SECRET
 * so the HMAC secret is never exposed in the Vite client bundle.
 */
import crypto from 'node:crypto';

export async function requestSignedToken({ apiUrl, apiKey, signingSecret }) {
  const targetBaseUrl = (apiUrl || process.env.VITE_API_URL || '').trim().replace(/\/$/, '');
  const resolvedApiKey = (apiKey || process.env.API_KEY || process.env.VITE_API_KEY || '').trim();
  const resolvedSecret = (signingSecret || process.env.API_SIGNING_SECRET || '').trim();

  if (!targetBaseUrl) {
    return { status: 400, body: { error: 'Missing target API URL' } };
  }

  if (!resolvedApiKey || !resolvedSecret) {
    return { status: 200, body: { token: 'passthrough', ttl: 999999 } };
  }

  const timestamp = String(Math.floor(Date.now() / 1000));
  const nonce = crypto.randomUUID();
  const signature = crypto
    .createHmac('sha256', resolvedSecret)
    .update(`${timestamp}.${nonce}`)
    .digest('hex');

  const upstreamResponse = await fetch(`${targetBaseUrl}/auth/token`, {
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

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'Method Not Allowed' });
    return;
  }

  try {
    const payload = typeof req.body === 'string' && req.body ? JSON.parse(req.body) : (req.body || {});
    const result = await requestSignedToken({
      apiUrl: payload.apiUrl,
      apiKey: req.headers['x-api-key'],
    });
    res.status(result.status).json(result.body);
  } catch (err) {
    res.status(500).json({ error: err.message || 'Internal Server Error' });
  }
}

