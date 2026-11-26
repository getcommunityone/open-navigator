import { describe, expect, it } from 'vitest'
import { STORIES, storyTitle } from './dataStory'

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
    expect(t.basis).toBe('Of 29 speakers on record at local meetings, 18 spoke against and 3 spoke for.')
  })

  it('names the place in the sentiment and its basis', () => {
    const t = storyTitle(story, wa, { speakers: speakers(20, 4), meetings: 69 })
    expect(t.place).toBe('Washington')
    expect(t.basis).toContain('at local meetings in Washington,')
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
})
