import { describe, expect, it, vi } from 'vitest'
import { installStaleDeployReload, isStaleChunkError, reloadOnceForStaleDeploy } from './staleDeploy'

function memoryStorage() {
  const m = new Map<string, string>()
  return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v) }
}

describe('isStaleChunkError (#936)', () => {
  it('recognises a missing lazy chunk in each browser wording and Vite CSS preload', () => {
    for (const msg of [
      'Unable to preload CSS for https://www.communityone.com/assets/ScrollCue-C-uJ7YO1.css',
      'Failed to fetch dynamically imported module: https://x/assets/DataStory-abc.js',
      'error loading dynamically imported module: https://x/assets/DataStory-abc.js',
      'Importing a module script failed.',
    ]) {
      expect(isStaleChunkError(new Error(msg))).toBe(true)
    }
  })

  it('does not treat other errors as stale chunks', () => {
    expect(isStaleChunkError(new Error('x is not a function'))).toBe(false)
    expect(isStaleChunkError(undefined)).toBe(false)
  })
})

describe('reloadOnceForStaleDeploy (#936)', () => {
  it('reloads once, then not again within 30 seconds, then again after', () => {
    const storage = memoryStorage()
    const reload = vi.fn()
    let t = 1_000_000
    const deps = { storage, reload, now: () => t }
    expect(reloadOnceForStaleDeploy(deps)).toBe(true)
    t += 5_000
    expect(reloadOnceForStaleDeploy(deps)).toBe(false) // still broken after the reload: show the message
    t += 30_000
    expect(reloadOnceForStaleDeploy(deps)).toBe(true) // a later deploy: recover again
    expect(reload).toHaveBeenCalledTimes(2)
  })

  it('does not reload without usable storage, since nothing could stop a loop', () => {
    const reload = vi.fn()
    expect(reloadOnceForStaleDeploy({ storage: null, reload })).toBe(false)
    expect(reload).not.toHaveBeenCalled()
  })
})

describe('installStaleDeployReload (#936)', () => {
  it('reloads on vite:preloadError and cancels the event so the failed import is not thrown', () => {
    const target = new EventTarget() as unknown as Window
    const reload = vi.fn()
    installStaleDeployReload(target, { storage: memoryStorage(), reload, now: () => 1_000_000 })
    const event = new Event('vite:preloadError', { cancelable: true })
    target.dispatchEvent(event)
    expect(reload).toHaveBeenCalledOnce()
    expect(event.defaultPrevented).toBe(true)
  })
})
