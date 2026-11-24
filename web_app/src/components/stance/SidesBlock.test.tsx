import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import SidesBlock, { passageLink, type Passage } from './SidesBlock'

// Test-only wording: nothing here is served by the app.
const p = (quote: string, extra: Partial<Passage> = {}): Passage => ({ quote, jurisdictionName: 'Testville', ...extra })

describe('SidesBlock', () => {
  it('renders nothing without sides, or when either side is empty', () => {
    expect(renderToStaticMarkup(<SidesBlock sides={undefined} />)).toBe('')
    expect(renderToStaticMarkup(<SidesBlock sides={{ for: [p('a')], against: [] }} />)).toBe('')
    expect(renderToStaticMarkup(<SidesBlock sides={{ for: [], against: [p('b')] }} />)).toBe('')
  })
  it('shows both columns with the quote, its source and a timestamped link', () => {
    const html = renderToStaticMarkup(
      <SidesBlock
        sides={{
          for: [p('quote-for', { speakerRole: 'Resident', meetingDate: '2025-01-02', videoUrl: 'https://example.test/v?id=1', startSeconds: 95 })],
          against: [p('quote-against')],
        }}
      />,
    )
    expect(html).toContain('What was said for')
    expect(html).toContain('What was said against')
    expect(html).toContain('quote-for')
    expect(html).toContain('Resident')
    expect(html).toContain('t=95s')
    expect(html).not.toContain('undefined')
  })
  it('caps each side at two quotes with a control for the rest', () => {
    const many = [p('q1'), p('q2'), p('q3')]
    const html = renderToStaticMarkup(<SidesBlock sides={{ for: many, against: [p('x')] }} />)
    expect(html).toContain('q2')
    expect(html).not.toContain('q3')
    expect(html).toContain('Show 1 more')
  })
  it('adds a start time only when it is known', () => {
    expect(passageLink(p('q', { videoUrl: 'https://example.test/v' }))).toBe('https://example.test/v')
    expect(passageLink(p('q'))).toBeNull()
  })
})
