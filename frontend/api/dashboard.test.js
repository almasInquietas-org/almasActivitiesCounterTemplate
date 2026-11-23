import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import { afterEach, beforeEach, describe, it } from 'node:test';
import handler, {
  clearServerTokenCache,
  extractClubParam,
  fetchDashboardData,
} from './dashboard.js';

function createMockRes() {
  return {
    statusCode: 200,
    headers: {},
    body: null,
    setHeader(name, value) {
      this.headers[name] = value;
    },
    status(code) {
      this.statusCode = code;
      return this;
    },
    json(payload) {
      this.body = payload;
      return this;
    },
  };
}

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('GET /api/dashboard BFF', () => {
  const originalFetch = globalThis.fetch;
  const savedEnv = {
    API_URL: process.env.API_URL,
    VITE_API_URL: process.env.VITE_API_URL,
    API_KEY: process.env.API_KEY,
    VITE_API_KEY: process.env.VITE_API_KEY,
    API_SIGNING_SECRET: process.env.API_SIGNING_SECRET,
  };

  beforeEach(() => {
    clearServerTokenCache();
    delete process.env.API_URL;
    delete process.env.VITE_API_URL;
    delete process.env.API_KEY;
    delete process.env.VITE_API_KEY;
    delete process.env.API_SIGNING_SECRET;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    for (const [key, val] of Object.entries(savedEnv)) {
      if (val === undefined) {
        delete process.env[key];
      } else {
        process.env[key] = val;
      }
    }
  });

  it('rejects non-GET methods with 405 and Allow: GET', async () => {
    const res = createMockRes();
    await handler({ method: 'POST', headers: {} }, res);

    assert.equal(res.statusCode, 405);
    assert.equal(res.headers.Allow, 'GET');
    assert.equal(res.headers['Cache-Control'], 'no-store');
    assert.deepEqual(res.body, { error: 'Method Not Allowed' });
  });

  it('serves cached dashboard JSON in passthrough mode', async () => {
    process.env.API_URL = 'https://lambda.example.com/';
    const calls = [];
    globalThis.fetch = async (url, init) => {
      calls.push({ url, init });
      return jsonResponse(200, { total_km: 120.5, total_activities: 4 });
    };

    const res = createMockRes();
    await handler({ method: 'GET', url: '/api/dashboard', headers: {} }, res);

    assert.equal(res.statusCode, 200);
    assert.equal(res.headers['Cache-Control'], 'public, s-maxage=30, stale-while-revalidate=60');
    assert.deepEqual(res.body, { total_km: 120.5, total_activities: 4 });
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, 'https://lambda.example.com/');
    assert.equal(calls[0].init.headers.Authorization, undefined);
    assert.ok(calls[0].init.signal instanceof AbortSignal);
  });

  it('signs /auth/token server-to-server, caches token, and refreshes once on 401', async () => {
    const calls = [];
    let tokenCounter = 0;
    let dashboardFailuresLeft = 1;

    const fakeFetch = async (url, init) => {
      calls.push({ url, init });
      if (url.endsWith('/auth/token')) {
        tokenCounter += 1;
        const ts = init.headers['X-Timestamp'];
        const nonce = init.headers['X-Nonce'];
        const expectedSig = crypto
          .createHmac('sha256', 'server-secret')
          .update(`${ts}.${nonce}`)
          .digest('hex');
        assert.equal(init.headers['X-Api-Key'], 'server-key');
        assert.equal(init.headers['X-Signature'], expectedSig);
        return jsonResponse(200, { token: `tok-${tokenCounter}`, ttl: 300 });
      }

      if (calls.filter((c) => !c.url.endsWith('/auth/token')).length === 1) {
        return jsonResponse(200, { total_km: 10 });
      }

      if (dashboardFailuresLeft > 0) {
        dashboardFailuresLeft -= 1;
        return jsonResponse(401, { error: 'Expired' });
      }

      return jsonResponse(200, { total_km: 20 });
    };

    const first = await fetchDashboardData({
      configuredApiUrl: 'https://lambda.example.com',
      apiKey: 'server-key',
      signingSecret: 'server-secret',
      fetchImpl: fakeFetch,
    });
    assert.equal(first.status, 200);
    assert.deepEqual(first.body, { total_km: 10 });

    // Second call reuses cached tok-1, receives 401, refreshes to tok-2, and retries once
    const second = await fetchDashboardData({
      configuredApiUrl: 'https://lambda.example.com',
      apiKey: 'server-key',
      signingSecret: 'server-secret',
      fetchImpl: fakeFetch,
    });
    assert.equal(second.status, 200);
    assert.deepEqual(second.body, { total_km: 20 });
    assert.equal(tokenCounter, 2);
  });

  it('ignores untrusted client x-api-key and authorization headers', async () => {
    process.env.API_URL = 'https://lambda.example.com';
    process.env.API_KEY = 'real-server-key';
    process.env.API_SIGNING_SECRET = 'real-server-secret';

    const seenApiKeys = [];
    globalThis.fetch = async (url, init) => {
      if (url.endsWith('/auth/token')) {
        seenApiKeys.push(init.headers['X-Api-Key']);
        return jsonResponse(200, { token: 'server-tok', ttl: 300 });
      }
      assert.equal(init.headers.Authorization, 'Bearer server-tok');
      return jsonResponse(200, { total_km: 50 });
    };

    const res = createMockRes();
    await handler(
      {
        method: 'GET',
        url: '/api/dashboard',
        headers: {
          'x-api-key': 'attacker-key',
          authorization: 'Bearer attacker-token',
        },
      },
      res,
    );

    assert.equal(res.statusCode, 200);
    assert.deepEqual(seenApiKeys, ['real-server-key']);
  });

  it('forwards only the club query parameter upstream', async () => {
    process.env.API_URL = 'https://lambda.example.com';
    let requestedUrl = '';
    globalThis.fetch = async (url) => {
      requestedUrl = url;
      return jsonResponse(200, { total_km: 33 });
    };

    const req = {
      method: 'GET',
      url: '/api/dashboard?view=counter&club=almas_inquietas&utm_source=ig',
      headers: {},
    };
    assert.equal(extractClubParam(req), 'almas_inquietas');

    const res = createMockRes();
    await handler(req, res);

    assert.equal(res.statusCode, 200);
    assert.equal(requestedUrl, 'https://lambda.example.com/?club=almas_inquietas');
  });

  it('returns 504 with no-store on upstream timeout', async () => {
    const result = await fetchDashboardData({
      configuredApiUrl: 'https://lambda.example.com',
      fetchImpl: async () => {
        throw new DOMException('Request timed out', 'TimeoutError');
      },
    });

    assert.equal(result.status, 504);
    assert.equal(result.headers['Cache-Control'], 'no-store');
    assert.deepEqual(result.body, { error: 'Upstream request timed out' });
  });

  it('returns sanitized 502 with no-store on upstream network error', async () => {
    const result = await fetchDashboardData({
      configuredApiUrl: 'https://lambda.example.com',
      fetchImpl: async () => {
        throw new Error('ECONNREFUSED 10.0.0.5:5432');
      },
    });

    assert.equal(result.status, 502);
    assert.equal(result.headers['Cache-Control'], 'no-store');
    assert.deepEqual(result.body, { error: 'Upstream service unavailable' });
  });

  it('returns 500 with no-store when auth configuration is incomplete', async () => {
    const result = await fetchDashboardData({
      configuredApiUrl: 'https://lambda.example.com',
      apiKey: 'only-key-no-secret',
      signingSecret: '',
      fetchImpl: async () => jsonResponse(200, {}),
    });

    assert.equal(result.status, 500);
    assert.equal(result.headers['Cache-Control'], 'no-store');
    assert.deepEqual(result.body, { error: 'Server configuration error' });
  });
});
