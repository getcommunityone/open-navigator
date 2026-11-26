import { describe, expect, it } from 'vitest'
import { MAP_POPUP_OPTIONS, escapeHtml, meetingsButtonHtml } from './mapPopup'
import { PLACE_POPUP_OPTIONS } from './placePopup'

describe('MAP_POPUP_OPTIONS', () => {
  it('keeps every map popup in view with room on all sides', () => {
    expect(MAP_POPUP_OPTIONS.autoPan).toBe(true)
    expect(MAP_POPUP_OPTIONS.keepInView).toBe(true)
    expect(MAP_POPUP_OPTIONS.autoPanPaddingTopLeft).toEqual([40, 90])
    expect(MAP_POPUP_OPTIONS.autoPanPaddingBottomRight).toEqual([40, 40])
  })

  it('is what the Places popup builds on', () => {
    expect(PLACE_POPUP_OPTIONS).toMatchObject(MAP_POPUP_OPTIONS)
  })
})

describe('escapeHtml', () => {
  it('escapes the characters that can open a tag or an attribute', () => {
    expect(escapeHtml(`<b a="1" b='2'>&`)).toBe('&lt;b a=&quot;1&quot; b=&#39;2&#39;&gt;&amp;')
  })
})

describe('meetingsButtonHtml', () => {
  it('links a 7-digit place GEOID to its meetings page', () => {
    const html = meetingsButtonHtml('0177256')
    expect(html).toContain('Open meetings →')
    expect(html).toContain('href="/jurisdiction/0177256/meetings"')
  })

  it('shows no button when there is no real GEOID', () => {
    for (const bad of ['', 'idx_0', '12', '01772560', undefined, null]) {
      expect(meetingsButtonHtml(bad as string | null | undefined)).toBe('')
    }
  })
})
