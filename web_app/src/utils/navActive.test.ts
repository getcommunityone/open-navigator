import { describe, expect, it } from 'vitest'
import { activeNavKey } from './navActive'

describe('activeNavKey', () => {
  it('lights the home section in view, and nothing between sections', () => {
    expect(activeNavKey('/', 'data-stories')).toBe('stories')
    expect(activeNavKey('/', 'search')).toBe('search')
    expect(activeNavKey('/', 'how-it-works')).toBe('how')
    expect(activeNavKey('/', 'impact')).toBeNull()
    expect(activeNavKey('/', '')).toBeNull()
  })
  it('lights Data Stories on the hub and every story', () => {
    expect(activeNavKey('/stories')).toBe('stories')
    expect(activeNavKey('/stories/')).toBe('stories')
    expect(activeNavKey('/stories/data-centers')).toBe('stories')
    expect(activeNavKey('/challenge/data-centers')).toBe('stories')
    expect(activeNavKey('/stories-old')).toBeNull()
  })
  it('lights Places on the places list and jurisdiction pages', () => {
    expect(activeNavKey('/jurisdictions')).toBe('places')
    expect(activeNavKey('/jurisdiction/0177256/meetings')).toBe('places')
    expect(activeNavKey('/jurisdiction-quality')).toBeNull()
  })
  it('lights Search on /search only, and ignores the home section off home', () => {
    expect(activeNavKey('/search')).toBe('search')
    expect(activeNavKey('/search', 'how-it-works')).toBe('search')
    expect(activeNavKey('/chat', 'search')).toBeNull()
  })
})
