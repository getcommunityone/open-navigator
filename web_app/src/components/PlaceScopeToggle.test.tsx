import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { PlaceScopeToggle } from './PlaceScopeToggle'

// #1331: the header's segmented place / National toggle, as markup. Places here are test stand-ins.
const noop = () => {}
const html = (state: Parameters<typeof PlaceScopeToggle>[0]['state']) =>
  renderToStaticMarkup(<PlaceScopeToggle state={state} onPickPlace={noop} onSwitch={noop} />)

describe('PlaceScopeToggle', () => {
  it('with no town: one half reading "Find your town", which opens the picker', () => {
    const h = html({ mode: 'zip' })
    expect(h).toContain('Find your town')
    expect(h).toContain('aria-haspopup="dialog"')
    expect(h).not.toContain('National')
  })

  it('place active: the town half is pressed and offers a change (▾)', () => {
    const h = html({ mode: 'toggle', place: 'Tuscaloosa, AL', active: 'place', canToggle: true })
    expect(h).toMatch(/data-side="place"[^>]*aria-pressed="true"/)
    expect(h).toMatch(/data-side="national"[^>]*aria-pressed="false"/)
    expect(h).toContain('▾')
    expect(h).toContain('aria-label="Tuscaloosa, AL. Change town"')
  })

  it('National active: the National half is pressed; the town half returns to the town (no picker, no ▾)', () => {
    const h = html({ mode: 'toggle', place: 'Tuscaloosa, AL', active: 'national', canToggle: true })
    expect(h).toMatch(/data-side="national"[^>]*aria-pressed="true"/)
    expect(h).toMatch(/data-side="place"[^>]*aria-pressed="false"/)
    expect(h).toContain('aria-label="Show Tuscaloosa, AL"')
    expect(h).not.toContain('▾')
  })

  it('a page with no place scope: the town half only', () => {
    const h = html({ mode: 'toggle', place: 'Tuscaloosa, AL', active: 'place', canToggle: false })
    expect(h).toContain('Tuscaloosa, AL')
    expect(h).not.toContain('National')
  })
})
