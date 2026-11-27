import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'
import TopicCountyMap from './TopicCountyMap'
import type { TopicPlaces } from '../../api/topics'

// Test stand-ins shaped like GET /api/topics/{id}/places, not warehouse figures.
const place = (id: string, meetings: number) => ({
  jurisdiction_id: id,
  jurisdiction_name: `Town ${id}`,
  jurisdiction_type: 'city',
  geoid: null,
  latitude: 33,
  longitude: -87,
  meetings,
  lean_meetings: 0,
  speakers_against: 0,
  speakers_for: 0,
  speakers_neutral: 0,
  speakers_question: 0,
  silent_meetings: 0,
  public_against_meetings: 0,
  disagreement_meetings: 0,
})

function render(data: TopicPlaces | undefined) {
  const qc = new QueryClient()
  if (data) qc.setQueryData(['topic-story', 99, 'places', 'ZZ'], data)
  return renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <TopicCountyMap
          topicId={99}
          stateCode="ZZ"
          scopeLabel="Testland"
          subject="test topic"
          onPickState={() => {}}
          fallback={<p data-testid="outline">outline</p>}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('TopicCountyMap (#1349)', () => {
  it('waits on a quiet skeleton, not the outline, while the place counts load', () => {
    expect(render(undefined)).not.toContain('data-testid="outline"')
  })

  it('keeps the honest outline when the mart is not published', () => {
    const html = render({ topic_id: 99, state_code: 'ZZ', total_meetings: 4, unplaced_meetings: 4, available: false, by_place: [] })
    expect(html).toContain('data-testid="outline"')
  })

  it('keeps the outline when none of the meetings can be placed', () => {
    const html = render({ topic_id: 99, state_code: 'ZZ', total_meetings: 3, unplaced_meetings: 3, available: true, by_place: [] })
    expect(html).toContain('data-testid="outline"')
  })

  it('draws the county map, not the outline, once a meeting is placed', () => {
    const html = render({ topic_id: 99, state_code: 'ZZ', total_meetings: 5, unplaced_meetings: 1, available: true, by_place: [place('a', 4)] })
    expect(html).not.toContain('data-testid="outline"')
  })
})
