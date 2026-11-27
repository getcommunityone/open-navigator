import { describe, expect, it } from 'vitest'
import {
  MAP_POPUP_OPTIONS,
  escapeHtml,
  fillMeetingsSlot,
  meetingsButtonHtml,
  meetingsSlotHtml,
} from './mapPopup'
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
    for (const bad of ['', 'idx_0', '12', '123456', '01772560', '0177 56', undefined, null]) {
      expect(meetingsButtonHtml(bad as string | null | undefined)).toBe('')
    }
  })
})

describe('county meetings button', () => {
  it('links a 5-digit county FIPS to its meetings page', () => {
    const html = meetingsButtonHtml('01033')
    expect(html).toContain('Open meetings →')
    expect(html).toContain('href="/jurisdiction/01033/meetings"')
  })

  it('writes an empty slot for a valid id and nothing for a bad one', () => {
    expect(meetingsSlotHtml('01033')).toBe('<div data-meetings-slot="01033"></div>')
    expect(meetingsSlotHtml('')).toBe('')
    expect(meetingsSlotHtml('idx_3')).toBe('')
  })

  // No DOM in the test environment: a stub root that holds one slot.
  function stubRoot(slotId: string) {
    const slot = { innerHTML: '' }
    const root = {
      slot,
      querySelector: (sel: string) => (sel === `[data-meetings-slot="${slotId}"]` ? slot : null),
    }
    return root
  }

  it('fills the slot only when the county has documents', () => {
    const root = stubRoot('01033')
    fillMeetingsSlot(root, '01033', 0)
    expect(root.slot.innerHTML).toBe('')
    fillMeetingsSlot(root, '01033', 72)
    expect(root.slot.innerHTML).toContain('href="/jurisdiction/01033/meetings"')
  })

  it('leaves the slot empty when the count is unknown or the id has no slot', () => {
    const root = stubRoot('01033')
    fillMeetingsSlot(root, '01033', undefined)
    fillMeetingsSlot(root, '01033', Number.NaN)
    fillMeetingsSlot(root, '01001', 5)
    expect(root.slot.innerHTML).toBe('')
  })
})
