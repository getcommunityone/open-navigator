import { describe, expect, it } from 'vitest'
import { STORIES, storyConclusion } from './dataStory'

// Test-only counts: nothing here is served by the app.
const story = STORIES['data-centers']!
const c = (against: number, forN: number, question = 1, neutral = 7) => ({ for: forN, against, question, neutral })

describe('storyConclusion (#989)', () => {
  it('shows the headline with its basis while speakers against outnumber those for by 2:1', () => {
    const r = storyConclusion(story, c(18, 3))!
    expect(r.headline).toBe('America hates data centers.')
    expect(r.basis).toBe('29 speakers counted by hand: 18 against and 3 for.')
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

  // #1134: the meeting reading leads; the hand count only appears with its scope.
  it('nationally leads with the meeting reading and scopes the hand count', () => {
    const r = storyConclusion(story, { ...c(18, 3), states: 4 }, undefined, { against: 283, states: 32 })!
    expect(r.headline).toBe('America hates data centers.')
    expect(r.basis).toBe(
      'The public mostly opposed data centers in 283 meetings across 32 states. 29 speakers counted by hand in 4 states: 18 against and 3 for.',
    )
  })
  it('passes on the meeting reading alone when the speakers do not back it', () => {
    const r = storyConclusion(story, c(2, 3), undefined, { against: 60, states: 9 })!
    expect(r.basis).toBe(
      'The public mostly opposed data centers in 60 meetings across 9 states. 13 speakers counted by hand: 3 for and 2 against.',
    )
    expect(storyConclusion(story, null, undefined, { against: 50, states: 1 })!.basis).toBe(
      'The public mostly opposed data centers in 50 meetings across 1 state.',
    )
  })
  it('gates the meeting reading on confident-against meetings only', () => {
    expect(storyConclusion(story, null, undefined, { against: 49, states: 20 })).toBeNull()
    expect(storyConclusion(story, c(10, 6), undefined, { against: 49 })).toBeNull()
    // Below the reading's gate, the speaker gate still carries it and the reading isn't stated.
    expect(storyConclusion(story, c(18, 3), undefined, { against: 12, states: 3 })!.basis).toBe('29 speakers counted by hand: 18 against and 3 for.')
  })
  it('uses the place gate and names the place', () => {
    const r = storyConclusion(story, null, 'in Arizona', { against: 14 })!
    expect(r.basis).toBe('The public mostly opposed data centers in 14 meetings in Arizona.')
    expect(storyConclusion(story, null, 'in Arizona', { against: 9 })).toBeNull()
  })
})
