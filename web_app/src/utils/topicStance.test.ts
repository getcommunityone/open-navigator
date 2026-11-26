import { describe, expect, it } from 'vitest'
import type { TopicStanceMap } from '../api/topics'
import { AI_LEGEND_LABEL, LEGEND_LABEL, stanceLine } from '../components/home/StoryStatesMap'
import { topicStanceForMap } from './topicStance'

// Test stand-ins shaped like GET /api/topics/{id}/state-map, not warehouse figures.
const row = (state_code: string, meetings: number, against: number, forr: number, mixed: number, disagree = 0) => ({
  state_code,
  state: null,
  meetings,
  lean_meetings: against + forr + mixed,
  public_against_meetings: against,
  public_for_meetings: forr,
  no_side_meetings: mixed,
  disagreement_meetings: disagree,
})

describe('topicStanceForMap (#1127)', () => {
  it('claims nothing while the request is loading or failed', () => {
    expect(topicStanceForMap(undefined)).toBeUndefined()
    expect(topicStanceForMap(null)).toBeUndefined()
  })

  it('is an empty split (grey map, "no AI reading yet") when the reading does not exist yet', () => {
    const map: TopicStanceMap = { topic_id: 100006, available: false, by_state: [row('TX', 12, 0, 0, 0)] }
    expect(topicStanceForMap(map)).toEqual([])
  })

  it('splits each read state by meetings: against, for, mixed; unread states stay out (grey)', () => {
    const map: TopicStanceMap = {
      topic_id: 100006,
      available: true,
      by_state: [row('TX', 12, 3, 1, 2, 1), row('WI', 5, 0, 0, 0)],
    }
    expect(topicStanceForMap(map)).toEqual([
      {
        state_code: 'TX',
        meetings: 12,
        speakers_against: 3,
        speakers_for: 1,
        speakers_neutral: 2,
        speakers_question: 0,
        disagreement_meetings: 1,
      },
    ])
  })
})

describe('stanceLine wording', () => {
  const s = { speakers_against: 3, speakers_for: 1, speakers_neutral: 2, speakers_question: 0 }

  it('says meetings and AI reading for a topic split, never speakers', () => {
    expect(stanceLine(s, 'meetings')).toBe('AI reading of 6 meetings: 3 leaned against · 1 leaned for · 2 mixed')
  })

  it('keeps the speaker wording for data centers', () => {
    expect(stanceLine(s)).toBe('3 spoke against · 1 spoke for · 2 no side')
  })

  it('has the four-entry legend in both wordings', () => {
    expect(Object.values(LEGEND_LABEL)).toEqual(['Spoke against', 'Spoke for', 'No side'])
    expect(Object.values(AI_LEGEND_LABEL)).toEqual(['Public leaned against', 'Public leaned for', 'Mixed'])
  })
})
