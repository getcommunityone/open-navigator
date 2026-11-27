import { describe, expect, it } from 'vitest'
import { swipeDirection } from './useSwipeNav'

describe('swipeDirection (#1222)', () => {
  it('swipe left = next, swipe right = previous', () => {
    expect(swipeDirection(-120, 10, 200)).toBe('next')
    expect(swipeDirection(120, -10, 200)).toBe('prev')
  })
  it('never takes a vertical scroll or a diagonal for a swipe', () => {
    expect(swipeDirection(-20, 300, 200)).toBeNull()
    expect(swipeDirection(-90, 80, 200)).toBeNull()
  })
  it('ignores short or slow drags', () => {
    expect(swipeDirection(-30, 0, 200)).toBeNull()
    expect(swipeDirection(-200, 0, 1500)).toBeNull()
  })
})
