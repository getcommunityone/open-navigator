import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { Dots } from './ChartPanel'
import { chartSpec, type DotsSpec } from '../../utils/stanceGame'
import type { DataCenterMeetingMentionsResponse } from '../../api/dataCenters'

// Test-only records: nothing here is served by the app.
const mention = (id: string, video_url: string, start_seconds: number | null) => ({
  data_center_meeting_mention_id: id,
  video_id: id,
  video_url,
  jump_url: video_url,
  meeting_title: `Meeting ${id}`,
  meeting_date: '2026-05-26',
  jurisdiction_name: 'Testville',
  state_code: 'NC',
  passage_index: 1,
  start_seconds,
  evidence: 'x',
  match_terms: [],
  match_strength: 'data_center',
})

const res = {
  scope: { level: 'national' },
  counts: { passages: 2, meetings: 2, site_specific: 0 },
  items: [mention('a', 'https://www.youtube.com/watch?v=7VghnjHd_1w', 7747.4), mention('b', 'https://example.gov/meeting/9', null)],
} as unknown as DataCenterMeetingMentionsResponse

describe('meeting dots play their recording in place (#972)', () => {
  const spec = chartSpec('meeting-mentions', res, null) as DotsSpec
  const dots = spec.groups.flatMap((g) => g.dots)

  it('gives only a YouTube passage a video, with its start time', () => {
    expect(dots.find((d) => d.id === 'a')?.video).toEqual({ videoId: '7VghnjHd_1w', start: 7747.4 })
    expect(dots.find((d) => d.id === 'b')?.video).toBeUndefined()
  })

  it('marks a video dot as opening a dialog and keeps other dots as plain source links', () => {
    const html = renderToStaticMarkup(<Dots spec={spec} />)
    expect(html).toMatch(/aria-label="Meeting a, Testville, NC, 2026-05-26 \(plays the recording\)"[^>]*aria-haspopup="dialog"|aria-haspopup="dialog"[^>]*aria-label="Meeting a/)
    expect(html).toContain('(opens the source)')
    expect(html).toContain('href="https://example.gov/meeting/9"')
  })

  it('loads nothing from YouTube until a dot is chosen: no iframe and no thumbnail at rest', () => {
    const html = renderToStaticMarkup(<Dots spec={spec} />)
    expect(html).not.toContain('<iframe')
    expect(html).not.toContain('ytimg.com')
    expect(html).not.toContain('youtube-nocookie')
  })
})
