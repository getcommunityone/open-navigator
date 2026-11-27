import { describe, expect, it } from 'vitest'
import type { LegislationBill, LegislationState } from '../api/topicPolicy'
import {
  actionLabels,
  countByStatus,
  filterBills,
  pct,
  positionFill,
  positionStyle,
  shadeStates,
  sortBills,
  topStatus,
  yearSpan,
} from './topicPolicy'

const bill = (over: Partial<LegislationBill>): LegislationBill => ({
  bill_id: 'b',
  identifier: 'HB 1',
  title: 't',
  session: '2026',
  year: '2026',
  category: 'ban',
  status: 'pending',
  passed_a_chamber: false,
  url: null,
  introduced_date: null,
  last_action_date: '2026-01-01',
  last_action: null,
  ...over,
})

const states: LegislationState[] = [
  {
    state_code: 'KY',
    state: 'Kentucky',
    top_status: 'passed_chamber',
    status_counts: {},
    bills: [
      bill({ bill_id: 'k1', status: 'failed', year: '2025', category: 'restriction' }),
      bill({ bill_id: 'k2', status: 'passed_chamber', year: '2026', category: 'unclear' }),
    ],
  },
  { state_code: 'UT', state: 'Utah', top_status: 'enacted', status_counts: {}, bills: [bill({ bill_id: 'u1', status: 'enacted', year: '2025', category: 'unclear' })] },
  { state_code: 'ME', state: 'Maine', top_status: 'failed', status_counts: {}, bills: [bill({ bill_id: 'm1', status: 'failed', year: '2019' })] },
]

describe('topStatus', () => {
  it('picks the furthest status and null for none', () => {
    expect(topStatus([{ status: 'failed' }, { status: 'pending' }])).toBe('pending')
    expect(topStatus([{ status: 'passed_chamber' }, { status: 'enacted' }])).toBe('enacted')
    expect(topStatus([])).toBeNull()
  })
})

describe('filterBills / shadeStates', () => {
  it('filters by year and category and recolours each state from what is left', () => {
    expect(filterBills(states[0]!.bills, { sinceYear: 2026, category: null }).map((b) => b.bill_id)).toEqual(['k2'])
    const recent = shadeStates(states, { sinceYear: 2025, category: null })
    expect(recent.map((s) => [s.state_code, s.status])).toEqual([
      ['KY', 'passed_chamber'],
      ['UT', 'enacted'],
    ])
    const restriction = shadeStates(states, { sinceYear: null, category: 'restriction' })
    expect(restriction.map((s) => [s.state_code, s.status])).toEqual([['KY', 'failed']])
    expect(countByStatus(recent)).toEqual({ enacted: 1, passed_chamber: 1, pending: 0, failed: 0 })
  })

  it('sorts a state’s bills furthest first, then newest', () => {
    const out = sortBills([
      bill({ bill_id: 'a', status: 'failed', last_action_date: '2026-05-01' }),
      bill({ bill_id: 'b', status: 'pending', last_action_date: '2025-01-01' }),
      bill({ bill_id: 'c', status: 'pending', last_action_date: '2026-02-01' }),
    ])
    expect(out.map((b) => b.bill_id)).toEqual(['c', 'b', 'a'])
  })

  it('finds the year span, ignoring bills with no year', () => {
    expect(yearSpan(states)).toEqual([2019, 2026])
    expect(yearSpan([{ ...states[0]!, bills: [bill({ year: null })] }])).toBeNull()
  })
})

describe('positions', () => {
  it('names the five positions plainly and colours sides', () => {
    expect(positionStyle('support_require_all')).toEqual({ label: 'Support, require everywhere', side: 'support', strong: true })
    expect(positionStyle('oppose_ban_all').label).toBe('Oppose, ban everywhere')
    expect(positionStyle('mostly_opposed').side).toBe('oppose')
    expect(positionFill(positionStyle('no_opinion'))).toBe('var(--neutral-data)')
    expect(positionFill(positionStyle('support_local_choice'))).toContain('color-mix')
  })

  it('never makes up a share when the total is 0', () => {
    expect(pct(3, 0)).toBeNull()
    expect(pct(22, 112)).toBe(20)
  })
})

describe('actionLabels', () => {
  it('uses topic words where defined, else generic ones', () => {
    expect(actionLabels('water-fluoridation').blocked).toBe('Voted to end fluoridation')
    expect(actionLabels('pickleball').advanced).toBe('Voted to move it forward')
  })
})
