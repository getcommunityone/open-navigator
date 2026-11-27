import { describe, expect, it } from 'vitest'
import { BOX_COLORS, PUBLIC_AGAINST_COLOR, hasDisagreement, leanFill, leanLine, tint } from './storyColors'

describe('tint', () => {
  it('mixes toward white', () => {
    expect(tint('#000000', 0.5)).toBe('#808080')
    expect(tint('#B4443F', 0)).toBe('#B4443F')
    expect(tint('#B4443F', 1)).toBe('#FFFFFF')
  })
  it('leaves a non-hex colour alone', () => {
    expect(tint('red', 0.5)).toBe('red')
  })
})

describe('public-against colour', () => {
  it('is a lighter tint, distinct from Spoke against and the meeting grey', () => {
    expect(PUBLIC_AGAINST_COLOR).not.toBe(BOX_COLORS.against)
    expect(PUBLIC_AGAINST_COLOR).not.toBe(BOX_COLORS.meetings)
  })
})

describe('leanLine', () => {
  it('is null when nothing is on record', () => {
    expect(leanLine(undefined)).toBeNull()
    expect(leanLine({ public_against_meetings: 0, disagreement_meetings: 0 })).toBeNull()
  })
  it('names each count only when above 0', () => {
    expect(leanLine({ public_against_meetings: 3, disagreement_meetings: 0 })).toBe(
      'AI reading: the public mostly opposed in 3 meetings.',
    )
    expect(leanLine({ public_against_meetings: 1, disagreement_meetings: 1 })).toBe(
      'AI reading: the public mostly opposed in 1 meeting; officials sided against the public in 1 meeting.',
    )
    expect(leanLine({ public_against_meetings: 0, disagreement_meetings: 2 })).toBe(
      'AI reading: officials sided against the public in 2 meetings.',
    )
  })
})

describe('leanFill / hasDisagreement', () => {
  it('tints only with a public-against meeting', () => {
    expect(leanFill({ public_against_meetings: 2 }, '#ccc')).toBe(PUBLIC_AGAINST_COLOR)
    expect(leanFill({ public_against_meetings: 0, disagreement_meetings: 1 }, '#ccc')).toBe('#ccc')
    expect(leanFill(null, '#ccc')).toBe('#ccc')
  })
  it('outlines only with a disagreement meeting', () => {
    expect(hasDisagreement({ disagreement_meetings: 1 })).toBe(true)
    expect(hasDisagreement({ disagreement_meetings: 0 })).toBe(false)
    expect(hasDisagreement(undefined)).toBe(false)
  })
})
