import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { requestSignedToken } from './api/token.js'

function serverTokenProxyPlugin(env) {
  return {
    name: 'server-token-proxy',
    configureServer(server) {
      server.middlewares.use('/api/token', async (req, res) => {
        if (req.method !== 'POST') {
          res.statusCode = 405
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify({ error: 'Method Not Allowed' }))
          return
        }

        let rawBody = ''
        for await (const chunk of req) {
          rawBody += chunk
        }

        try {
          const payload = rawBody ? JSON.parse(rawBody) : {}
          const result = await requestSignedToken({
            apiUrl: payload.apiUrl || env.VITE_API_URL,
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
      })
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
