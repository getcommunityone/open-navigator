import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import { hasQuoteText } from '../../lib/highlight'
import { allocateBoxes, positionsBoxes, upcomingStrip, type BoxGroup } from '../../utils/screenBoxes'
import type { TopicUpcomingResponse, UpcomingItem } from '../../api/topicUpcoming'
import ScreenBoxes from './ScreenBoxes'
import UpcomingBoxes from './UpcomingBoxes'
import UpcomingPanel from './UpcomingPanel'

// Test-only rows: nothing here is served by the app.
const g = (key: string, count: number): BoxGroup => ({ key, label: key, count, color: '#123456' })
const item = (id: string, date: string, kind: UpcomingItem['kind'], matched = ''): UpcomingItem => ({
  upcoming_id: id, kind, match_basis: 'agenda_text', date, time: null, jurisdiction_name: 'Testville', state_code: 'ZZ', state: 'Testland',
  body_name: 'Council', title: `Meeting ${id}`, location: null, source_url: 'https://example.test/a', source_label: 'Agenda', matched_text: matched,
  prior_meeting_date: null, prior_url: null, tentative: false,
})
const data = (items: UpcomingItem[]): TopicUpcomingResponse => ({
  topic: 't', topic_id: 1, state_code: 'ZZ', state: 'Testland', city: null, available: true, as_of: '2026-11-27', last_updated: null, built_at: null,
  total: items.length, counts: { meeting: items.length, hearing: 0, deadline: 0, bill_action: 0, event: 0 }, items,
  pending_bills: { total: 0, latest_action_seen: null, items: [] }, broader: null,
})

describe('hasQuoteText (#1415)', () => {
  it('is false for empty, whitespace, bare quote marks and empty marks', () => {
    for (const t of [null, undefined, '', '   ', '“”', '"" ', '<mark></mark>', ' <mark> </mark> ']) expect(hasQuoteText(t)).toBe(false)
  })
  it('is true when there are words', () => {
    expect(hasQuoteText('A <mark>data center</mark> rezoning')).toBe(true)
  })
})

describe('allocateBoxes (#1415)', () => {
  it('draws one box per record when the total fits', () => {
    const a = allocateBoxes([g('a', 3), g('b', 2)])
    expect(a.per).toBe(1)
    expect(a.cells).toHaveLength(5)
  })
  it('states the unit above the cap and keeps every non-empty group', () => {
    const a = allocateBoxes([g('a', 1000), g('b', 1), g('c', 0)])
    expect(a.per).toBe(Math.ceil(1001 / 40))
    expect(a.cells.length).toBeLessThanOrEqual(41)
    expect(new Set(a.cells.map((c) => c.key))).toEqual(new Set(['a', 'b']))
  })
  it('draws nothing for zero', () => {
    expect(allocateBoxes([g('a', 0)]).cells).toHaveLength(0)
  })
})

describe('ScreenBoxes (#1415)', () => {
  it('marks every box with data-box, with a title and a legend', () => {
    const html = renderToStaticMarkup(<ScreenBoxes spec={positionsBoxes({ speakers_for: 2, speakers_against: 5, speakers_question: 0, speakers_neutral: 1 }, 'Georgia')} />)
    expect((html.match(/data-box=""/g) ?? []).length).toBe(8)
    expect(html).toContain('data-chart-title')
    expect(html).toContain('data-chart-legend')
    expect(html).toContain('Georgia: 5 of 8 counted speakers spoke against')
  })
  it('an empty scope shows one hollow box and says so', () => {
    const html = renderToStaticMarkup(<ScreenBoxes spec={positionsBoxes({ speakers_for: 0, speakers_against: 0, speakers_question: 0, speakers_neutral: 0 }, 'Georgia')} />)
    expect((html.match(/data-box=""/g) ?? []).length).toBe(1)
    expect(html).toContain('sb-box--empty')
    expect(html).toContain('No public speaker')
  })
})

describe('Coming up boxes (#1415)', () => {
  it('lays each item on the date strip, coloured by kind, with the next date in the title', () => {
    const d = data([item('1', '2026-12-01', 'meeting'), item('2', '2026-12-02', 'hearing'), item('3', '2027-01-20', 'meeting')])
    const strip = upcomingStrip(d)
    expect(strip.days).toBe(60)
    expect(strip.inWindow).toBe(3)
    const html = renderToStaticMarkup(<UpcomingBoxes data={d} scopeLabel="Georgia" />)
    expect((html.match(/data-box=""/g) ?? []).length).toBe(3)
    expect(html).toContain('3 items ahead in Georgia; the next is Dec 1')
    expect(html).toContain('Public hearing')
  })
  it('items past 90 days are counted in a note, not drawn', () => {
    const d = data([item('1', '2026-12-01', 'meeting'), item('2', '2027-06-01', 'meeting')])
    expect(upcomingStrip(d).later).toBe(1)
  })
  it('nothing upcoming is a hollow box, not invented items', () => {
    const html = renderToStaticMarkup(<UpcomingBoxes data={data([])} scopeLabel="Georgia" />)
    expect((html.match(/data-box=""/g) ?? []).length).toBe(1)
    expect(html).toContain('Nothing is scheduled ahead in Georgia')
  })
})

describe('Coming up list never renders an empty quote (#1415)', () => {
  it('items without matched text show title, date and link but no blockquote', async () => {
    vi.resetModules()
    const qc = new QueryClient()
    qc.setQueryData(['topic-upcoming', 't', 'ZZ', ''], data([item('1', '2026-12-01', 'meeting', ''), item('2', '2026-12-02', 'meeting', '   '), item('3', '2026-12-03', 'meeting', 'A <mark>t</mark> item')]))
    const html = renderToStaticMarkup(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <UpcomingPanel topic="t" stateCode="ZZ" scopeLabel="Testland" subject="t" basePath="/stories/t" />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect((html.match(/<blockquote/g) ?? []).length).toBe(1)
    expect(html).toContain('Meeting 1')
    expect(html).toContain('Take part')
  })
})
