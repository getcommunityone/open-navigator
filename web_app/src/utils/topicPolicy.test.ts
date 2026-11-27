import { describe, expect, it } from 'vitest'
import type { LegislationSummaryRow } from '../api/topicPolicy'
import {
  actionLabels,
  countByCategory,
  countByStatus,
  filterRows,
  pct,
  positionFill,
  positionStyle,
  shadeStates,
  topStatus,
  yearSpan,
} from './topicPolicy'

const row = (over: Partial<LegislationSummaryRow>): LegislationSummaryRow => ({
  state_code: 'KY',
  state: 'Kentucky',
  category: 'ban',
  year: '2026',
  status: 'pending',
  bills: 1,
  ...over,
})

const rows: LegislationSummaryRow[] = [
  row({ status: 'failed', year: '2025', category: 'restriction', bills: 3 }),
  row({ status: 'passed_chamber', year: '2026', category: 'unclear' }),
  row({ state_code: 'UT', state: 'Utah', status: 'enacted', year: '2025', category: 'unclear' }),
  row({ state_code: 'ME', state: 'Maine', status: 'failed', year: '2019' }),
  row({ state_code: 'GA', state: 'Georgia', status: 'pending', year: null }),
]

describe('topStatus', () => {
  it('picks the furthest status and null for none', () => {
    expect(topStatus([{ status: 'failed' }, { status: 'pending' }])).toBe('pending')
    expect(topStatus([{ status: 'passed_chamber' }, { status: 'enacted' }])).toBe('enacted')
    expect(topStatus([])).toBeNull()
  })
})

describe('filterRows / shadeStates', () => {
  it('filters by year and category and recolours each state from what is left', () => {
    expect(filterRows(rows, { sinceYear: 2026, category: null })).toHaveLength(1)
    const recent = shadeStates(rows, { sinceYear: 2025, category: null })
    expect(recent.map((s) => [s.state_code, s.status, s.bills])).toEqual([
      ['KY', 'passed_chamber', 4],
      ['UT', 'enacted', 1],
    ])
    const restriction = shadeStates(rows, { sinceYear: null, category: 'restriction' })
    expect(restriction.map((s) => [s.state_code, s.status])).toEqual([['KY', 'failed']])
    expect(countByStatus(recent)).toEqual({ enacted: 1, passed_chamber: 1, pending: 0, failed: 0 })
    // A bill with no year shows under every year, never under a period.
    expect(shadeStates(rows, { sinceYear: null, category: null }).map((s) => s.state_code)).toContain('GA')
  })

  it('counts bills per category within the period', () => {
    expect(Object.fromEntries(countByCategory(rows, 2025))).toEqual({ restriction: 3, unclear: 2 })
  })

  it('finds the year span, ignoring rows with no year', () => {
    expect(yearSpan(rows)).toEqual([2019, 2026])
    expect(yearSpan([row({ year: null })])).toBeNull()
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
