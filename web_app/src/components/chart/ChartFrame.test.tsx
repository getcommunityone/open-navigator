import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'
import ChartFrame from './ChartFrame'
import BoxWaffleChart from '../stance/BoxWaffleChart'
import DumbbellRows, { type DumbbellRow } from '../stance/DumbbellRows'
import { CountBars } from '../stance/FitDisplay'
import { Dots } from '../stance/ChartPanel'
import StoryCountyMap, { type PlaceCount } from '../stance/StoryCountyMap'
import StoryStatesMap from '../home/StoryStatesMap'
import StoryDotMap from '../stance/StoryDotMap'
import TimelineChart from '../stance/TimelineChart'
import LegislationMap from '../stance/LegislationMap'
import type { DotsSpec } from '../../utils/stanceGame'

// Test-only fixtures: shapes the API returns, never served by the app.
const square = (x0: number, y0: number, x1: number, y1: number) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]
const topo = {
  type: 'Topology',
  arcs: [square(0, 0, 480, 600), square(490, 0, 970, 600), square(490, 0, 730, 600), square(740, 0, 970, 600)],
  objects: {
    states: { type: 'GeometryCollection', geometries: [{ type: 'Polygon', id: '01', arcs: [[0]], properties: { name: 'Alabama' } }, { type: 'Polygon', id: '12', arcs: [[1]], properties: { name: 'Florida' } }] },
    counties: { type: 'GeometryCollection', geometries: [{ type: 'Polygon', id: '12001', arcs: [[2]], properties: { name: 'Alachua' } }, { type: 'Polygon', id: '12003', arcs: [[3]], properties: { name: 'Baker' } }] },
  },
}

const withClient = (el: JSX.Element, seed: (qc: QueryClient) => void = () => {}) => {
  const qc = new QueryClient()
  qc.setQueryData(['us-atlas-states-albers'], topo)
  qc.setQueryData(['us-atlas-counties-albers'], topo)
  seed(qc)
  return renderToStaticMarkup(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{el}</MemoryRouter>
    </QueryClientProvider>,
  )
}

/** A rendered chart has exactly the frame's title and a non-empty legend. */
function expectFramed(html: string) {
  expect(html).toContain('data-chart-frame')
  const title = /data-chart-title[^>]*>([^<]{4,})/.exec(html)
  expect(title, 'a title').not.toBeNull()
  const legend = /data-chart-legend[^>]*>([\s\S]*?)<\/div><\/div>|data-chart-legend[^>]*>([\s\S]*?)<\/div>/.exec(html)
  expect(legend, 'a legend').not.toBeNull()
  expect(((legend?.[1] ?? legend?.[2]) ?? '').replace(/<[^>]+>/g, '').trim().length).toBeGreaterThan(2)
}

const place = (id: string, name: string, meetings: number, extra: Partial<PlaceCount> = {}): PlaceCount => ({
  jurisdiction_id: id,
  jurisdiction_name: name,
  jurisdiction_type: 'county',
  geoid: id,
  latitude: null,
  longitude: null,
  meetings,
  speakers_for: 0,
  speakers_against: 0,
  speakers_question: 0,
  speakers_neutral: 0,
  ...extra,
})

describe('every map and chart has a title and a legend (#1409)', () => {
  it('ChartFrame renders both, and the types require them', () => {
    const html = renderToStaticMarkup(
      <ChartFrame title="Short-term rentals came up in 9 meetings" legend={[{ key: 'a', label: 'Spoke against', color: '#c00' }]}>
        <svg />
      </ChartFrame>,
    )
    expectFramed(html)
    // @ts-expect-error title and legend are required
    renderToStaticMarkup(<ChartFrame>x</ChartFrame>)
  })

  it('the county map keeps its title and key with no side panel (home, chrome off)', () => {
    const byPlace = [place('12001', 'Alachua County', 9, { speakers_against: 4, speakers_for: 1 }), place('12003', 'Baker County', 3)]
    for (const chrome of [true, false]) {
      const html = withClient(<StoryCountyMap stateCode="FL" scopeLabel="Florida" byPlace={byPlace} onPickState={() => {}} chrome={chrome} subject="short-term rentals" />)
      expect(html).toContain('stance-map-svg')
    expectFramed(html)
    }
  })

  it('the national map and the dot map', () => {
    const byState = [{ state_code: 'AL', state: 'Alabama', meetings: 9 }, { state_code: 'FL', state: 'Florida', meetings: 4 }]
    const html = withClient(<StoryStatesMap byState={byState} highlight={null} href={(c) => `/x?state=${c}`} subject="short-term rentals" />)
    expect(html).toContain('<svg')
    expectFramed(html)
    const dot = withClient(<StoryDotMap byState={byState} scopeStateCode={null} scopeLabel="National" onPickState={() => {}} />)
    expect(dot).toContain('<svg')
    expectFramed(dot)
  })

  it('box waffle, dumbbell rows, count bars and dots', () => {
    expectFramed(
      renderToStaticMarkup(
        <BoxWaffleChart title="Who spoke" unitLabel="speakers" categories={[{ key: 'a', label: 'Against', count: 30, color: '#c00' }, { key: 'b', label: 'For', count: 10, color: '#0a0' }]} />,
      ),
    )
    const rows: DumbbellRow[] = [{ key: 'up', label: 'Up', a: 0.1, b: 0.4, right: '+30 pp', ariaLabel: 'Up', tip: { cat: 'Up', val: '' } }]
    expectFramed(renderToStaticMarkup(<DumbbellRows title="Share of meetings, 2025 and 2026" rows={rows} aName="2025" bName="2026" ariaLabel="x" unitPlural="places" />))
    expectFramed(renderToStaticMarkup(<CountBars label="Sites by status" rows={[{ label: 'Planned', count: 8 }, { label: 'Operating', count: 2 }]} />))
    const spec: DotsSpec = {
      kind: 'dots', title: 'Meetings', source: 'test', note: null, unit: 'meeting', drawn: 2, grandTotal: 2, perDot: 1, dotMeans: 'One dot is one meeting.',
      groups: [{ key: 'g', label: 'Group', shown: 2, total: 2, share: 100, heading: 'Group · 2', dots: [{ id: '1', title: 'A' }, { id: '2', title: 'B' }] }],
    } as unknown as DotsSpec
    expectFramed(withClient(<Dots spec={spec} />))
  })

  it('the timeline and the legislation map', () => {
    const years = [{ year: '2025', meetings: 12, passages: null, all_recorded_meetings: 600, share: 0.02 }, { year: '2026', meetings: 18, passages: null, all_recorded_meetings: 580, share: 0.031 }, { year: '2027', meetings: 20, passages: null, all_recorded_meetings: 500, share: 0.04 }, { year: '2028', meetings: 22, passages: null, all_recorded_meetings: 500, share: 0.044 }, { year: '2029', meetings: 25, passages: null, all_recorded_meetings: 500, share: 0.05 }, { year: '2030', meetings: 31, passages: null, all_recorded_meetings: 500, share: 0.062 }]
    const tl = withClient(<TimelineChart topic="t" scopeLabel="Florida" subject="short-term rentals" idBase="t" />, (qc) =>
      qc.setQueryData(['topic-timeline', 't', 'national', ''], { topic: 't', topic_name: 'T', scope: { level: 'national', state_code: null, state: null, city: null }, years, undated_meetings: 0, total_meetings: 128, total_passages: null, milestones: [], coverage_available: true, bills_available: false }),
    )
    expect(tl).toContain('sc-trend')
    expectFramed(tl)
    const lm = withClient(<LegislationMap topic="t" scopeLabel="National" subject="x" />, (qc) =>
      qc.setQueryData(['topic-legislation', 't'], { available: true, total_bills: 1, categories: [], summary: [{ state_code: 'AL', state: 'Alabama', year: '2026', category: 'restrict', status: 'enacted', bills: 1 }] }),
    )
    expect(lm).toContain('lm-map')
    expectFramed(lm)
  })
})
