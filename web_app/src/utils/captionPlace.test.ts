import { describe, expect, it } from 'vitest'
import type { StoryScope } from './dataStory'
import { scopePlaceName, splitCaptionAtPlace, splitTextAtPlace } from './captionPlace'
import { captionSubhead, captionText, pickCaption, type Caption } from './storyCaption'

// Test stand-ins: caption shapes, not warehouse figures.
const P = { blank: 'place' } as const
const T = { blank: 'topic' } as const
const nat: StoryScope = { stateName: null, city: null }
const al: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: null }
const tus: StoryScope = { stateCode: 'AL', stateName: 'Alabama', city: 'Tuscaloosa' }

const cap = (over: Partial<Caption>): Caption => ({ kind: 'volume', template: [], place: '', basis: null, ai: false, ...over })
const joined = (s: { before: string; place: string; after: string } | null) => (s ? `${s.before}${s.place}${s.after}` : null)

describe('splitCaptionAtPlace', () => {
  it('national "America hates": the control leads the title', () => {
    const c = cap({ kind: 'position', template: [P, ' hates ', T, '.'], place: 'America' })
    const s = splitCaptionAtPlace(c, 'data centers', nat)
    expect(s).toEqual({ before: '', place: 'America', after: ' hates data centers.' })
    expect(joined(s)).toBe(captionText(c, 'data centers'))
  })

  it('a place\'s own conclusion: the control is the place word', () => {
    const c = cap({ kind: 'position', template: [P, ' mostly wants limits on short-term rentals.'], place: 'Alabama' })
    expect(splitCaptionAtPlace(c, 'short-term rentals', al)).toEqual({ before: '', place: 'Alabama', after: ' mostly wants limits on short-term rentals.' })
  })

  it('a broader scope\'s title (#1222): no split, so the control moves to the line under it', () => {
    const c = cap({ kind: 'wider_position', template: ['America', ' hates ', T, '.'], place: 'Tuscaloosa, Alabama', widerPlace: 'America' })
    expect(splitCaptionAtPlace(c, 'data centers', tus)).toBeNull()
    // The subhead starts with the place in scope, where the control goes.
    const s = splitTextAtPlace(captionSubhead(c, 'data-centers', tus), scopePlaceName(tus))
    expect(s?.before).toBe('')
    expect(s?.place).toBe('Tuscaloosa, Alabama')
  })

  it('national question: "the United States" is the control', () => {
    const c = pickCaption('data-centers', null, nat)
    const s = splitCaptionAtPlace(c, 'data centers', nat)
    expect(s?.place).toBe('the United States')
    expect(joined(s)).toBe(captionText(c, 'data centers'))
  })

  it('a national title naming a leading state adds no "In the United States" lead: no split', () => {
    const c = cap({ kind: 'state_gap', template: [P, ' took up ', T, ' in 570 meetings, more than any other state.'], place: 'California' })
    expect(splitCaptionAtPlace(c, 'short-term rentals', nat)).toBeNull()
    expect(scopePlaceName(nat)).toBe('the United States')
  })

  it('never names a place other than the scope as the control', () => {
    const c = cap({ kind: 'state_gap', template: [P, ' and more.'], place: 'Georgia' })
    expect(splitCaptionAtPlace(c, 'x', al)).toBeNull()
  })
})

describe('splitTextAtPlace', () => {
  it('splits at the first mention, or null', () => {
    expect(splitTextAtPlace('Where Alabama talked.', 'Alabama')).toEqual({ before: 'Where ', place: 'Alabama', after: ' talked.' })
    expect(splitTextAtPlace('Nothing here.', 'Alabama')).toBeNull()
    expect(splitTextAtPlace(null, 'Alabama')).toBeNull()
  })
})
