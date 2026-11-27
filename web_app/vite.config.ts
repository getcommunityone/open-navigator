import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import fs from 'fs'
import path from 'path'

/** Local writable @assistant-ui tree when root-owned node_modules blocks npm (#630). */
const auiVendor = path.resolve(__dirname, 'vendor/aui-nm/node_modules/@assistant-ui/react')
const auiAliases = fs.existsSync(auiVendor)
  ? {
      '@assistant-ui/react': path.resolve(
        __dirname,
        'vendor/aui-nm/node_modules/@assistant-ui/react',
      ),
      '@assistant-ui/core': path.resolve(
        __dirname,
        'vendor/aui-nm/node_modules/@assistant-ui/core',
      ),
      '@assistant-ui/store': path.resolve(
        __dirname,
        'vendor/aui-nm/node_modules/@assistant-ui/store',
      ),
      '@assistant-ui/tap': path.resolve(
        __dirname,
        'vendor/aui-nm/node_modules/@assistant-ui/tap',
      ),
    }
  : {}

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        navigateFallbackDenylist: [/^\/api/, /^\/docs/],
        // The main bundle is ~3 MB; vite-plugin-pwa 2.x fails the build when a
        // precached asset exceeds its 2 MB default. 5 MB leaves headroom.
        maximumFileSizeToCacheInBytes: 5 * 1024 * 1024,
      },
      devOptions: {
        enabled: false
      },
      manifest: {
        name: 'Open Navigator',
        short_name: 'Navigator',
        description: 'Track jurisdictions, nonprofits, and local policy with open data and AI.',
        theme_color: '#ffffff',
        icons: [
          {
            src: '/communityone_logo_64.png',
            sizes: '64x64',
            type: 'image/png'
          },
          {
            src: '/communityone_logo_192.png',
            sizes: '192x192',
            type: 'image/png'
          },
          {
            src: '/communityone_logo_512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable'
          }
        ]
      }
    })
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      ...auiAliases,
    },
  },
  server: {
    port: 5173,
    // Fail loudly if 5173 is taken instead of silently moving to 5174: Google sign-in
    // redirects to 5173, so a hop breaks login with no error (#787).
    strictPort: true,
    // WSL2's inotify often misses edits made from the Linux side, so HMR never
    // fires and the browser keeps serving the build from when Vite started.
    // Polling reliably picks up changes (slightly higher idle CPU is the trade).
    watch: { usePolling: true, interval: 200 },
    proxy: {
      '/api': {
        // VITE_API_PROXY points a second dev server at its own API (agents, the a11y checks); 8001 is the default.
        target: process.env.VITE_API_PROXY ?? 'http://localhost:8001',
        changeOrigin: true,
        proxyTimeout: 120_000,
        timeout: 120_000,
        // Don't follow redirects - let browser handle OAuth redirects
        followRedirects: false,
        configure: (proxy: any, _options) => {
          proxy.on('error', (err: any, _req: any, _res: any) => {
            console.log('proxy error', err);
          });
          proxy.on('proxyReq', (proxyReq: any, req: any, _res: any) => {
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
