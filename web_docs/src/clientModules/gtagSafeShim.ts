/**
 * Backup if head inline is blocked: ensure `window.gtag` before the gtag plugin's
 * `onRouteDidUpdate` runs on SPA navigations.
 */
function ensureGtagStub(): void {
  if (typeof window === 'undefined') return
  const w = window as unknown as { dataLayer?: unknown[]; gtag?: unknown }
  w.dataLayer = w.dataLayer ?? []
  if (typeof w.gtag === 'function') return
  w.gtag = function gtag(...args: unknown[]) {
    w.dataLayer!.push(args)
  }
}

ensureGtagStub()
if (typeof window !== 'undefined') {
  window.addEventListener('load', ensureGtagStub)
}
