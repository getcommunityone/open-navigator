import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { SpeakerName, nameDisplay } from './SpeakerName'

const high = { method: 'self_intro', confidence: 0.9, tier: 'high', evidence: '"my name is ..."' }
const medium = { method: 'chair_call', confidence: 0.6, tier: 'medium', evidence: '"next speaker is ..."' }
const low = { method: 'self_intro', confidence: 0.35, tier: 'low', evidence: '"my name is ..." 90 s earlier' }

describe('SpeakerName', () => {
  it('high shows the name with no likely marker', () => {
    const html = renderToStaticMarkup(<SpeakerName name="Jane D." attribution={high} />)
    expect(html).toContain('Jane D.')
    expect(html).not.toContain('likely')
    expect(html).toContain('How we know')
  })

  it('medium shows the name marked likely, with how it was matched', () => {
    const html = renderToStaticMarkup(<SpeakerName name="Jane D." attribution={medium} />)
    expect(html).toContain('Jane D.')
    expect(html).toContain('likely')
    expect(html).toContain('Matched from the chair calling the speaker')
  })

  it('low does not show the name, only an opt-in possible name', () => {
    expect(nameDisplay('Jane D.', low).identified).toBe(false)
    const html = renderToStaticMarkup(<SpeakerName name="Jane D." attribution={low} possibleName="Joan P." />)
    expect(html).toContain('Speaker not identified')
    expect(html).not.toContain('Jane D.')
    expect(html).toContain('Possibly')
  })

  it('no possible name for a withheld speaker', () => {
    const html = renderToStaticMarkup(<SpeakerName name={null} attribution={low} possibleName={null} />)
    expect(html).toContain('Speaker not identified')
    expect(html).not.toContain('Possibly')
  })
})
