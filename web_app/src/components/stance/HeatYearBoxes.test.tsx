import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import HeatYearBoxes from './HeatYearBoxes'
import type { TopicHeatByYear } from '../../api/topics'

// Test-only fixtures: nothing here is served by the app.
function html(data: TopicHeatByYear) {
  const qc = new QueryClient()
  qc.setQueryData(['topic-heat-by-year', 't', 'national', ''], data)
  return renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <HeatYearBoxes topic="t" scopeLabel="National" subject="data centers" />
    </QueryClientProvider>,
  )
}

describe('HeatYearBoxes (#1418)', () => {
  it('draws one box per heated speaker, labels each year and leads with a fall', () => {
    const out = html({
      topic: 't',
      years: [
        { year: '2025', mean: 3.8, speakers_rated: 40, share_heated: 0.5, speakers_heated: 5 },
        { year: '2026', mean: 2.9, speakers_rated: 55, share_heated: 0.2, speakers_heated: 11 },
      ],
    })
    expect(out.match(/data-box/g)?.length).toBe(16)
    expect(out).toContain('2026')
    expect(out).toContain('cooling')
  })
  it('renders nothing when no year met the minimum', () => {
    expect(html({ topic: 't', years: [] })).toBe('')
  })
})
