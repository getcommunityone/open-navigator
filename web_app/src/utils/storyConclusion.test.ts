import { describe, expect, it } from 'vitest'
import { STORIES, storyConclusion } from './dataStory'

// Test-only counts: nothing here is served by the app.
const story = STORIES['data-centers']!
const c = (against: number, forN: number, question = 1, neutral = 7) => ({ for: forN, against, question, neutral })

describe('storyConclusion (#989)', () => {
  it('shows the headline with its basis while speakers against outnumber those for by 2:1', () => {
    const r = storyConclusion(story, c(18, 3))!
    expect(r.headline).toBe('America hates data centers.')
    expect(r.basis).toBe('Of 29 speakers on record at local meetings, 18 spoke against and 3 spoke for.')
  })
  it('holds back the headline when the record does not back it', () => {
    expect(storyConclusion(story, c(10, 6))).toBeNull() // under 2:1
    expect(storyConclusion(story, c(3, 0, 0, 2))).toBeNull() // fewer than 10 speakers
    expect(storyConclusion(story, c(0, 0, 0, 20))).toBeNull() // nobody against
    expect(storyConclusion(story, null)).toBeNull()
  })
  it('needs a conclusion on the story', () => {
    expect(storyConclusion({ ...story, conclusion: undefined }, c(18, 3))).toBeNull()
  })
})
