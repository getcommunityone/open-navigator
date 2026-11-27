import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { HeaderPlacePhoneView, type HeaderPlacePhoneViewProps } from './HeaderPlacePhone'

// #1301: the phone header's selector, as markup. Places here are test stand-ins.
const noop = () => {}
const base: Omit<HeaderPlacePhoneViewProps, 'state'> = {
  editing: false, zip: '', busy: false, error: null, choices: null,
  onZip: noop, onSubmit: noop, onCancel: noop, onPickChoice: noop, onToggle: noop, onEdit: noop,
}
const html = (p: Partial<HeaderPlacePhoneViewProps> & Pick<HeaderPlacePhoneViewProps, 'state'>) =>
  renderToStaticMarkup(<HeaderPlacePhoneView {...base} {...p} />)

describe('HeaderPlacePhoneView', () => {
  it('with no town: a pin and a 5-digit numeric ZIP field', () => {
    const h = html({ state: { mode: 'zip' } })
    expect(h).toContain('📍')
    expect(h).toMatch(/inputMode="numeric"|inputmode="numeric"/)
    expect(h).toMatch(/autocomplete="postal-code"/i)
    expect(h).toContain('aria-label="ZIP code"')
    expect(h).toMatch(/maxlength="5"/i)
    expect(h).not.toContain('National')
  })

  it('with a town: one tap between the town and National, with the active side pressed', () => {
    const h = html({ state: { mode: 'toggle', place: 'Tuscaloosa, AL', active: 'national', canToggle: true } })
    expect(h).toContain('Tuscaloosa, AL')
    expect(h).toMatch(/aria-pressed="false"[^>]*>.*Tuscaloosa, AL/)
    expect(h).toMatch(/aria-pressed="true"[^>]*>National</)
    expect(h).not.toContain('ZIP code')
  })

  it('a page with no place scope: the town chip only, no National', () => {
    const h = html({ state: { mode: 'toggle', place: 'Tuscaloosa, AL', active: 'place', canToggle: false } })
    expect(h).toContain('Tuscaloosa, AL')
    expect(h).not.toContain('National')
  })

  it('changing the ZIP from the toggle shows the field with a way back', () => {
    const h = html({ state: { mode: 'toggle', place: 'Tuscaloosa, AL', active: 'place', canToggle: true }, editing: true })
    expect(h).toContain('aria-label="ZIP code"')
    expect(h).toContain('aria-label="Keep the current place"')
  })

  it('a ZIP that spans places lists the real choices; an unknown ZIP says so', () => {
    const loc = { state: 'AL', city: 'Northport', county: 'Tuscaloosa' }
    const h = html({ state: { mode: 'zip' }, zip: '35476', choices: [{ label: 'Northport, AL', loc }, { label: 'Tuscaloosa County, AL', loc }] })
    expect(h).toContain('35476 crosses places. Which is home?')
    expect(h).toContain('Northport, AL')
    expect(html({ state: { mode: 'zip' }, error: "We couldn't find that ZIP." })).toContain('find that ZIP')
  })
})
