import { describe, expect, it } from 'vitest'
import { MAP_POPUP_OPTIONS, escapeHtml } from './mapPopup'
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
