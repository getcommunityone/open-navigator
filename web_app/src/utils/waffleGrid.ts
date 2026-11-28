/**
 * 10x10 proportion waffle allocator (#1400, ported from vizjb12 §4.8A).
 *
 * Allocates exact integer cells summing to `gridSize * gridSize` (100) from real category counts using largest
 * remainder, never inventing data (returns empty when total <= 0). Cells fill bottom-left origin column-major,
 * matching vizjb12's waffle lattice.
 */

export interface WaffleCategory {
  key: string
  label: string
  count: number
  color: string
}

export interface WaffleShare extends WaffleCategory {
  cells: number
  pct: number
}

export interface WaffleCell {
  index: number
  col: number
  row: number
  categoryKey: string
  label: string
  color: string
  sharePct: number
  count: number
}

export function allocateWaffleCells(
  categories: WaffleCategory[],
  gridSize = 10,
): { cells: WaffleCell[]; shares: WaffleShare[]; total: number } {
  const positive = categories.filter((c) => c.count > 0)
  const total = positive.reduce((a, c) => a + c.count, 0)
  const nCells = gridSize * gridSize
  if (total <= 0 || nCells <= 0) return { cells: [], shares: [], total: 0 }

  // Largest-remainder (Hamilton) apportionment so exact integer cells sum to nCells.
  const exact = positive.map((c) => {
    const quota = (c.count / total) * nCells
    const floor = Math.floor(quota)
    return { cat: c, floor, rem: quota - floor, pct: (c.count / total) * 100 }
  })
  let remaining = nCells - exact.reduce((a, x) => a + x.floor, 0)
  const byRem = [...exact].sort((a, b) => b.rem - a.rem || b.cat.count - a.cat.count || a.cat.label.localeCompare(b.cat.label))
  const assigned = new Map<string, number>(exact.map((x) => [x.cat.key, x.floor]))
  for (let i = 0; i < byRem.length && remaining > 0; i++) {
    const key = byRem[i]!.cat.key
    assigned.set(key, (assigned.get(key) ?? 0) + 1)
    remaining -= 1
  }

  // Keep caller's order (usually largest-first or stance order).
  const shares: WaffleShare[] = exact.map((x) => ({
    ...x.cat,
    cells: assigned.get(x.cat.key) ?? 0,
    pct: x.pct,
  }))

  // Fill column-major from bottom-left (col = 0..gridSize-1, row = gridSize-1 down to 0).
  const cells: WaffleCell[] = []
  let idx = 0
  for (const s of shares) {
    for (let k = 0; k < s.cells; k++) {
      const col = Math.floor(idx / gridSize)
      const yRow = gridSize - 1 - (idx % gridSize)
      cells.push({
        index: idx,
        col,
        row: yRow,
        categoryKey: s.key,
        label: s.label,
        color: s.color,
        sharePct: s.pct,
        count: s.count,
      })
      idx += 1
    }
  }
  return { cells, shares, total }
}
