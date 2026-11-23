import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { extractClubParam, fetchDashboardData } from './api/dashboard.js'

/**
 * Creates a Connect-compatible middleware handler for `/api/dashboard` using
 * trusted server-side environment variables.
 *
 * @param {Record<string, string>} env - Loaded Vite environment variables.
 * @returns {(req: object, res: object) => Promise<void>} Middleware function.
 */
function createDashboardProxyMiddleware(env) {
  return async (req, res) => {
    if (req.method !== 'GET') {
      res.statusCode = 405
      res.setHeader('Allow', 'GET')
      res.setHeader('Cache-Control', 'no-store')
      res.setHeader('Content-Type', 'application/json')
      res.end(JSON.stringify({ error: 'Method Not Allowed' }))
      return
    }

    try {
      const result = await fetchDashboardData({
        configuredApiUrl: env.API_URL || env.VITE_API_URL,
        apiKey: env.API_KEY || env.VITE_API_KEY,
        signingSecret: env.API_SIGNING_SECRET,
        club: extractClubParam(req),
      })
      res.statusCode = result.status
      for (const [headerName, headerValue] of Object.entries(result.headers)) {
        res.setHeader(headerName, headerValue)
      }
      res.setHeader('Content-Type', 'application/json')
      res.end(JSON.stringify(result.body))
    } catch (err) {
      console.error('[vite /api/dashboard] Unexpected error:', err)
      res.statusCode = 500
      res.setHeader('Cache-Control', 'no-store')
      res.setHeader('Content-Type', 'application/json')
      res.end(JSON.stringify({ error: 'Internal Server Error' }))
    }
  }
}

/**
 * Vite plugin that mounts the `/api/dashboard` BFF route in both the
 * development server (`vite dev`) and preview server (`vite preview`).
 *
 * @param {Record<string, string>} env - Loaded Vite environment variables.
 * @returns {import('vite').Plugin} Vite plugin configuration object.
 */
function serverDashboardProxyPlugin(env) {
  const dashboardMiddleware = createDashboardProxyMiddleware(env)
  return {
    name: 'server-dashboard-proxy',
    configureServer(server) {
      server.middlewares.use('/api/dashboard', dashboardMiddleware)
    },
    configurePreviewServer(server) {
      server.middlewares.use('/api/dashboard', dashboardMiddleware)
    },
  }
}

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '')
  return {
    plugins: [react(), serverDashboardProxyPlugin(env)],
  }
})
