import { describe, expect, it } from 'vitest'
import { swipeDirection } from './useSwipeNav'

describe('swipeDirection (#1224)', () => {
  it('a quick flick to the left goes on, to the right goes back', () => {
    expect(swipeDirection(-120, 10, 200)).toBe('next')
    expect(swipeDirection(120, -10, 200)).toBe('prev')
  })
  it('a short move, a mostly vertical one, or a slow drag is not a swipe', () => {
    expect(swipeDirection(-30, 0, 100)).toBeNull()
    expect(swipeDirection(-80, 70, 100)).toBeNull()
    expect(swipeDirection(-200, 0, 1500)).toBeNull()
  })
})
