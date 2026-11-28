import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { HeatFlames, heatLabel } from './HeatFlames'

describe('HeatFlames', () => {
  it('labels the rating for assistive tech', () => {
    expect(heatLabel(4)).toBe('Heat 4 of 5')
    const html = renderToStaticMarkup(<HeatFlames heat={4} method="ai_meeting_analysis" />)
    expect(html).toContain('aria-label="Heat 4 of 5"')
    expect(html).toContain("Rated by the meeting analysis")
    expect(html.match(/is-on/g)?.length).toBe(4)
  })
  it('renders nothing for null or out-of-range heat', () => {
    expect(renderToStaticMarkup(<HeatFlames heat={null} />)).toBe('')
    expect(renderToStaticMarkup(<HeatFlames heat={0} />)).toBe('')
    expect(heatLabel(6)).toBeNull()
  })
})
