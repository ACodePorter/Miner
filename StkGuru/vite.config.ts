import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost',
        changeOrigin: true,
        secure: false,
      }
    },
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
    }
  },
  // Optimize for development
  optimizeDeps: {
    include: ['react', 'react-dom', 'highcharts', 'highcharts-react-official']
  },
  // Disable service worker for development
  worker: {
    format: 'es'
  }
})
