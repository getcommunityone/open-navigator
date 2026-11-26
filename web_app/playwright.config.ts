import { defineConfig, devices } from '@playwright/test'

/**
 * Accessibility checks (#1146; web_docs/docs/development/accessibility.md): axe on the key pages and a keyboard-only walk.
 * They run against a dev server that is already up (A11Y_BASE_URL, default the usual Vite on 5173). Files end in `.e2e.ts`
 * so vitest leaves them alone.
 */
export default defineConfig({
  testDir: './e2e',
  testMatch: /.*\.e2e\.ts$/,
  timeout: 90_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.A11Y_BASE_URL ?? 'http://localhost:5173',
    viewport: { width: 1280, height: 900 },
    trace: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } } }],
})
