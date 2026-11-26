import { describe, expect, it } from 'vitest'
import { STORIES, storyTitle, storyTitleText } from './dataStory'

// Test-only counts: nothing here is served by the app.
const story = STORIES['data-centers']!
const speakers = (against: number, forN: number) => ({ for: forN, against, question: 1, neutral: 7 })
const national = { stateName: null, city: null }
const wa = { stateCode: 'WA', stateName: 'Washington', city: null }

describe('storyTitle (#993)', () => {
  it('states the sentiment, as America nationally, when the speakers back it', () => {
    const t = storyTitle(story, national, { speakers: speakers(18, 3), meetings: 1859 })
    expect(t.kind).toBe('sentiment')
    expect(t.template).toEqual([{ blank: 'place' }, ' hates ', { blank: 'topic' }, '.'])
    expect(t.place).toBe('America')
    expect(t.basis).toBe('29 speakers counted by hand: 18 against, 3 for.')
  })

  it('names the place in the sentiment and its basis', () => {
    const t = storyTitle(story, wa, { speakers: speakers(20, 4), meetings: 69 })
    expect(t.place).toBe('Washington')
    expect(t.basis).toBe('32 speakers counted by hand in Washington: 20 against, 4 for.')
  })

  it('falls back to the fact when the place has no speakers to back a sentiment', () => {
    const t = storyTitle(story, wa, { speakers: { for: 0, against: 0, question: 0, neutral: 0 }, meetings: 69 })
    expect(t.kind).toBe('fact')
    expect(t.template).toEqual([{ blank: 'place' }, ' talked about ', { blank: 'topic' }, ' in 69 meetings.'])
    expect(t.place).toBe('Washington')
  })

  it('keeps the question when there is nothing on record', () => {
    const t = storyTitle(story, wa, { speakers: null, meetings: 0 })
    expect(t.kind).toBe('question')
    expect(t.place).toBe('Washington')
    expect(t.basis).toBeNull()
    expect(storyTitle(story, national, { speakers: null, meetings: null }).place).toBe('the United States')
  })

  // #1134: a state scope uses the state's own record, never the national headline.
  const az = { stateCode: 'AZ', stateName: 'Arizona', city: null }
  it('a state with a meeting reading leads with it', () => {
    const t = storyTitle(story, az, { speakers: { for: 0, against: 11, question: 1, neutral: 0 }, meetings: 25, lean: { against: 14 } })
    expect(t.kind).toBe('sentiment')
    expect(storyTitleText(story, t)).toBe('Arizona hates data centers.')
    expect(t.basis).toBe(
      'The public leaned against data centers in 14 meetings in Arizona (AI reading of meetings). 12 speakers counted by hand in Arizona: 11 against, 0 for.',
    )
  })
  it('a state without a meeting reading falls to its meetings, then the question', () => {
    const t = storyTitle(story, az, { speakers: null, meetings: 25, lean: null })
    expect(storyTitleText(story, t)).toBe('Arizona talked about data centers in 25 meetings.')
    const thin = storyTitle(story, az, { speakers: null, meetings: 25, lean: { against: 3 } })
    expect(thin.kind).toBe('fact')
    const q = storyTitle(story, az, { speakers: null, meetings: 0, lean: null })
    expect(storyTitleText(story, q)).toBe('What did local meetings in Arizona say about data centers?')
  })
  it('nationally with the reading missing, falls back to the speakers', () => {
    const t = storyTitle(story, national, { speakers: { ...speakers(18, 3), states: 4 }, meetings: 1859, lean: null })
    expect(storyTitleText(story, t)).toBe('America hates data centers.')
    expect(t.basis).toBe('29 speakers counted by hand in 4 states: 18 against, 3 for.')
  })
})
