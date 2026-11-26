import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import ChatMarkdown from './ChatMarkdown'

const html = (text: string) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <ChatMarkdown text={text} />
    </MemoryRouter>,
  )

describe('ChatMarkdown (#1011)', () => {
  it('renders bold, bullets and meeting links without raw markdown', () => {
    const out = html(
      'Two councils acted.\n\n- **Dunes City, OR**: rejected the initiative ([City Council, 2026-06-17](/meetings/79744))\n- **Tuscaloosa, AL**: approved permits (/meetings/14307)',
    )
    expect(out).not.toContain('**')
    expect(out.match(/<li>/g)).toHaveLength(2)
    expect(out).toContain('<strong>Dunes City, OR</strong>')
    expect(out).toMatch(/href="\/meetings\/79744"[^>]*>City Council, 2026-06-17<\/a>/)
    expect(out).toMatch(/href="\/meetings\/14307"[^>]*>meeting<\/a>/)
  })

  it('never links an unsafe scheme', () => {
    const out = html('See [this](javascript:alert(1)) and [ok](https://example.org/x).')
    expect(out).not.toContain('javascript:')
    expect(out).toContain('href="https://example.org/x"')
    expect(out).toContain('this')
  })

  it('escapes HTML in the answer', () => {
    expect(html('<img src=x onerror=alert(1)>')).not.toContain('<img')
  })
})
