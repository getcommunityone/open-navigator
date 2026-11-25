/**
 * Recover a tab that was open across a deploy (#936).
 *
 * Every build gives lazily loaded pages new hashed file names, and a deploy removes the old ones.
 * A tab opened before the deploy still holds the old chunk graph, so the first lazy page it opens
 * afterwards asks for a file that is gone (404), and the import fails ("Unable to preload CSS for
 * .../ScrollCue-C-uJ7YO1.css"). Reloading fetches the new index.html and its new file names:
 * the server sends index.html no-cache, and the PWA service worker (skipWaiting + clientsClaim)
 * has normally already swapped to the new precache by the time the old files are gone. If an old
 * worker is still in control, the one automatic reload may land on the old page again; the guard
 * below then stops, and the message asks for a manual reload (see huggingface-spaces.md).
 *
 * So: reload once per failing file. The guard is the failing message (a 404 for the same file
 * after the reload means the deploy really lacks it) plus a 30 second window. The event is NOT
 * cancelled: cancelling makes Vite resolve the import to undefined, which React.lazy turns into an
 * unrelated TypeError. The real error reaches LazyRouteBoundary, which shows "Loading the latest
 * version…" while isStaleReloadPending() is true.
 */

const GUARD_KEY = 'stale-deploy-reload'
/** Any second stale-chunk error within this window after a reload is not retried. */
const GUARD_WINDOW_MS = 30_000

const STALE_CHUNK_PATTERNS = [
  /unable to preload css/i, // Vite's CSS preload
  /failed to fetch dynamically imported module/i, // Chrome, Edge
  /error loading dynamically imported module/i, // Firefox
  /importing a module script failed/i, // Safari
  /loading (css )?chunk \S+ failed/i, // webpack-style wording some libraries rethrow
]

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : typeof error === 'string' ? error : ''
}

/** True when the error says a lazily loaded file could not be fetched (a stale or missing chunk). */
export function isStaleChunkError(error: unknown): boolean {
  const message = messageOf(error)
  return STALE_CHUNK_PATTERNS.some((re) => re.test(message))
}

let reloadPending = false

/** True once this page has asked for a stale-deploy reload and is waiting for the new document. */
export function isStaleReloadPending(): boolean {
  return reloadPending
}

export interface ReloadDeps {
  storage?: Pick<Storage, 'getItem' | 'setItem'> | null
  reload?: () => void
  now?: () => number
  online?: () => boolean
}

function defaultStorage(): Pick<Storage, 'getItem' | 'setItem'> | null {
  try {
    return window.sessionStorage
  } catch {
    return null // storage blocked (private mode, sandboxed frame)
  }
}

function defaultOnline(): boolean {
  return typeof navigator === 'undefined' || navigator.onLine !== false
}

/**
 * Reload the page for a stale chunk, unless:
 *  - the browser says it is offline (a network failure looks the same, and reloading offline
 *    would replace a working page with the browser's offline page);
 *  - this tab already reloaded for the same failing file (the deploy really lacks it);
 *  - this tab reloaded for any stale chunk in the last 30 seconds;
 *  - there is no usable storage (nothing could stop a loop).
 * Returns true when it reloaded (or a reload is already pending).
 */
export function reloadOnceForStaleDeploy(error: unknown, deps: ReloadDeps = {}): boolean {
  if (reloadPending) return true
  if (!(deps.online ?? defaultOnline)()) return false
  const storage = deps.storage === undefined ? defaultStorage() : deps.storage
  if (!storage) return false
  const now = (deps.now ?? Date.now)()
  const message = messageOf(error)
  try {
    const last = JSON.parse(storage.getItem(GUARD_KEY) ?? 'null') as { at?: number; message?: string } | null
    if (last) {
      if (last.message === message) return false
      const age = now - Number(last.at ?? 0)
      // a negative age means the clock stepped back: treat the old mark as expired
      if (age >= 0 && age < GUARD_WINDOW_MS) return false
    }
    storage.setItem(GUARD_KEY, JSON.stringify({ at: now, message }))
  } catch {
    return false
  }
  reloadPending = true
  ;(deps.reload ?? (() => window.location.reload()))()
  return true
}

/**
 * Listen for Vite's preload failures (fired for a lazy chunk's JS or CSS) and reload once.
 * The event is left uncancelled, so the import still fails with its real error.
 */
export function installStaleDeployReload(target: Window = window, deps: ReloadDeps = {}): void {
  target.addEventListener('vite:preloadError', (event) => {
    const payload = (event as Event & { payload?: unknown }).payload
    reloadOnceForStaleDeploy(payload, deps)
  })
}

/** For tests only: forget a pending reload. */
export function resetStaleReloadForTests(): void {
  reloadPending = false
}
