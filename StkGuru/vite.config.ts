import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  // Set the third parameter to all env regardless of the `VITE_` prefix.
  loadEnv(mode, process.cwd(), '')
  
  // Environment-specific configurations
  const envConfigs = {
    development: {
      apiBaseUrl: 'http://localhost',
      proxyTarget: 'http://localhost',
    },
    test: {
      apiBaseUrl: 'http://localhost:8080',
      proxyTarget: 'http://localhost:8080',
    },
    staging: {
      apiBaseUrl: 'https://staging-api.stkguru.com',
      proxyTarget: 'https://staging-api.stkguru.com',
    },
    production: {
      apiBaseUrl: 'https://api.stkguru.com',
      proxyTarget: 'https://api.stkguru.com',
    },
    ghpages: {
      apiBaseUrl: 'https://stk.guru',
      proxyTarget: '',
    },
    'ghpages-dev': {
      // For ghpages-dev, we serve static files from public/api/, so no proxy needed
      apiBaseUrl: '', // will be set to window.location.origin in client
      proxyTarget: '', // no proxy needed for static files
    },
  }

  const currentEnv = mode || 'development'
  const config = envConfigs[currentEnv as keyof typeof envConfigs] || envConfigs.development

  // For ghpages-dev, set apiBaseUrl/proxyTarget to window.location.origin if possible
  if (currentEnv === 'ghpages-dev') {
    // In Node.js context, we can't access window, so use a fallback
    const origin = 'http://localhost:5173'
    config.apiBaseUrl = origin
    config.proxyTarget = origin
  }

  return {
    plugins: [react()],
    define: {
      // Make environment variables available to the client
      __API_BASE_URL__: JSON.stringify(config.apiBaseUrl),
      __ENV__: JSON.stringify(currentEnv),
    },
    server: {
      ...((currentEnv !== 'ghpages' && currentEnv !== 'ghpages-dev') && {
        proxy: {
          '/api': {
            target: config.proxyTarget,
            changeOrigin: true,
            secure: false,
            configure: (proxy) => {
              proxy.on('error', (err) => {
                // eslint-disable-next-line no-console
                console.log('Proxy error:', err)
              })
              proxy.on('proxyReq', (_, req) => {
                // eslint-disable-next-line no-console
                console.log('Sending Request to the Target:', req.method, req.url)
              })
              proxy.on('proxyRes', (proxyRes, req) => {
                // eslint-disable-next-line no-console
                console.log('Received Response from the Target:', proxyRes.statusCode, req.url)
              })
            },
          },
        },
      }),
      hmr: {
        // Fix WebSocket connection issues
        port: 5173,
        host: 'localhost',
        protocol: 'ws',
        timeout: 30000,
        // Disable HMR overlay for service worker errors
        overlay: false,
      },
      // Add better error handling and logging
      watch: {
        usePolling: false,
        interval: 1000,
      },
    },
    // Optimize for development
    optimizeDeps: {
      include: ['react', 'react-dom', 'highcharts', 'highcharts-react-official']
    },
    // Disable service worker for development
    worker: {
      format: 'es'
    },
    // Build configuration
    build: {
      outDir: 'dist',
      sourcemap: currentEnv === 'development',
      rollupOptions: {
        output: {
          manualChunks: {
            vendor: ['react', 'react-dom'],
            charts: ['highcharts', 'highcharts-react-official'],
          },
        },
      },
    },
  }
})
