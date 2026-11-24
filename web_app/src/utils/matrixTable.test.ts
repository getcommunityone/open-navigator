import { describe, expect, it } from 'vitest'
import {
  barFraction,
  changeTone,
  filterRows,
  fitsInside,
  layoutLabels,
  parseOff,
  signedChange,
  sparklinePath,
  sparklinePoints,
  stackByRegion,
  toCsv,
  toggleSeries,
  writeOff,
} from './matrixTable'

describe('barFraction', () => {
  it('places a value between min and max', () => {
    expect(barFraction(5, 0, 10)).toBe(0.5)
    expect(barFraction(0, 0, 10)).toBe(0)
    expect(barFraction(10, 0, 10)).toBe(1)
  })
  it('is null for a missing value and 1 when min equals max', () => {
    expect(barFraction(null, 0, 10)).toBeNull()
    expect(barFraction(undefined, 0, 10)).toBeNull()
    expect(barFraction(NaN, 0, 10)).toBeNull()
    expect(barFraction(7, 7, 7)).toBe(1)
  })
  it('keeps a genuine zero and clamps strays', () => {
    expect(barFraction(0, 0, 0)).toBe(1)
    expect(barFraction(-3, 0, 10)).toBe(0)
    expect(barFraction(30, 0, 10)).toBe(1)
  })
})

describe('signedChange', () => {
  it('formats percentage metrics in points', () => {
    expect(signedChange(25.3, 20, 'pp')).toBe('+5.3 pp')
    expect(signedChange(10, 20, 'pp')).toBe('−10 pp')
    expect(signedChange(20, 20, 'pp')).toBe('0.0 pp')
  })
  it('formats other metrics with the supplied formatter', () => {
    expect(signedChange(1300, 1200, 'number', (a) => `${a}k`)).toBe('+100k')
    expect(signedChange(1100, 1200, 'number', (a) => `${a}k`)).toBe('−100k')
  })
  it('is null when either reading is missing', () => {
    expect(signedChange(null, 1, 'pp')).toBeNull()
    expect(signedChange(1, undefined, 'number')).toBeNull()
    expect(signedChange(0, 0, 'number')).toBe('0')
  })
})

describe('changeTone', () => {
  it('reads rising as good unless lower is better', () => {
    expect(changeTone(2, false)).toBe('good')
    expect(changeTone(-2, false)).toBe('bad')
    expect(changeTone(-2, true)).toBe('good')
    expect(changeTone(2, true)).toBe('bad')
  })
})

describe('sparklinePath', () => {
  it('draws one sub-path through consecutive values and ends on the last point', () => {
    const { d, last } = sparklinePath([1, 2, 3], 100, 20)
    expect(d.match(/M/g)).toHaveLength(1)
    expect(d.match(/L/g)).toHaveLength(2)
    expect(last).toEqual({ x: 97, y: 3 })
  })
  it('starts a new sub-path after a gap instead of bridging it', () => {
    const { d, last } = sparklinePath([1, 2, null, 4, 5], 100, 20)
    expect(d.match(/M/g)).toHaveLength(2)
    expect(d.match(/L/g)).toHaveLength(2)
    expect(last!.x).toBe(97)
    expect(sparklinePoints([1, 2, null, 4, 5], 100, 20)[2]).toBeNull()
  })
  it('has no path and no last point when nothing is present', () => {
    expect(sparklinePath([null, null], 100, 20)).toEqual({ d: '', last: null })
    expect(sparklinePath([], 100, 20)).toEqual({ d: '', last: null })
  })
  it('puts a flat series mid-height and the last present value last', () => {
    expect(sparklinePath([5, 5, null], 100, 20).last).toEqual({ x: 50, y: 10 })
  })
})

describe('share labels', () => {
  it('fits a number inside a wide segment only', () => {
    expect(fitsInside(120, '34%')).toBe(true)
    expect(fitsInside(20, '6%')).toBe(false)
  })
  it('staggers a label onto a second row when neighbours would collide', () => {
    const places = layoutLabels([{ cx: 40, w: 60 }, { cx: 60, w: 60 }, { cx: 400, w: 60 }], 500)
    expect(places[0]!.row).toBe(0)
    expect(places[1]!.row).toBeGreaterThan(0)
    expect(places[2]!.row).toBe(0)
  })
  it('never lets two labels in the same row overlap, even when the bar is crowded', () => {
    const boxes = [100, 120, 140, 160, 180, 200].map((cx) => ({ cx, w: 90 }))
    const places = layoutLabels(boxes, 600)
    places.forEach((a, i) =>
      places.forEach((c, j) => {
        if (j > i && a.row === c.row) expect(a.left + 90 <= c.left || c.left + 90 <= a.left).toBe(true)
      }),
    )
  })
  it('keeps labels inside the width', () => {
    const [a, b] = layoutLabels([{ cx: 2, w: 80 }, { cx: 498, w: 80 }], 500)
    expect(a!.left).toBe(0)
    expect(b!.left).toBe(420)
  })
})

describe('toCsv', () => {
  const cols = [
    { key: 'name', label: 'State' },
    { key: 'v', label: 'Value' },
  ]
  it('writes a header and CRLF line ends', () => {
    expect(toCsv(cols, [{ name: 'Ohio', v: 5 }, { name: 'Iowa', v: 7 }])).toBe('State,Value\r\nOhio,5\r\nIowa,7')
  })
  it('quotes commas, quotes and line breaks, doubling embedded quotes', () => {
    expect(toCsv(cols, [{ name: 'A, "B"', v: 1 }, { name: 'x\ny', v: 2 }])).toBe('State,Value\r\n"A, ""B""",1\r\n"x\ny",2')
  })
  it('writes null and undefined as an empty cell, not 0', () => {
    expect(toCsv(cols, [{ name: 'Ohio', v: null }, { name: 'Iowa' }])).toBe('State,Value\r\nOhio,\r\nIowa,')
  })
  it('keeps a year string exactly as given', () => {
    expect(toCsv([{ key: 'y', label: 'Vintage' }], [{ y: '2023' }])).toBe('Vintage\r\n2023')
  })
})

describe('filterRows', () => {
  const rows = [
    { name: 'Alabama', code: 'AL', region: null as string | null },
    { name: 'Ohio', code: 'OH', region: 'Midwest' },
  ]
  it('matches case-insensitively on any key', () => {
    expect(filterRows(rows, 'ohi', ['name', 'code'])).toEqual([rows[1]])
    expect(filterRows(rows, 'MIDW', ['region'])).toEqual([rows[1]])
  })
  it('keeps everything for a blank query and ignores null fields', () => {
    expect(filterRows(rows, '  ', ['name'])).toEqual(rows)
    expect(filterRows(rows, 'null', ['region'])).toEqual([])
  })
})

describe('stackByRegion', () => {
  const regions = ['NE', 'MW']
  it('sums per region and skips missing values', () => {
    const out = stackByRegion(
      [{ vintage: '2020', items: [{ region: 'NE', value: 5 }, { region: 'NE', value: null }, { region: 'MW', value: 3 }, { region: 'S', value: 9 }] }],
      regions,
    )
    expect(out[0]).toEqual({ vintage: '2020', byRegion: { NE: 5, MW: 3 }, counts: { NE: 1, MW: 1 }, total: 8 })
  })
  it('never turns a region with no values into zero', () => {
    const out = stackByRegion([{ vintage: '2021', items: [{ region: 'NE', value: 4 }, { region: 'MW', value: undefined }] }], regions)
    expect(out[0]!.byRegion).toEqual({ NE: 4, MW: null })
    expect(out[0]!.total).toBe(4)
    const none = stackByRegion([{ vintage: '2022', items: [] }], regions)
    expect(none[0]!.total).toBeNull()
  })
  it('keeps a genuine zero', () => {
    expect(stackByRegion([{ vintage: '2020', items: [{ region: 'NE', value: 0 }] }], regions)[0]!.byRegion.NE).toBe(0)
  })
})

describe('series toggles', () => {
  it('hides and shows a series but never the last visible one', () => {
    const all = ['a', 'b']
    const off1 = toggleSeries(new Set(), 'a', all)
    expect([...off1]).toEqual(['a'])
    expect([...toggleSeries(off1, 'b', all)]).toEqual(['a'])
    expect([...toggleSeries(off1, 'a', all)]).toEqual([])
  })
  it('round-trips the ?off= value per section', () => {
    const raw = writeOff(writeOff(null, 'columns', new Set(['NE'])), 'trend', new Set(['median', '01']))
    expect(raw).toBe('columns:NE,trend:median,trend:01')
    expect([...parseOff(raw, 'trend')]).toEqual(['median', '01'])
    expect(writeOff(raw, 'columns', new Set())).toBe('trend:median,trend:01')
    expect(writeOff(null, 'x', new Set())).toBeNull()
  })
})
