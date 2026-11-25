import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  installStaleDeployReload,
  isStaleChunkError,
  isStaleReloadPending,
  reloadOnceForStaleDeploy,
  resetStaleReloadForTests,
} from './staleDeploy'

function memoryStorage() {
  const m = new Map<string, string>()
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) }
}

const CSS_GONE = new Error('Unable to preload CSS for https://x/assets/ScrollCue-C-uJ7YO1.css')
const JS_GONE = new Error('Failed to fetch dynamically imported module: https://x/assets/DataStory-abc.js')

afterEach(() => resetStaleReloadForTests())

describe('isStaleChunkError (#936)', () => {
  it('recognises a missing lazy chunk in each browser wording and Vite CSS preload', () => {
    for (const msg of [
      CSS_GONE.message,
      JS_GONE.message,
      'error loading dynamically imported module: https://x/assets/DataStory-abc.js',
      'Importing a module script failed.',
    ]) {
      expect(isStaleChunkError(new Error(msg))).toBe(true)
    }
  })

  it('does not treat other errors as stale chunks', () => {
    expect(isStaleChunkError(new Error('x is not a function'))).toBe(false)
    expect(isStaleChunkError(new TypeError("Cannot read properties of undefined (reading 'default')"))).toBe(false)
    expect(isStaleChunkError(undefined)).toBe(false)
  })
})

describe('reloadOnceForStaleDeploy (#936)', () => {
  it('reloads once and marks the reload pending, so the boundary can say so', () => {
    const reload = vi.fn()
    expect(reloadOnceForStaleDeploy(CSS_GONE, { storage: memoryStorage(), reload, now: () => 1_000_000, online: () => true })).toBe(true)
    expect(reload).toHaveBeenCalledOnce()
    expect(isStaleReloadPending()).toBe(true)
    // the JS failure that follows the CSS one in the same page doesn't reload twice
    expect(reloadOnceForStaleDeploy(JS_GONE, { storage: memoryStorage(), reload, now: () => 1_000_001, online: () => true })).toBe(true)
    expect(reload).toHaveBeenCalledOnce()
  })

  it('after the reload: never again for the same file, not within 30s for another, again after that', () => {
    const storage = memoryStorage()
    const reload = vi.fn()
    let t = 1_000_000
    const deps = { storage, reload, now: () => t, online: () => true }
    expect(reloadOnceForStaleDeploy(JS_GONE, deps)).toBe(true)
    resetStaleReloadForTests() // the new page
    t += 120_000
    expect(reloadOnceForStaleDeploy(JS_GONE, deps)).toBe(false) // same file still missing: the deploy lacks it
    expect(reloadOnceForStaleDeploy(new Error('Failed to fetch dynamically imported module: https://x/assets/Other-1.js'), { ...deps, now: () => 1_000_000 + 5_000 })).toBe(false) // within 30s
    t += 1
    expect(reloadOnceForStaleDeploy(new Error('Failed to fetch dynamically imported module: https://x/assets/Other-1.js'), deps)).toBe(true)
    expect(reload).toHaveBeenCalledTimes(2)
  })

  it('treats a mark from the future (clock stepped back) as expired', () => {
    const storage = memoryStorage()
    storage.setItem('stale-deploy-reload', JSON.stringify({ at: 9_000_000, message: 'old' }))
    const reload = vi.fn()
    expect(reloadOnceForStaleDeploy(JS_GONE, { storage, reload, now: () => 1_000_000, online: () => true })).toBe(true)
  })

  it('does not reload offline, where a network failure looks the same', () => {
    const reload = vi.fn()
    expect(reloadOnceForStaleDeploy(JS_GONE, { storage: memoryStorage(), reload, online: () => false })).toBe(false)
    expect(reload).not.toHaveBeenCalled()
  })

  it('does not reload without usable storage, since nothing could stop a loop', () => {
    const reload = vi.fn()
    expect(reloadOnceForStaleDeploy(JS_GONE, { storage: null, reload, online: () => true })).toBe(false)
    expect(reload).not.toHaveBeenCalled()
  })
})

describe('installStaleDeployReload (#936)', () => {
  it('reloads on vite:preloadError but leaves the event uncancelled, so the import fails with its real error', () => {
    const target = new EventTarget() as unknown as Window
    const reload = vi.fn()
    installStaleDeployReload(target, { storage: memoryStorage(), reload, now: () => 1_000_000, online: () => true })
    const event = Object.assign(new Event('vite:preloadError', { cancelable: true }), { payload: CSS_GONE })
    target.dispatchEvent(event)
    expect(reload).toHaveBeenCalledOnce()
    // cancelling would make Vite resolve the import to undefined, which React.lazy turns into a TypeError
    expect(event.defaultPrevented).toBe(false)
  })
})
