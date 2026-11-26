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
  it('has the house theme and the seven reference themes, the default first, and falls back to it for an unknown id', () => {
    expect(DEFAULT_THEME_ID).toBe('open-navigator')
    expect(FOLIO_THEMES).toHaveLength(8)
    expect(FOLIO_THEMES.map((t) => t.id)).toEqual(['open-navigator', 'lavender-press', 'newsprint', 'night-edition', 'gazette-mono', 'swiss-poster', 'forest-ochre', 'riso-pastel'])
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
        for (const fg of ['--ink', '--ink-2', '--ink-3', '--violet-ink', '--vermilion-ink', '--bad-ink']) {
          expect(contrastRatio(bg, t.vars[fg]!), `${fg} on ${bg}`).toBeGreaterThanOrEqual(4.5)
        }
      }
      expect(contrastRatio(t.vars['--band']!, t.vars['--white']!)).toBeGreaterThanOrEqual(4.5)
    })
  }
})

// Colour-vision check for the house theme: simulate the three common deficiencies (Machado et al. 2009, severity 1) and
// require every pair of series, and each neighbouring pair of segment colours, to stay apart (CIE76 delta E >= 12).
const CVD = {
  protan: [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]],
  deutan: [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.01182, 0.04294, 0.968881]],
  tritan: [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.3039]],
} as const
const toLinear = (hex: string): number[] => {
  const n = parseInt(hex.slice(1), 16)
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((c) => {
    const s = c / 255
    return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
  })
}
const lab = (rgb: number[]): number[] => {
  const [r, g, b] = rgb as [number, number, number]
  const xyz = [(0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047, 0.2126 * r + 0.7152 * g + 0.0722 * b, (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883]
  const f = (t: number) => (t > 0.008856 ? Math.cbrt(t) : 7.787 * t + 16 / 116)
  const [fx, fy, fz] = xyz.map(f) as [number, number, number]
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)]
}
const deltaE = (a: string, b: string, kind: keyof typeof CVD | null): number => {
  const sim = (hex: string) => {
    const lin = toLinear(hex)
    return kind ? CVD[kind].map((row) => Math.min(1, Math.max(0, row[0]! * lin[0]! + row[1]! * lin[1]! + row[2]! * lin[2]!))) : lin
  }
  const [p, q] = [lab(sim(a)), lab(sim(b))] as [number[], number[]]
  return Math.hypot(p[0]! - q[0]!, p[1]! - q[1]!, p[2]! - q[2]!)
}

describe('open-navigator theme colour-vision safety', () => {
  const t = themeById('open-navigator')
  for (const kind of [null, 'protan', 'deutan', 'tritan'] as const) {
    it(`series stay apart (${kind ?? 'normal vision'})`, () => {
      for (let i = 0; i < t.series.length; i++)
        for (let j = i + 1; j < t.series.length; j++) expect(deltaE(t.series[i]!, t.series[j]!, kind), `${t.series[i]} vs ${t.series[j]}`).toBeGreaterThanOrEqual(12)
    })
    it(`neighbouring segment colours stay apart (${kind ?? 'normal vision'})`, () => {
      const seg = t.seg.slice(0, -1) // the last one is the neutral track colour
      for (let i = 0; i + 1 < seg.length; i++) expect(deltaE(seg[i]!, seg[i + 1]!, kind), `${seg[i]} vs ${seg[i + 1]}`).toBeGreaterThanOrEqual(12)
    })
  }
})
