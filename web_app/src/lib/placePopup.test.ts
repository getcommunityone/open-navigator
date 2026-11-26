import { describe, expect, it } from 'vitest'
import { PLACE_POPUP_OPTIONS, placePopupHtml, type PlacePopupPin } from './placePopup'

const pin: PlacePopupPin = {
  geoid: '0177256',
  name: 'Tuscaloosa',
  state_code: 'AL',
  place_count: 1,
  transcript_count: 12,
}

describe('placePopupHtml', () => {
  it('gives a place an "Open meetings →" button to its meetings page', () => {
    const html = placePopupHtml(pin, 'city')
    expect(html).toContain('Open meetings →')
    expect(html).toContain('href="/jurisdiction/0177256/meetings"')
  })

  it('uses the same meetings button for counties and school districts', () => {
    for (const level of ['county', 'school_district']) {
      expect(placePopupHtml(pin, level)).toContain('/jurisdiction/0177256/meetings')
    }
  })

  it('gives a state a button to the places list filtered to it', () => {
    const html = placePopupHtml({ ...pin, name: 'Alabama', place_count: 3 }, 'state')
    expect(html).toContain('Browse places in Alabama →')
    expect(html).toContain('href="/jurisdictions?state=AL"')
    expect(html).toContain('3 indexed places')
  })

  it('escapes the place name', () => {
    const html = placePopupHtml({ ...pin, name: '<img src=x onerror=alert(1)>' }, 'city')
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img')
  })

  it('pluralises the real transcript count', () => {
    expect(placePopupHtml({ ...pin, transcript_count: 1 }, 'city')).toContain('1 transcript<')
    expect(placePopupHtml(pin, 'city')).toContain('12 transcripts')
  })
})

describe('PLACE_POPUP_OPTIONS', () => {
  it('keeps the popup in view with room on every side', () => {
    expect(PLACE_POPUP_OPTIONS.autoPan).toBe(true)
    expect(PLACE_POPUP_OPTIONS.keepInView).toBe(true)
    expect(PLACE_POPUP_OPTIONS.autoPanPaddingTopLeft).toEqual([40, 90])
    expect(PLACE_POPUP_OPTIONS.autoPanPaddingBottomRight).toEqual([40, 40])
  })
})
