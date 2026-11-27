import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import DumbbellRows, { type DumbbellRow } from './DumbbellRows'

// Test-only rows: nothing here is served by the app.
const rows: DumbbellRow[] = [
  { key: 'up', label: 'Up', a: 10, b: 40, right: '+300%', ariaLabel: 'Up', tip: { cat: 'Up', val: '' } },
  { key: 'down', label: 'Down', a: 30, b: 20, right: '−33%', negative: true, ariaLabel: 'Down', tip: { cat: 'Down', val: '' } },
]

describe('DumbbellRows options for Browse all topics (#1343)', () => {
  it('prints values over the dots with a custom format, tones the falling dot, and makes rows links', () => {
    const html = renderToStaticMarkup(
      <DumbbellRows rows={rows} aName="2025" bName="2026" ariaLabel="x" unitPlural="topics" format={(v) => `${v} mtgs`} valuesOverDots toneDots onSelect={() => {}} />,
    )
    expect(html).toContain('40 mtgs')
    expect(html).toContain('10 mtgs')
    expect(html).toContain('sc-dot-down')
    expect(html).toContain('role="link"')
  })

  it('leaves the story dumbbell as it was by default', () => {
    const html = renderToStaticMarkup(<DumbbellRows rows={rows} aName="2025" bName="2026" ariaLabel="x" unitPlural="topics" />)
    expect(html).not.toContain('sc-dot-down')
    expect(html).not.toContain('role="link"')
    expect(html).toContain('role="img"')
  })
})
