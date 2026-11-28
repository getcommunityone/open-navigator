import { renderToStaticMarkup } from 'react-dom/server'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import TrendingTermsRow from './TrendingTermsRow'
import type { TrendTermsResponse } from '../../api/trendingTerms'

vi.mock('../../api/trendingTerms', () => ({
  fetchTrendingTerms: vi.fn(() => new Promise(() => {})),
  fetchTrendEvidence: vi.fn(() => new Promise(() => {})),
}))

// Test-only response: nothing here is served by the app.
const resp = (sort: 'rising' | 'hot', state: string | null, city: string | null = null): TrendTermsResponse => ({
  scope: { level: state ? 'state' : 'national', state_code: state, state: state ? 'Georgia' : null, requested_city: city },
  sort,
  year_a: '2025',
  year_b: '2026',
  terms: [
    {
      term_id: 'b'.repeat(32), term: 'sample alpha', rank: 1, meetings_a: 5, meetings_b: 30, recorded_a: 100,
      recorded_b: 200, share_a: 0.05, share_b: 0.15, rise: 3, n_meetings: 35, n_jurisdictions: 9, hot_score: 4.2,
      is_sensitive: false, latest_meeting_date: '2026-11-01',
    },
  ],
})

function render(sort: 'rising' | 'hot', state?: string, city?: string) {
  const qc = new QueryClient()
  // requested_city is left null on purpose: the city note must come from the URL's city, not the response.
  qc.setQueryData(['trending-terms', state ?? '', city ?? '', sort], resp(sort, state ?? null, null))
  return renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <TrendingTermsRow stateCode={state} city={city} sort={sort} onSortChange={() => {}} />
    </QueryClientProvider>,
  )
}

describe('TrendingTermsRow (#1399)', () => {
  it('shows rising chips with an up arrow and the real change, national scope label', () => {
    const html = render('rising')
    expect(html).toContain('Trending in meetings · National')
    expect(html).toContain('sample alpha')
    expect(html).toContain('↑')
    expect(html).toContain('+200%')
    expect(html).toContain('overflow-x:auto')
  })

  it('shows a flame on the heated sort and names the state scope', () => {
    const html = render('hot', 'GA')
    expect(html).toContain('Trending in meetings · Georgia')
    expect(html).toContain('🔥')
    expect(html).toContain('aria-pressed="true"')
  })

  it('says a city is answered by its state', () => {
    expect(render('rising', 'GA', 'Atlanta')).toContain('counted per state, not per city')
  })
})
