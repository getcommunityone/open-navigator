import { describe, expect, it } from 'vitest'
import { pickBoxQuote, pickZoneIndex, stanceFromPublicLean } from './mapQuote'

describe('pickZoneIndex (#1357)', () => {
  it('returns 0 when there is only one quote, one box, or rank 0', () => {
    expect(pickZoneIndex(0, 10, 3)).toBe(0)
    expect(pickZoneIndex(5, 10, 1)).toBe(0)
    expect(pickZoneIndex(0, 1, 3)).toBe(0)
    expect(pickZoneIndex(-2, 10, 3)).toBe(0)
  })

  it('partitions a state or band into contiguous zones across all quotes', () => {
    // 60 boxes across 2 quotes: 0..29 -> 0, 30..59 -> 1
    expect(pickZoneIndex(0, 60, 2)).toBe(0)
    expect(pickZoneIndex(29, 60, 2)).toBe(0)
    expect(pickZoneIndex(30, 60, 2)).toBe(1)
    expect(pickZoneIndex(59, 60, 2)).toBe(1)

    // 90 boxes across 3 quotes: thirds
    expect(pickZoneIndex(0, 90, 3)).toBe(0)
    expect(pickZoneIndex(29, 90, 3)).toBe(0)
    expect(pickZoneIndex(30, 90, 3)).toBe(1)
    expect(pickZoneIndex(59, 90, 3)).toBe(1)
    expect(pickZoneIndex(60, 90, 3)).toBe(2)
    expect(pickZoneIndex(89, 90, 3)).toBe(2)
  })

  it('gives distinct quotes to adjacent boxes in tiny states with fewer boxes than quotes', () => {
    expect(pickZoneIndex(0, 2, 3)).toBe(0)
    expect(pickZoneIndex(1, 2, 3)).toBe(1)
  })
})

describe('pickBoxQuote (#1357)', () => {
  const texasQuotes = [
    { id: 'against-1', side: 'against' as const, speakerName: 'James C.' },
    { id: 'for-1', side: 'for' as const, speakerName: 'Marshall B.' },
    { id: 'for-2', side: 'for' as const, speakerName: 'Kirk C.' },
    { id: 'meet-1', side: null, speakerName: null },
    { id: 'meet-2', side: null, speakerName: null },
    { id: 'meet-3', side: null, speakerName: null },
  ]

  it('returns undefined when a state has no quotes', () => {
    expect(pickBoxQuote({ side: 'against', rank: 0, stateCount: 10, bandRank: 0, bandCount: 10 }, [])).toBeUndefined()
  })

  it('matches the hovered stance band and switches across speakers in that band', () => {
    const red = pickBoxQuote({ side: 'against', rank: 5, stateCount: 180, bandRank: 5, bandCount: 30 }, texasQuotes)
    expect(red?.id).toBe('against-1')

    const tealLeft = pickBoxQuote({ side: 'for', rank: 35, stateCount: 180, bandRank: 5, bandCount: 60 }, texasQuotes)
    const tealRight = pickBoxQuote({ side: 'for', rank: 80, stateCount: 180, bandRank: 50, bandCount: 60 }, texasQuotes)
    expect(tealLeft?.id).toBe('for-1')
    expect(tealRight?.id).toBe('for-2')
  })

  it('walks through untagged meeting passages on the neutral band instead of locking onto an opposing speaker', () => {
    const purple1 = pickBoxQuote({ side: 'neutral', rank: 95, stateCount: 180, bandRank: 5, bandCount: 90 }, texasQuotes)
    const purple2 = pickBoxQuote({ side: 'neutral', rank: 135, stateCount: 180, bandRank: 45, bandCount: 90 }, texasQuotes)
    const purple3 = pickBoxQuote({ side: 'neutral', rank: 170, stateCount: 180, bandRank: 80, bandCount: 90 }, texasQuotes)
    expect(purple1?.id).toBe('meet-1')
    expect(purple2?.id).toBe('meet-2')
    expect(purple3?.id).toBe('meet-3')
  })

  it('includes question speakers in the neutral band with named speakers first', () => {
    const quotes = [
      { id: 'meet-1', side: null, speakerName: null },
      { id: 'q-1', side: 'question' as const, speakerName: 'Pat R.' },
    ]
    const left = pickBoxQuote({ side: 'neutral', rank: 0, stateCount: 20, bandRank: 0, bandCount: 20 }, quotes)
    const right = pickBoxQuote({ side: 'neutral', rank: 15, stateCount: 20, bandRank: 15, bandCount: 20 }, quotes)
    expect(left?.id).toBe('q-1')
    expect(right?.id).toBe('meet-1')
  })

  it('orders named speakers first on unsplit states without discarding unnamed meeting passages', () => {
    const quotes = [
      { id: 'meet-1', side: null, speakerName: null },
      { id: 'named-1', side: null, speakerName: 'Rob D.' },
      { id: 'meet-2', side: null, speakerName: null },
    ]
    const first = pickBoxQuote({ side: null, rank: 0, stateCount: 30, bandRank: 0, bandCount: 30 }, quotes)
    const mid = pickBoxQuote({ side: null, rank: 15, stateCount: 30, bandRank: 15, bandCount: 30 }, quotes)
    const last = pickBoxQuote({ side: null, rank: 25, stateCount: 30, bandRank: 25, bandCount: 30 }, quotes)
    expect(first?.id).toBe('named-1')
    expect(mid?.id).toBe('meet-1')
    expect(last?.id).toBe('meet-2')
  })
  it('matches topic meeting passages using band without setting a speaker side', () => {
    const topicQuotes = [
      { id: 'm-against', band: 'against' as const, speakerName: null },
      { id: 'm-for', band: 'for' as const, speakerName: null },
      { id: 'm-split', band: 'neutral' as const, speakerName: null },
    ]
    expect(pickBoxQuote({ side: 'against', rank: 0, stateCount: 30, bandRank: 0, bandCount: 10 }, topicQuotes)?.id).toBe('m-against')
    expect(pickBoxQuote({ side: 'for', rank: 12, stateCount: 30, bandRank: 2, bandCount: 10 }, topicQuotes)?.id).toBe('m-for')
    expect(pickBoxQuote({ side: 'neutral', rank: 25, stateCount: 30, bandRank: 5, bandCount: 10 }, topicQuotes)?.id).toBe('m-split')
  })
})

describe('stanceFromPublicLean', () => {
  it('maps topic public_stance strings to map band sides', () => {
    expect(stanceFromPublicLean('against')).toBe('against')
    expect(stanceFromPublicLean('for')).toBe('for')
    expect(stanceFromPublicLean('split')).toBe('neutral')
    expect(stanceFromPublicLean('silent')).toBeNull()
    expect(stanceFromPublicLean(null)).toBeNull()
  })
})
