import { describe, expect, it } from 'vitest'
import { overviewLead } from './overviewLead'

describe('overviewLead (#1349)', () => {
  it('drops the subhead and lede that restate the "where it came up" headline', () => {
    expect(
      overviewLead(
        'Where water fluoridation came up at local meetings in Alabama, in the words said there.',
        'What local governments said about water fluoridation, in the words said at the meeting.',
      ),
    ).toEqual({ subhead: null, lede: null })
  })

  it('keeps a subhead with a finding and a lede with its own copy', () => {
    const subhead = 'How the public leaned on guns at local meetings in Alabama, read from each meeting\'s transcript.'
    const lede = 'Courts, noise and new venues, as councils and parks boards weigh them, in the words said at the meeting.'
    expect(overviewLead(subhead, lede)).toEqual({ subhead, lede })
  })

  it('treats missing lines as none', () => {
    expect(overviewLead(null, undefined)).toEqual({ subhead: null, lede: null })
  })
})
