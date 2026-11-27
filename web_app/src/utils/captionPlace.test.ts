import { describe, expect, it } from 'vitest'
import type { StoryScope } from './dataStory'
import { splitCaptionAtPlace } from './captionPlace'
import { captionText, pickCaption, type Caption } from './storyCaption'

// Test stand-ins: caption shapes, not warehouse figures.
const P = { blank: 'place' } as const
const T = { blank: 'topic' } as const
const nat: StoryScope = { stateName: null, city: null }
const al: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: null }
const tus: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: 'Tuscaloosa' }

const cap = (over: Partial<Caption>): Caption => ({ kind: 'volume', template: [], place: '', basis: null, ai: false, ...over })
const joined = (s: { before: string; place: string; after: string }) => `${s.before}${s.place}${s.after}`

describe('splitCaptionAtPlace', () => {
  it('national "America hates": the control leads the title', () => {
    const c = cap({ kind: 'sentiment', template: [P, ' hates ', T, '.'], place: 'America' })
    const s = splitCaptionAtPlace(c, 'data centers', nat)
    expect(s).toEqual({ before: '', place: 'America', after: ' hates data centers.' })
    expect(joined(s)).toBe(captionText(c, 'data centers'))
  })

  it('wider-scope title: the control is the place the reader chose, the second place', () => {
    const c = cap({
      kind: 'wider_sentiment',
      template: ['America hates ', T, '; ', P, ' brought them up in 2 meetings.'],
      place: 'Tuscaloosa, Alabama',
      widerPlace: 'America',
    })
    const s = splitCaptionAtPlace(c, 'data centers', tus)
    expect(s).toEqual({ before: 'America hates data centers; ', place: 'Tuscaloosa, Alabama', after: ' brought them up in 2 meetings.' })
    expect(joined(s)).toBe(captionText(c, 'data centers'))
  })

  it('state scope: splits a place blank mid-sentence', () => {
    const c = cap({ kind: 'sentiment', template: ['In 12 meetings in ', P, ', the public mostly opposed ', T, '.'], place: 'Alabama' })
    expect(splitCaptionAtPlace(c, 'short-term rentals', al)).toEqual({
      before: 'In 12 meetings in ',
      place: 'Alabama',
      after: ', the public mostly opposed short-term rentals.',
    })
  })

  it('national question: "the United States" is the control', () => {
    const c = pickCaption('data-centers', null, nat)
    const s = splitCaptionAtPlace(c, 'data centers', nat)
    expect(s.place).toBe('the United States')
    expect(joined(s)).toBe(captionText(c, 'data centers'))
  })

  it('national title naming a leading state: "In the United States, …" leads, the claim unchanged', () => {
    const c = cap({ kind: 'state_gap', template: [P, ' took up ', T, ' in 570 meetings, more than any other state.'], place: 'California' })
    expect(splitCaptionAtPlace(c, 'short-term rentals', nat)).toEqual({
      before: 'In ',
      place: 'the United States',
      after: ', California took up short-term rentals in 570 meetings, more than any other state.',
    })
  })

  it('national title with no place blank: lower-cases its "In" after the lead', () => {
    const c = cap({ kind: 'sentiment', template: ['In 81 meetings, the public mostly opposed ', T, '.'], place: 'America' })
    expect(joined(splitCaptionAtPlace(c, 'short-term rentals', nat))).toBe(
      'In the United States, in 81 meetings, the public mostly opposed short-term rentals.',
    )
  })

  it('never names a place other than the scope as the control', () => {
    const c = cap({ kind: 'state_gap', template: [P, ' and more.'], place: 'Georgia' })
    expect(splitCaptionAtPlace(c, 'x', al).place).toBe('Alabama')
  })
})
