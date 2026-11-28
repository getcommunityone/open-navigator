import { describe, expect, it } from 'vitest'
import { allocateWaffleCells } from './waffleGrid'

describe('allocateWaffleCells (#1400)', () => {
  it('returns empty for zero or empty categories (no fabricated data)', () => {
    expect(allocateWaffleCells([])).toEqual({ cells: [], shares: [], total: 0 })
    expect(allocateWaffleCells([{ key: 'a', label: 'A', count: 0, color: '#000' }])).toEqual({ cells: [], shares: [], total: 0 })
  })

  it('allocates exactly 100 cells using largest remainder and fills bottom-left column-major', () => {
    const res = allocateWaffleCells([
      { key: 'against', label: 'Opposed', count: 67, color: '#b45309' },
      { key: 'for', label: 'Supportive', count: 33, color: '#0f766e' },
      { key: 'zero', label: 'Empty', count: 0, color: '#ccc' },
    ])
    expect(res.total).toBe(100)
    expect(res.cells).toHaveLength(100)
    expect(res.shares).toHaveLength(2)
    expect(res.shares[0]!.cells).toBe(67)
    expect(res.shares[1]!.cells).toBe(33)
    // First cell sits at bottom-left (col=0, row=9), tenth cell at top-left (col=0, row=0).
    expect(res.cells[0]).toMatchObject({ col: 0, row: 9, categoryKey: 'against' })
    expect(res.cells[9]).toMatchObject({ col: 0, row: 0, categoryKey: 'against' })
    expect(res.cells[10]).toMatchObject({ col: 1, row: 9, categoryKey: 'against' })
    expect(res.cells[99]).toMatchObject({ col: 9, row: 0, categoryKey: 'for' })
  })

  it('handles fractional quotas cleanly without losing a cell', () => {
    const res = allocateWaffleCells([
      { key: 'a', label: 'A', count: 1, color: '#111' },
      { key: 'b', label: 'B', count: 1, color: '#222' },
      { key: 'c', label: 'C', count: 1, color: '#333' },
    ])
    expect(res.cells).toHaveLength(100)
    expect(res.shares.reduce((a, s) => a + s.cells, 0)).toBe(100)
    expect(res.shares.map((s) => s.cells).sort()).toEqual([33, 33, 34])
  })
})
