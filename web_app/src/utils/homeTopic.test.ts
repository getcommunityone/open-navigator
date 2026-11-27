import { describe, expect, it } from 'vitest'
import { askedStory, tabKeyTarget, withStory } from './homeTopic'

describe('home topic param (#1350)', () => {
  it('reads topic, then the legacy story, else empty', () => {
    expect(askedStory(new URLSearchParams('topic=guns'))).toBe('guns')
    expect(askedStory(new URLSearchParams('story=pickleball'))).toBe('pickleball')
    expect(askedStory(new URLSearchParams('topic=guns&story=pickleball'))).toBe('guns')
    expect(askedStory(new URLSearchParams('state=AL'))).toBe('')
  })
  it('sets topic, keeps the place, drops the legacy story and the default', () => {
    expect(withStory(new URLSearchParams('state=AL&city=Tuscaloosa&story=x'), 'guns').toString()).toBe('state=AL&city=Tuscaloosa&topic=guns')
    expect(withStory(new URLSearchParams('state=AL&topic=guns'), 'data-centers').toString()).toBe('state=AL')
  })
  it('moves between tabs and wraps', () => {
    expect(tabKeyTarget('ArrowRight', 2, 3)).toBe(0)
    expect(tabKeyTarget('ArrowLeft', 0, 3)).toBe(2)
    expect(tabKeyTarget('Home', 2, 3)).toBe(0)
    expect(tabKeyTarget('End', 0, 3)).toBe(2)
    expect(tabKeyTarget('a', 0, 3)).toBeNull()
  })
})
