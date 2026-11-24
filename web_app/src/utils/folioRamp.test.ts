import { describe, expect, it } from 'vitest'
import { contrastRatio, FOLIO_INK, FOLIO_NEUTRAL, FOLIO_RAMP, labelOn } from './folioRamp'

describe('folio ramp labels', () => {
  it('every ramp step and the neutral cell reach WCAG AA (4.5:1) with the chosen label colour', () => {
    for (const bg of [...FOLIO_RAMP, FOLIO_NEUTRAL]) {
      expect(contrastRatio(bg, labelOn(bg))).toBeGreaterThanOrEqual(4.5)
    }
  })
  it('uses ink on the lightest step and white on the darkest', () => {
    expect(labelOn(FOLIO_RAMP[0])).toBe(FOLIO_INK)
    expect(labelOn(FOLIO_RAMP[5])).toBe('#FFFFFF')
  })
})
