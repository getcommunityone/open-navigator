import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'
import { DrillValue, KpiDrillSheet, drillSummary, figureDrill, isDrillable } from './KpiDrill'
import { drillKey, rowTotal, type DrillKind, type DrillPage } from '../../api/storyDrill'

// Test-only rows: nothing here is served by the app.
const noop = () => {}

function sheet(drill: DrillKind, pages: DrillPage[], scope = { stateCode: 'ZZ', city: null }) {
  const qc = new QueryClient()
  qc.setQueryData(drillKey(drill, scope), { pages, pageParams: pages.map((_, i) => i * 25) })
  return renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <KpiDrillSheet id="s" drill={drill} title="Spoke against" scope={scope} scopeLabel="Testland" onClose={noop} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('KPI drill-down (#1288)', () => {
  it('only a count above 0 is tappable', () => {
    expect(isDrillable(3)).toBe(true)
    expect(isDrillable(0)).toBe(false)
    expect(isDrillable(null)).toBe(false)
    expect(isDrillable(undefined)).toBe(false)
    const plain = renderToStaticMarkup(
      <DrillValue drillable={false} label="spoke for" open={false} controls="x" onToggle={noop}>
        0
      </DrillValue>,
    )
    expect(plain).toBe('0')
    const btn = renderToStaticMarkup(
      <DrillValue label="spoke for" open={false} controls="x" onToggle={noop}>
        8
      </DrillValue>,
    )
    expect(btn).toContain('<button')
    expect(btn).toContain('aria-expanded="false"')
    expect(btn).toContain('>8<')
  })

  it('maps every figure to its own list', () => {
    expect(figureDrill('against')).toEqual({ kind: 'speakers', side: 'against' })
    expect(figureDrill('question')).toEqual({ kind: 'speakers', side: 'question' })
    expect(figureDrill('votes_for')).toEqual({ kind: 'votes', side: 'for' })
    expect(figureDrill('votes_against')).toEqual({ kind: 'votes', side: 'against' })
  })

  it('a vote tile counts votes; its list counts decisions', () => {
    const page: DrillPage = { kind: 'votes', total: 8, totalDecisions: 1, items: [], available: true }
    expect(rowTotal(page)).toBe(1)
    expect(drillSummary({ kind: 'votes', side: 'for' }, page, 'Testland')).toBe('8 votes for in 1 decision · Testland')
  })

  it('lists every speaker with the quote marked, "First L." and the moment link', () => {
    const drill: DrillKind = { kind: 'speakers', side: 'against' }
    const html = sheet(drill, [
      {
        kind: 'speakers',
        total: 2,
        available: true,
        items: [
          {
            public_comment_id: 'a',
            quote: 'No data center here.',
            quote_highlighted: 'No <mark>data center</mark> here.',
            speaker_display_name: 'Pat Q.',
            jurisdiction_name: 'Testville',
            state_code: 'ZZ',
            meeting_date: '2026-01-02',
            video_url: 'https://example.test/v',
            jump_url: 'https://example.test/v?t=9s',
            match_basis: 'own_words',
          },
          { public_comment_id: 'b', quote: 'Vote no.', quote_highlighted: 'Vote no.', match_basis: 'same_item', decision_headline: 'Rezoning' },
        ],
      },
    ])
    expect((html.match(/class="kpi-drill-row"/g) ?? []).length).toBe(2)
    expect(html).toContain('<mark')
    expect(html).toContain('Pat Q.')
    expect(html).toContain('Speaker not named')
    expect(html).toContain('https://example.test/v?t=9s')
    expect(html).toContain('2 speakers · Testland')
    expect(html).toContain('All 2 shown.')
    expect(html).not.toContain('dangerouslySetInnerHTML')
  })

  it('links each vote decision to its page', () => {
    const drill: DrillKind = { kind: 'votes', side: 'for' }
    const html = sheet(drill, [
      {
        kind: 'votes',
        total: 8,
        totalDecisions: 1,
        available: true,
        items: [{ data_center_decision_id: 'd1', headline: 'Zoning delayed', votes_for: 8, votes_against: 1, decision_url: '/decisions/d1' }],
      },
    ])
    expect(html).toContain('href="/decisions/d1"')
    expect(html).toContain('8 for, 1 against')
  })

  it('withholds a possible minor but still lists the row, and says why comments carry no words', () => {
    const drill: DrillKind = { kind: 'comments', filter: 'all' }
    const html = sheet(drill, [
      {
        kind: 'comments',
        total: 2,
        available: true,
        note: 'stored without their words',
        items: [
          { data_center_comment_id: 'x', speaker_display_name: 'Lee R.', jump_url: 'https://example.test/w?t=5s', concern_keys: ['water_use'], company_keys: [], possible_minor: false },
          { data_center_comment_id: 'y', possible_minor: true, withheld_reason: 'The speaker may be a minor', concern_keys: [], company_keys: [] },
        ],
      },
    ])
    expect((html.match(/kpi-drill-row/g) ?? []).length).toBe(2)
    expect(html).toContain('The speaker may be a minor')
    expect(html).toContain('stored without their words')
    expect(html).toContain('water use')
  })

  it('offers more until the list reaches the total', () => {
    const items = Array.from({ length: 25 }, (_, i) => ({ public_comment_id: `p${i}`, quote: 'q', quote_highlighted: 'q' }))
    const html = sheet({ kind: 'speakers', side: 'for' }, [{ kind: 'speakers', total: 30, available: true, items }])
    expect(html).toContain('Show more (25 of 30)')
  })
})
