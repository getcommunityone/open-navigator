import { afterEach, describe, expect, it, vi } from 'vitest'
import { cueLength, cueNotes, createSoundBoard, readSoundSetting, SOUND_KEY, type Cue } from './stanceSound'

const CUES: Cue[] = ['open', 'question', 'lock', 'bar', 'finish']

describe('cueNotes', () => {
  it('gives every cue at least one audible, in-range note', () => {
    for (const c of CUES) {
      const notes = cueNotes(c)
      expect(notes.length).toBeGreaterThan(0)
      for (const n of notes) {
        expect(n.freq).toBeGreaterThan(80)
        expect(n.freq).toBeLessThan(4000)
        expect(n.start).toBeGreaterThanOrEqual(0)
        expect(n.duration).toBeGreaterThan(0)
      }
    }
  })
  it('keeps the short cues under 400 ms and the finish within 1.2 s', () => {
    for (const c of CUES.filter((x) => x !== 'finish')) expect(cueLength(c)).toBeLessThan(0.4)
    expect(cueLength('finish')).toBeLessThanOrEqual(1.2)
  })
  it('steps the bar cue up per scope and clamps the step', () => {
    const f = (s: number) => cueNotes('bar', s)[0]!.freq
    expect(f(1)).toBeGreaterThan(f(0))
    expect(f(2)).toBeGreaterThan(f(1))
    expect(f(99)).toBe(f(4))
    expect(f(-3)).toBe(f(0))
  })
  it('keeps the lock cue on a single pitch, so it cannot sound like right or wrong', () => {
    expect(new Set(cueNotes('lock').map((n) => n.freq)).size).toBe(1)
  })
})

/** A minimal window: a storage and listeners (the unit tests run without a DOM). */
function fakeWindow(store: Record<string, string> | 'throws', extra: Record<string, unknown> = {}) {
  const listeners = new Map<string, Array<() => void>>()
  const localStorage =
    store === 'throws'
      ? {
          getItem: () => {
            throw new Error('blocked')
          },
          setItem: () => {
            throw new Error('blocked')
          },
        }
      : { getItem: (k: string) => store[k] ?? null, setItem: (k: string, v: string) => void (store[k] = v) }
  const w = {
    localStorage,
    addEventListener: (e: string, f: () => void) => listeners.set(e, [...(listeners.get(e) ?? []), f]),
    removeEventListener: () => {},
    fire: (e: string) => (listeners.get(e) ?? []).forEach((f) => f()),
    ...extra,
  }
  vi.stubGlobal('window', w)
  return w
}

describe('the sound board', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('defaults to on and remembers the choice', () => {
    const store: Record<string, string> = {}
    fakeWindow(store)
    expect(readSoundSetting()).toBe(true)
    const b = createSoundBoard()
    b.setEnabled(false)
    expect(store[SOUND_KEY]).toBe('off')
    expect(b.enabled).toBe(false)
    expect(readSoundSetting()).toBe(false)
    b.setEnabled(true)
    expect(store[SOUND_KEY]).toBe('on')
  })
  it('does not throw when storage throws', () => {
    fakeWindow('throws')
    expect(readSoundSetting()).toBe(true)
    const b = createSoundBoard()
    expect(() => b.setEnabled(false)).not.toThrow()
  })
  it('makes no audio context before the first gesture, then one, and is a no-op without Web Audio', () => {
    const made = vi.fn()
    class Ctx {
      state = 'running'
      currentTime = 0
      destination = {}
      constructor() {
        made()
      }
      createGain() {
        return { gain: { value: 0, setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {} }
      }
      createOscillator() {
        return { frequency: { value: 0 }, connect() {}, start: vi.fn(), stop() {} }
      }
    }
    const w = fakeWindow({}, { AudioContext: Ctx })
    const b = createSoundBoard()
    b.play('open')
    expect(made).not.toHaveBeenCalled()
    w.fire('pointerdown')
    expect(made).toHaveBeenCalledTimes(1)
    b.play('open')
    b.play('finish')
    expect(made).toHaveBeenCalledTimes(1)

    fakeWindow({})
    const c = createSoundBoard()
    c.play('open')
    const d = createSoundBoard()
    expect(() => d.play('lock')).not.toThrow()
  })
  it('stays silent when sound is off', () => {
    const made = vi.fn()
    const w = fakeWindow({ [SOUND_KEY]: 'off' }, { AudioContext: made })
    const b = createSoundBoard()
    w.fire('keydown')
    b.play('open')
    expect(made).not.toHaveBeenCalled()
  })
})
