import { describe, expect, it } from 'vitest'
import { captureFlipFirst } from './pillFlip'

describe('pillFlip', () => {
  it('returns an empty map with no root', () => {
    expect(captureFlipFirst(null, '[data-flip-key]').size).toBe(0)
  })
})
