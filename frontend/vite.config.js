import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { requestSignedToken } from './api/token.js'

/**
 * Creates a Connect-compatible middleware handler for `/api/token` using
 * trusted server-side environment variables.
 *
 * @param {Record<string, string>} env - Loaded Vite environment variables.
 * @returns {(req: object, res: object) => Promise<void>} Middleware function.
 */
function createTokenProxyMiddleware(env) {
  return async (req, res) => {
    if (req.method !== 'POST') {
      res.statusCode = 405
      res.setHeader('Content-Type', 'application/json')
      res.end(JSON.stringify({ error: 'Method Not Allowed' }))
      return
    }

    try {
      const result = await requestSignedToken({
        configuredApiUrl: env.API_URL || env.VITE_API_URL,
        apiKey: req.headers['x-api-key'] || env.API_KEY || env.VITE_API_KEY,
        signingSecret: env.API_SIGNING_SECRET,
      })
      res.statusCode = result.status
      res.setHeader('Content-Type', 'application/json')
      res.end(JSON.stringify(result.body))
    } catch (err) {
      res.statusCode = 500
      res.setHeader('Content-Type', 'application/json')
      res.end(JSON.stringify({ error: err.message || 'Internal Server Error' }))
    }
  }
}

/**
 * Vite plugin that mounts the `/api/token` proxy route in both the
 * development server (`vite dev`) and preview server (`vite preview`).
 *
 * @param {Record<string, string>} env - Loaded Vite environment variables.
 * @returns {import('vite').Plugin} Vite plugin configuration object.
 */
function serverTokenProxyPlugin(env) {
  const tokenMiddleware = createTokenProxyMiddleware(env)
  return {
    name: 'server-token-proxy',
    configureServer(server) {
      server.middlewares.use('/api/token', tokenMiddleware)
    },
    configurePreviewServer(server) {
      server.middlewares.use('/api/token', tokenMiddleware)
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  return {
    plugins: [react(), serverTokenProxyPlugin(env)],
  }
})
