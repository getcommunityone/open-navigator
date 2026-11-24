import { describe, expect, it } from 'vitest'
import { NUDGE_ENTRANCE_MS, NUDGE_IDLE_MS, NUDGE_MAX, NUDGE_REPEAT_MS, arrivalTime, isBlocked, shouldNudge, type NudgeState } from './idleNudge'

const at = (s: Partial<NudgeState>): NudgeState => ({ now: 0, lastInteraction: 0, lastNudge: null, shown: 0, ...s })

describe('shouldNudge', () => {
  it('waits for about six seconds of stillness', () => {
    expect(NUDGE_IDLE_MS).toBe(6000)
    expect(shouldNudge(at({ now: NUDGE_IDLE_MS - 1 }))).toBe(false)
    expect(shouldNudge(at({ now: NUDGE_IDLE_MS }))).toBe(true)
  })
  it('repeats about every eight seconds, at most three times, then rests', () => {
    expect([NUDGE_REPEAT_MS, NUDGE_MAX]).toEqual([8000, 3])
    const first = NUDGE_IDLE_MS
    expect(shouldNudge(at({ now: first + NUDGE_REPEAT_MS - 1, lastNudge: first, shown: 1 }))).toBe(false)
    expect(shouldNudge(at({ now: first + NUDGE_REPEAT_MS, lastNudge: first, shown: 1 }))).toBe(true)
    expect(shouldNudge(at({ now: first + 2 * NUDGE_REPEAT_MS, lastNudge: first + NUDGE_REPEAT_MS, shown: 2 }))).toBe(true)
    expect(shouldNudge(at({ now: first + 100 * NUDGE_REPEAT_MS, lastNudge: first + 2 * NUDGE_REPEAT_MS, shown: NUDGE_MAX }))).toBe(false)
  })
  it('starts over after any interaction', () => {
    const t = 60_000
    // the reader tapped at t: the count is back to zero and the idle clock runs from t
    expect(shouldNudge(at({ now: t + NUDGE_IDLE_MS - 1, lastInteraction: t }))).toBe(false)
    expect(shouldNudge(at({ now: t + NUDGE_IDLE_MS, lastInteraction: t }))).toBe(true)
  })
  it('never fires while something is in the way', () => {
    const idle = { now: 10 * NUDGE_IDLE_MS }
    for (const key of ['dialog', 'table', 'typing', 'selecting', 'hidden', 'noNext'] as const) {
      expect(shouldNudge(at({ ...idle, blocked: { [key]: true } }))).toBe(false)
    }
    expect(shouldNudge(at({ ...idle, blocked: {} }))).toBe(true)
    expect(isBlocked(undefined)).toBe(false)
    expect(isBlocked({ dialog: false, typing: true })).toBe(true)
  })
  it('lets a screen finish arriving before the idle clock starts', () => {
    const start = arrivalTime(1000)
    expect(start).toBe(1000 + NUDGE_ENTRANCE_MS)
    expect(shouldNudge(at({ now: 1000 + NUDGE_IDLE_MS, lastInteraction: start }))).toBe(false)
    expect(shouldNudge(at({ now: start + NUDGE_IDLE_MS, lastInteraction: start }))).toBe(true)
    expect(arrivalTime(1000, 0)).toBe(1000)
    expect(arrivalTime(1000, -5)).toBe(1000)
  })
})
