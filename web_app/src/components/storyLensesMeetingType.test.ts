import { describe, expect, it } from 'vitest'
import { toRenderCards, type ApiCard } from './StoryLenses'

const card = (extra: Partial<ApiCard>): ApiCard => ({
  headline: 'Council approves budget',
  stats: [],
  jurisdiction: 'Tuscaloosa',
  date: '2026-01-02',
  url: '/decisions/abc',
  state_code: 'AL',
  ...extra,
})

describe('meeting type on the decision card (#797)', () => {
  it('carries a known meeting type through to the card', () => {
    const [c] = toRenderCards([card({ meeting_type: 'City Council' })], false)
    expect(c.meetingType).toBe('City Council')
  })

  it('leaves it out when the API has none (null or absent), never guessing', () => {
    const [a, b] = toRenderCards([card({ meeting_type: null }), card({})], false)
    expect(a.meetingType).toBeUndefined()
    expect(b.meetingType).toBeUndefined()
  })
})
