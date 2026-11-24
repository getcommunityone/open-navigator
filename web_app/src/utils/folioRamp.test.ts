import { describe, expect, it } from 'vitest'
import { contrastRatio, FOLIO_INK, FOLIO_NEUTRAL, FOLIO_RAMP, labelOn } from './folioRamp'
import { DEFAULT_THEME_ID, FOLIO_THEMES, themeById } from './folioThemes'

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

describe('every theme', () => {
  it('has seven themes, the default first, and falls back to it for an unknown id', () => {
    expect(FOLIO_THEMES).toHaveLength(7)
    expect(FOLIO_THEMES[0]!.id).toBe(DEFAULT_THEME_ID)
    expect(themeById('nope').id).toBe(DEFAULT_THEME_ID)
    expect(themeById(null).id).toBe(DEFAULT_THEME_ID)
    expect(themeById('night-edition').dark).toBe(true)
  })
  for (const t of FOLIO_THEMES) {
    const ink = t.vars['--ink']!
    it(`${t.id}: ramp steps, neutral, series and segment colours carry a label at 4.5:1`, () => {
      for (const bg of [...t.ramp, t.neutral, ...t.series, ...t.seg]) {
        expect(contrastRatio(bg, labelOn(bg, [ink]))).toBeGreaterThanOrEqual(4.5)
      }
    })
    it(`${t.id}: table bars, sparklines and share-label leaders are visible (3:1) on the page and against the bar track`, () => {
      const v = t.vars
      // The bar fill and sparkline stroke are --violet-ink; the track is --neutral-data; leaders are --ink-3.
      for (const paper of [v['--paper']!, v['--paper-raised']!]) {
        expect(contrastRatio(paper, v['--violet-ink']!), 'fill on paper').toBeGreaterThanOrEqual(3)
        expect(contrastRatio(paper, v['--ink-3']!), 'leader on paper').toBeGreaterThanOrEqual(3)
      }
      expect(contrastRatio(t.neutral, v['--violet-ink']!), 'fill on track').toBeGreaterThanOrEqual(3)
      expect(t.neutral).toBe(v['--neutral-data'])
    })
    it(`${t.id}: body text, links and the section band are at 4.5:1`, () => {
      for (const bg of [t.vars['--paper']!, t.vars['--paper-raised']!]) {
        for (const fg of ['--ink', '--ink-2', '--ink-3', '--violet-ink', '--vermilion-ink']) {
          expect(contrastRatio(bg, t.vars[fg]!), `${fg} on ${bg}`).toBeGreaterThanOrEqual(4.5)
        }
      }
      expect(contrastRatio(t.vars['--band']!, t.vars['--white']!)).toBeGreaterThanOrEqual(4.5)
    })
  }
})
