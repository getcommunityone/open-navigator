import { describe, expect, it } from 'vitest'
import { cueWord } from './scrollCue'

describe('cueWord', () => {
  it('says Scroll for a fine pointer and Swipe up for touch', () => {
    expect(cueWord(false)).toBe('Scroll')
    expect(cueWord(true)).toBe('Swipe up')
  })
})
