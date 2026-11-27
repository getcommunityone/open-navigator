import { describe, expect, it } from 'vitest'
import type { TopicOutcomesResponse } from '../api/topicOutcomes'
import { chainSteps, outcomesHeadline, partsSentence, stepScreen } from './topicOutcomes'

const step = (count: number) => ({ available: true, count, examples: [] })
const resp = (over: Partial<TopicOutcomesResponse['steps']> = {}): TopicOutcomesResponse => ({
  topic: 'water-fluoridation', state_code: 'GA', state: 'Georgia', city: null,
  steps: {
    meetings: step(0),
    public: { ...step(0), read: 0, silent: 0, by_lean: {} },
    actions: { ...step(0), by_outcome: {} },
    bills: { ...step(0), by_status: {} },
    linked_bills: { ...step(0), bills: 0, by_method: {} },
    next: { ...step(0), upcoming: 0, pending_bills: 0 },
    ...over,
  },
})
const words = { advanced: 'Voted to keep or start', blocked: 'Voted to end' }

describe('the chain from meeting to outcome (#1314)', () => {
  it('states parts in words, skipping zeros', () => {
    expect(partsSentence([['opposed', 12], ['mixed', 0], ['supportive', 1]])).toBe('12 opposed and 1 supportive')
    expect(partsSentence([['a', 1], ['b', 2], ['c', 3]])).toBe('1 a, 2 b and 3 c')
    expect(partsSentence([['a', 0]])).toBe('')
  })

  it('says "No recorded … yet" for every empty step, never a stand-in', () => {
    const lines = chainSteps(resp(), 'water fluoridation', words).map((s) => [s.id, s.count, s.line])
    expect(lines).toEqual([
      ['meetings', 0, 'No recorded meetings on water fluoridation yet.'],
      ['public', 0, 'No recorded public comment on it yet.'],
      ['actions', 0, 'No recorded votes or delays yet.'],
      ['bills', 0, 'No recorded state bills yet.'],
      ['linked_bills', 0, 'No recorded meeting named a state bill yet.'],
      ['next', 0, 'No upcoming meetings on record, and no open state bill.'],
    ])
    expect(outcomesHeadline(resp(), 'water fluoridation', 'Georgia')).toBe('In Georgia, no recorded meetings on water fluoridation yet.')
  })

  it('counts each step in the topic’s own words', () => {
    const d = resp({
      meetings: step(466),
      public: { ...step(105), read: 300, silent: 195, by_lean: { opposed: 83, supportive: 22 } },
      actions: { ...step(88), by_outcome: { advanced: 61, blocked: 4, tabled: 23 } },
      bills: { ...step(3), by_status: { pending: 1, failed: 2 } },
      linked_bills: { ...step(2), bills: 3, by_method: { transcript: 3 } },
      next: { ...step(2), upcoming: 1, pending_bills: 1 },
    })
    const by = Object.fromEntries(chainSteps(d, 'water fluoridation', words).map((s) => [s.id, s.line]))
    expect(by.public).toBe('Meetings where the public spoke: 83 mostly opposed and 22 mostly supportive.')
    expect(by.actions).toBe('Meetings where the body acted: 61 voted to keep or start, 4 voted to end and 23 tabled or put off.')
    expect(by.bills).toBe('1 pending and 2 failed.')
    expect(by.linked_bills).toBe('Meetings that named 3 state bills by number.')
    expect(by.next).toBe('1 meeting or hearing ahead and 1 state bill still open.')
    expect(outcomesHeadline(d, 'water fluoridation', 'National')).toBe(
      'Across America, water fluoridation came up in 466 meetings; local bodies voted or put it off in 88 and 2 named a state bill.',
    )
  })

  it('opens each step on its own screen', () => {
    expect(stepScreen('actions', false)).toBe('actions')
    expect(stepScreen('actions', true)).toBe('decisions')
    expect(stepScreen('next', false)).toBe('upcoming')
    expect(stepScreen('linked_bills', false)).toBeNull()
  })
})
