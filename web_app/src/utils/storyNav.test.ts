import { describe, expect, it } from 'vitest'
import { LIVE_STORIES, currentDot, dotState, isLastScreen, nextLiveStory, nextStoryLink, storyProgress, storyTopicOptions } from './storyNav'

describe('LIVE_STORIES', () => {
  it('lists the Data Center Story then Short-term rentals, the two live stories', () => {
    expect(LIVE_STORIES.map((s) => s.id)).toEqual(['data-centers', 'short-term-rentals'])
    expect(LIVE_STORIES[0]!.title).toBe('Data centers')
  })
})

describe('nextLiveStory', () => {
  it('is the following live story', () => {
    expect(nextLiveStory('data-centers')).toEqual({ id: 'short-term-rentals', title: 'Short-term rentals' })
  })
  it('stops at the end of the list (no wrap) and for an unknown story', () => {
    expect(nextLiveStory('short-term-rentals')).toBeNull()
    expect(nextLiveStory('nope')).toBeNull()
  })
})

describe('nextStoryLink', () => {
  it('carries the scope query to the next story', () => {
    expect(nextStoryLink('data-centers', '?state=AL&city=Tuscaloosa')).toMatchObject({
      href: '/stories/short-term-rentals?state=AL&city=Tuscaloosa',
      label: 'Next story: Short-term rentals',
    })
  })
  it('falls back to every data story, still scoped', () => {
    expect(nextStoryLink('short-term-rentals', '?state=AL')).toEqual({ href: '/stories?state=AL', label: 'All data stories', next: null })
    expect(nextStoryLink('short-term-rentals', '')).toMatchObject({ href: '/stories' })
  })
})

describe('storyProgress', () => {
  it('counts the screen in view as reached', () => {
    expect(storyProgress(0, 4)).toBe(0.25)
    expect(storyProgress(1, 4)).toBe(0.5)
    expect(storyProgress(3, 4)).toBe(1)
  })
  it('clamps out-of-range screens and an empty story', () => {
    expect(storyProgress(9, 4)).toBe(1)
    expect(storyProgress(-2, 4)).toBe(0.25)
    expect(storyProgress(0, 0)).toBe(0)
  })
})

describe('dots', () => {
  it('marks the current dot, those behind and those ahead', () => {
    expect(currentDot(2, 5)).toBe(2)
    expect(currentDot(7, 5)).toBe(4)
    expect(currentDot(0, 0)).toBe(-1)
    expect([0, 1, 2].map((i) => dotState(i, 1, 3))).toEqual(['past', 'now', 'ahead'])
  })
  it('knows the last screen', () => {
    expect(isLastScreen(4, 5)).toBe(true)
    expect(isLastScreen(3, 5)).toBe(false)
    expect(isLastScreen(0, 0)).toBe(false)
  })
})

describe('storyTopicOptions (#1224)', () => {
  const live = [
    { id: 'data-centers', title: 'Data centers' },
    { id: 'guns', title: 'Gun control' },
    { id: 'pickleball', title: 'Pickleball' },
  ]
  it('lists every live story, the current one as the title says it', () => {
    expect(storyTopicOptions(live, 'guns', 'gun control')).toEqual([
      { value: 'data-centers', label: 'Data centers' },
      { value: 'guns', label: 'gun control' },
      { value: 'pickleball', label: 'Pickleball' },
    ])
  })
  it('keeps the current story while the live list is still loading', () => {
    expect(storyTopicOptions([], 'data-centers', 'data centers')).toEqual([{ value: 'data-centers', label: 'data centers' }])
  })
})
