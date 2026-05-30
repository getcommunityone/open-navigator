/**
 * Dev-only: swallow known browser-extension promise rejections on the page.
 *
 * Does not affect extension service workers (`background.js`); disable extensions
 * or use a clean browser profile to silence those.
 */

const EXTENSION_REJECTION =
  /message channel closed|asynchronous response by returning true/i

let hintShown = false

function showExtensionHint() {
  if (hintShown || import.meta.env.PROD) return
  hintShown = true
  console.info(
    '[open-navigator] Console errors from background.js (chrome-extension://) come from a ' +
      'browser extension, not this app. Use Incognito with extensions off, or disable the ' +
      'extension at chrome://extensions (match the ID in DevTools → Sources → background.js).',
  )
}

export function installExtensionConsoleNoiseFilter() {
  if (import.meta.env.PROD || typeof window === 'undefined') return

  window.addEventListener(
    'unhandledrejection',
    (event) => {
      const msg = String(
        (event.reason as Error)?.message ?? event.reason ?? '',
      )
      if (EXTENSION_REJECTION.test(msg)) {
        event.preventDefault()
        showExtensionHint()
      }
    },
    true,
  )

  window.addEventListener(
    'error',
    (event) => {
      const src = String(event.filename ?? '')
      if (
        src.includes('chrome-extension://') ||
        src.includes('moz-extension://')
      ) {
        event.preventDefault()
        showExtensionHint()
      }
    },
    true,
  )
}
