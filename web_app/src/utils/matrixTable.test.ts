import { describe, expect, it } from 'vitest'
import { filterRows, parseOff, stackByRegion, toCsv, toggleSeries, writeOff } from './matrixTable'

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
