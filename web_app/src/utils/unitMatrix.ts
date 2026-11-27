/**
 * Unit matrix groupings (#1140): one square per record, regrouped by a real field of each record.
 *
 * A grouping is offered only when the records really carry its field (at least one record has it). Records without the
 * field are counted in a group that says so ("Date not given", "Not screened"), so the groups always add up to the records
 * drawn. A group is never drawn for zero records, and every percentage is a real count over the records drawn.
 */

export type OutcomeKey = 'approved' | 'denied' | 'tabled' | 'moratorium' | 'no_action'
export type SideKey = 'against' | 'for' | 'mixed' | 'no_side'

/** Real fields of one record that a matrix can group by. Absent or null means the record does not carry it. */
export interface DotFacets {
  year?: string | null
  /** 2-letter state code. */
  state?: string | null
  /** The town or government (jurisdiction name). */
  town?: string | null
  /** What officials did, from the AI reading of the meeting. */
  outcome?: OutcomeKey | null
  /** Whether the public mostly opposed, mostly supported or split, from the AI reading of the meeting. */
  side?: SideKey | null
}

export type GroupingKey = 'all' | 'native' | 'year' | 'place' | 'outcome' | 'side'

export interface MatrixRecord {
  facets?: DotFacets
  /** The record's group in the chart's own grouping (e.g. Debated / Without debate). */
  nativeKey?: string
}

export interface MatrixGroup {
  key: string
  label: string
  count: number
  /** Percent of the records drawn, one decimal. */
  pct: number
  /** Indices into the record list, in order. */
  members: number[]
  /** A semantic tone for the colour, when the grouping has one. */
  tone?: OutcomeKey | SideKey
}

export const OUTCOME_LABELS: Record<OutcomeKey, string> = {
  approved: 'Approved',
  denied: 'Denied',
  tabled: 'Tabled or deferred',
  moratorium: 'Moratorium',
  no_action: 'No action',
}
export const SIDE_LABELS: Record<SideKey, string> = {
  against: 'Public mostly opposed',
  for: 'Public mostly supported',
  mixed: 'Both sides spoke',
  no_side: 'Spoke, no side',
}
/** The "By who spoke" groups in a topic's own position words (#1200, utils/topicPositions). */
export function sideLabelsFor(w: { against: string; for: string; split: string; silent: string }): Record<SideKey, string> {
  return { against: w.against, for: w.for, mixed: w.split, no_side: w.silent }
}
const OUTCOME_ORDER: OutcomeKey[] = ['approved', 'denied', 'tabled', 'moratorium', 'no_action']
const SIDE_ORDER: SideKey[] = ['against', 'for', 'mixed', 'no_side']

/** Most place groups drawn; the rest share one "Other places" block (a real count). */
export const MAX_PLACE_GROUPS = 8

/** data_center_meeting_lean.dc_outcome → outcome group. */
export function outcomeFromDc(v: string | null | undefined): OutcomeKey | null {
  switch (v) {
    case 'approved':
      return 'approved'
    case 'denied':
      return 'denied'
    case 'tabled_or_deferred':
      return 'tabled'
    case 'moratorium':
      return 'moratorium'
    case 'discussed_no_action':
      return 'no_action'
    default:
      return null
  }
}

/** A decision's recorded outcome text ("Approved with conditions", "Deferred") → outcome group. */
export function outcomeFromText(v: string | null | undefined): OutcomeKey | null {
  const s = (v ?? '').toLowerCase()
  if (!s.trim()) return null
  if (/moratori/.test(s)) return 'moratorium'
  if (/\b(den(y|ied)|reject|fail|vot(ed|e) down)/.test(s)) return 'denied'
  if (/\b(tabl|defer|postpon|continu)/.test(s)) return 'tabled'
  if (/\b(approv|adopt|pass|grant|award)/.test(s)) return 'approved'
  return 'no_action'
}

/** data_center_meeting_lean.public_lean → public side. */
export function sideFromLean(v: string | null | undefined): SideKey | null {
  switch (v) {
    case 'mostly_opposed':
      return 'against'
    case 'mostly_supported':
      return 'for'
    case 'mixed':
      return 'mixed'
    case 'no_public_comment_on_data_center':
      return 'no_side'
    default:
      return null
  }
}

const pct1 = (n: number, d: number) => (d > 0 ? Math.round((1000 * n) / d) / 10 : 0)

/** The groupings these records support, in toggle order. `native` is offered when the chart has its own grouping. */
export function availableGroupings(records: MatrixRecord[], hasNative: boolean, placeGrain: 'state' | 'town'): GroupingKey[] {
  const has = (f: keyof DotFacets) => records.some((r) => r.facets?.[f] != null && r.facets[f] !== '')
  const out: GroupingKey[] = ['all']
  if (hasNative) out.push('native')
  if (has('year')) out.push('year')
  if (has(placeGrain)) out.push('place')
  if (has('outcome')) out.push('outcome')
  if (has('side')) out.push('side')
  return out
}

/**
 * Groups for one grouping. `native` takes its groups (and order and labels) from the chart's own grouping.
 * Years sort newest first; places by count (then name), with more than MAX_PLACE_GROUPS folded into "Other places";
 * outcomes and sides in a fixed order. The "not carried" group always comes last.
 */
export function groupRecords(
  records: MatrixRecord[],
  grouping: GroupingKey,
  opts: {
    placeGrain?: 'state' | 'town'
    native?: Array<{ key: string; label: string }>
    placeLabel?: (k: string) => string
    /** The side groups' words (#1200); the generic SIDE_LABELS by default. */
    sideLabels?: Record<SideKey, string>
  } = {},
): MatrixGroup[] {
  const total = records.length
  if (total === 0) return []
  if (grouping === 'all') return [{ key: 'all', label: 'All', count: total, pct: 100, members: records.map((_, i) => i) }]

  const buckets = new Map<string, number[]>()
  const keyOf = (r: MatrixRecord): string => {
    const f = r.facets ?? {}
    switch (grouping) {
      case 'native':
        return r.nativeKey ?? ''
      case 'year':
        return f.year ?? ''
      case 'place':
        return (opts.placeGrain === 'town' ? f.town : f.state) ?? ''
      case 'outcome':
        return f.outcome ?? ''
      case 'side':
        return f.side ?? ''
      default:
        return ''
    }
  }
  records.forEach((r, i) => {
    const k = keyOf(r)
    const list = buckets.get(k)
    if (list) list.push(i)
    else buckets.set(k, [i])
  })

  const missing: Record<string, string> = {
    year: 'Date not given',
    place: opts.placeGrain === 'town' ? 'Town not given' : 'State not given',
    outcome: 'Not screened',
    side: 'Not screened',
    native: 'Other',
  }
  const mk = (key: string, label: string, members: number[], tone?: MatrixGroup['tone']): MatrixGroup => ({
    key: key || 'none',
    label,
    count: members.length,
    pct: pct1(members.length, total),
    members,
    ...(tone ? { tone } : {}),
  })
  const known = [...buckets.entries()].filter(([k]) => k !== '')
  const none = buckets.get('')
  let groups: MatrixGroup[]
  switch (grouping) {
    case 'native': {
      const order = opts.native ?? []
      groups = order.filter((n) => buckets.has(n.key)).map((n) => mk(n.key, n.label, buckets.get(n.key)!))
      break
    }
    case 'year':
      groups = known.sort((a, b) => b[0].localeCompare(a[0])).map(([k, m]) => mk(k, k, m))
      break
    case 'place': {
      const sorted = known.sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0]))
      const label = opts.placeLabel ?? ((k: string) => k)
      const head = sorted.slice(0, MAX_PLACE_GROUPS).map(([k, m]) => mk(k, label(k), m))
      const rest = sorted.slice(MAX_PLACE_GROUPS).flatMap(([, m]) => m).sort((a, b) => a - b)
      groups = rest.length ? [...head, mk('other', `Other places (${sorted.length - MAX_PLACE_GROUPS})`, rest)] : head
      break
    }
    case 'outcome':
      groups = OUTCOME_ORDER.filter((k) => buckets.has(k)).map((k) => mk(k, OUTCOME_LABELS[k], buckets.get(k)!, k))
      break
    case 'side':
      groups = SIDE_ORDER.filter((k) => buckets.has(k)).map((k) => mk(k, (opts.sideLabels ?? SIDE_LABELS)[k], buckets.get(k)!, k))
      break
    default:
      groups = []
  }
  if (none && none.length) groups.push(mk('', missing[grouping] ?? 'Not given', none))
  return groups.filter((g) => g.count > 0)
}

/** "Approved · 12 (40.0%)": the block label. */
export function groupLabel(g: Pick<MatrixGroup, 'label' | 'count' | 'pct'>): string {
  return `${g.label} · ${g.count.toLocaleString('en-US')} (${g.pct.toFixed(1)}%)`
}

export interface SquareLayout {
  x: number
  y: number
  size: number
}

export interface MatrixLayout {
  width: number
  height: number
  squares: SquareLayout[]
  labels: Array<{ key: string; x: number; y: number; text: string; width: number; top: number; height: number }>
}

/**
 * Where each record's square sits for the given groups: one grid for "All", otherwise one labelled block per group (two
 * columns from 520px). The square at index i always belongs to record i, so squares keep their identity across groupings.
 */
export function layoutMatrix(n: number, groups: MatrixGroup[], width: number, grouping: GroupingKey): MatrixLayout {
  const w = Math.max(260, width)
  const gap = w < 440 ? 3 : 4
  const squares: SquareLayout[] = new Array(n)
  const labels: MatrixLayout['labels'] = []
  if (grouping === 'all' || groups.length <= 1) {
    const cols = n > 300 ? (w >= 520 ? 34 : w >= 380 ? 28 : 24) : n > 120 ? (w >= 520 ? 26 : 20) : w >= 520 ? 20 : 16
    const sq = Math.min(22, (w - (cols - 1) * gap) / cols)
    const step = sq + gap
    const members = groups[0]?.members ?? Array.from({ length: n }, (_, i) => i)
    members.forEach((idx, j) => {
      squares[idx] = { x: (j % cols) * step, y: Math.floor(j / cols) * step, size: sq }
    })
    const rows = Math.ceil(members.length / cols)
    return { width: w, height: Math.max(sq, rows * step - gap), squares, labels }
  }
  const twoCol = w >= 520
  const colGap = 24
  const blockW = twoCol ? (w - colGap) / 2 : w
  const baseCols = n > 300 ? 34 : n > 120 ? 26 : 20
  const step0 = Math.min(22, (w - (baseCols - 1) * gap) / baseCols) + gap
  const blockCols = Math.max(8, Math.floor((blockW + gap) / step0))
  const bSq = (blockW - (blockCols - 1) * gap) / blockCols
  const bStep = bSq + gap
  let rowY = 0
  const stride = twoCol ? 2 : 1
  for (let r = 0; r < groups.length; r += stride) {
    let maxH = 0
    groups.slice(r, r + stride).forEach((g, col) => {
      const baseX = col * (blockW + colGap)
      const top = rowY + 22
      g.members.forEach((idx, j) => {
        squares[idx] = { x: baseX + (j % blockCols) * bStep, y: top + Math.floor(j / blockCols) * bStep, size: bSq }
      })
      const h = Math.ceil(g.count / blockCols) * bStep - gap
      maxH = Math.max(maxH, h)
      labels.push({ key: g.key, x: baseX, y: rowY + 13, text: groupLabel(g), width: blockW, top, height: h })
    })
    rowY += 22 + maxH + 22
  }
  for (let i = 0; i < n; i++) if (!squares[i]) squares[i] = { x: 0, y: 0, size: 0 }
  return { width: w, height: Math.max(40, rowY - 14), squares, labels }
}
