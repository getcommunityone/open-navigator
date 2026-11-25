/**
 * Recover a tab that was open across a deploy (#936).
 *
 * Every build gives lazily loaded pages new hashed file names, and a deploy removes the old ones.
 * A tab opened before the deploy still holds the old chunk graph, so the first lazy page it opens
 * afterwards asks for a file that is gone (404), and the import fails ("Unable to preload CSS for
 * .../ScrollCue-C-uJ7YO1.css"). index.html itself is served no-cache, so reloading picks up the
 * new build and the page works.
 *
 * So: reload once. A sessionStorage guard stops a loop when the file is really missing (a broken
 * deploy); then the error reaches LazyRouteBoundary, which says what happened.
 */

const GUARD_KEY = 'stale-deploy-reload-at'
/** A second stale-chunk error within this window after a reload is not retried. */
const GUARD_WINDOW_MS = 30_000

const STALE_CHUNK_PATTERNS = [
  /unable to preload css/i, // Vite's CSS preload
  /failed to fetch dynamically imported module/i, // Chrome, Edge
  /error loading dynamically imported module/i, // Firefox
  /importing a module script failed/i, // Safari
  /loading (css )?chunk \S+ failed/i, // webpack-style wording some libraries rethrow
]

/** True when the error says a lazily loaded file could not be fetched (a stale or missing chunk). */
export function isStaleChunkError(error: unknown): boolean {
  const message =
    error instanceof Error ? error.message : typeof error === 'string' ? error : ''
  return STALE_CHUNK_PATTERNS.some((re) => re.test(message))
}

export interface ReloadDeps {
  storage?: Pick<Storage, 'getItem' | 'setItem'> | null
  reload?: () => void
  now?: () => number
}

function defaultStorage(): Pick<Storage, 'getItem' | 'setItem'> | null {
  try {
    return window.sessionStorage
  } catch {
    return null // storage blocked (private mode, sandboxed frame)
  }
}

/**
 * Reload the page unless this tab already reloaded for a stale chunk in the last 30 seconds.
 * Returns true when it reloaded. Without usable storage it does not reload, because nothing
 * could stop a loop.
 */
export function reloadOnceForStaleDeploy(deps: ReloadDeps = {}): boolean {
  const storage = deps.storage === undefined ? defaultStorage() : deps.storage
  const now = (deps.now ?? Date.now)()
  const reload = deps.reload ?? (() => window.location.reload())
  if (!storage) return false
  try {
    const last = Number(storage.getItem(GUARD_KEY) ?? 0)
    if (Number.isFinite(last) && now - last < GUARD_WINDOW_MS) return false
    storage.setItem(GUARD_KEY, String(now))
  } catch {
    return false
  }
  reload()
  return true
}

/**
 * Listen for Vite's preload failures (fired for a lazy chunk's JS or CSS) and reload once.
 * When it reloads, the event is cancelled so the failed import isn't thrown into the page.
 */
export function installStaleDeployReload(target: Window = window, deps: ReloadDeps = {}): void {
  target.addEventListener('vite:preloadError', (event) => {
    if (reloadOnceForStaleDeploy(deps)) event.preventDefault()
  })
}
