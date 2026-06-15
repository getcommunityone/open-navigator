import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    // WSL2's inotify often misses edits made from the Linux side, so HMR never
    // fires and the browser keeps serving the build from when Vite started.
    // Polling reliably picks up changes (slightly higher idle CPU is the trade).
    watch: { usePolling: true, interval: 200 },
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        proxyTimeout: 120_000,
        timeout: 120_000,
        // Don't follow redirects - let browser handle OAuth redirects
        followRedirects: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq, req, _res) => {
            console.log('Proxying:', req.method, req.url, '→', proxyReq.path);
          });
        },
      },
    },
  },
  build: {
    outDir: '../api/static',
    emptyOutDir: true,
  },
})
