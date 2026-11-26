import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import QuoteCard from './QuoteCard'

// Test-only wording: nothing here is served by the app.
describe('QuoteCard (#1108)', () => {
  it('shows the real thumbnail, play label, place/date, highlighted quote and speaker row', () => {
    const html = renderToStaticMarkup(
      <QuoteCard
        place="Testville, MO"
        date="2026-05-07"
        quote="we need <mark>data center</mark> answers"
        side="against"
        speakerName="Test P."
        role="Resident"
        item="Rezoning for a site"
        videoId="7VghnjHd_1w"
        startSeconds={247}
        url="https://www.youtube.com/watch?v=7VghnjHd_1w&t=247s"
      />,
    )
    expect(html).toContain('https://i.ytimg.com/vi/7VghnjHd_1w/hqdefault.jpg')
    expect(html).toContain('alt="Recording of the Testville, MO meeting"')
    expect(html).toContain('Hear it at 4:07')
    expect(html).toContain('Testville, MO · May 7, 2026')
    expect(html).toMatch(/<mark[^>]*>data center<\/mark>/)
    expect(html).toContain('>TP<')
    expect(html).toContain('Test P.')
    expect(html).toContain('Spoke against')
    expect(html).toContain('Resident · On: Rezoning for a site')
    expect(html).not.toContain('In the meeting')
  })
  it('has no image without a video, and no speaker row for a meeting passage', () => {
    const html = renderToStaticMarkup(<QuoteCard place="Testville, MO" date={null} quote="a passage" meeting="Council" />)
    expect(html).not.toContain('<img')
    expect(html).not.toContain('qcard-speaker')
    expect(html).toContain('In the meeting · Council')
  })
  it('the header variant never shows the image and names the start time', () => {
    const html = renderToStaticMarkup(<QuoteCard variant="header" place="Testville, MO" quote="q" videoId="7VghnjHd_1w" startSeconds={65} />)
    expect(html).not.toContain('<img')
    expect(html).toContain('from 1:05')
  })
  it('never invents an avatar without a name', () => {
    const html = renderToStaticMarkup(<QuoteCard place="Testville" quote="q" side="for" />)
    expect(html).not.toContain('qcard-avatar')
    expect(html).toContain('Spoke for')
  })
  it('shows the AI summary, labelled, and the meeting analysis link when on record (#1124)', () => {
    const html = renderToStaticMarkup(
      <QuoteCard
        place="Testville, GA"
        quote="a passage"
        meeting="Council"
        summary="The board <b>discussed</b> a pause."
        analysisUrl="/meetings/12?state=GA"
      />,
    )
    expect(html).toContain('AI summary')
    // React-escaped: markup in the record is shown as text, never rendered.
    expect(html).toContain('The board &lt;b&gt;discussed&lt;/b&gt; a pause.')
    expect(html).toContain('class="qcard-summary-text"')
    expect(html).toContain('href="/meetings/12?state=GA"')
    expect(html).toContain('Open the meeting analysis →')
    expect(html).toContain('In the meeting · Council')
  })
  it('shows no summary block and no link without them (#1124)', () => {
    const html = renderToStaticMarkup(<QuoteCard place="Testville, GA" quote="a passage" summary="   " analysisUrl={null} />)
    expect(html).not.toContain('AI summary')
    expect(html).not.toContain('qcard-summary')
    expect(html).not.toContain('Open the meeting analysis')
  })
  it('names an attributed speaker instead of "In the meeting" (#1124)', () => {
    const html = renderToStaticMarkup(<QuoteCard place="Testville, GA" quote="a passage" meeting="Council" speakerName="Test P." role="Resident" />)
    expect(html).toContain('Test P.')
    expect(html).toContain('Resident')
    expect(html).not.toContain('In the meeting')
  })
})
