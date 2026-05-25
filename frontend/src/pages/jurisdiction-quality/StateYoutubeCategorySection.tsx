import { useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { STATE_CODE_TO_NAME } from '../../utils/stateMapping'

export type StateYoutubeCategoryKey = 'overall' | 'public_health' | 'education' | 'transportation'

export const STATE_YOUTUBE_CATEGORY_LABELS: Record<StateYoutubeCategoryKey, string> = {
  overall: 'Overall',
  public_health: 'Public health',
  education: 'Education',
  transportation: 'Transportation',
}

export type StateYoutubeCategoryRow = {
  state_code: string
  state_name: string
  category: string
  mapped: boolean
  youtube_channel_url?: string | null
  channel_id?: string | null
  channel_title?: string | null
  channel_type?: string | null
  discovery_method?: string | null
  match_score?: number | null
  confidence_score?: number | null
}

export type StateYoutubeCategoryRollup = {
  categories: string[]
  by_category: Record<string, StateYoutubeCategoryRow[]>
  summary?: Record<
    string,
    {
      total_states: number
      mapped: number
      missing: number
      pct_mapped: number | null
    }
  >
  explained?: {
    source_table?: string | null
    categories?: Record<string, string>
    classification?: string
  }
}

type EnrichedStateYoutubeCategoryRow = StateYoutubeCategoryRow & {
  name: string
  pct: number
  missing: number
}

function fmt(n: number): string {
  return n.toLocaleString('en-US')
}

function enrichStateYoutubeCategoryRows(
  rows: StateYoutubeCategoryRow[] | undefined,
): EnrichedStateYoutubeCategoryRow[] {
  return (rows ?? []).map((r) => ({
    ...r,
    name: r.state_name ?? STATE_CODE_TO_NAME[r.state_code] ?? r.state_code,
    pct: r.mapped ? 100 : 0,
    missing: r.mapped ? 0 : 1,
  }))
}

export default function StateYoutubeCategorySection({ rollup }: { rollup: StateYoutubeCategoryRollup }) {
  const categories = (rollup.categories ?? []).filter(
    (c): c is StateYoutubeCategoryKey => c in STATE_YOUTUBE_CATEGORY_LABELS,
  )
  const defaultCategory = categories.includes('overall') ? 'overall' : categories[0] ?? 'overall'
  const [category, setCategory] = useState<StateYoutubeCategoryKey>(defaultCategory)
  const [view, setView] = useState<'worst' | 'best' | 'all'>('worst')
  const [search, setSearch] = useState('')
  const [sortCol, setSortCol] = useState<'pct' | 'missing' | 'state_code'>('missing')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')

  const rows = rollup.by_category?.[category] ?? []
  const enriched = useMemo(() => enrichStateYoutubeCategoryRows(rows), [rows])
  const summary = rollup.summary?.[category]

  const filtered = useMemo(() => {
    let out = [...enriched]
    const q = search.trim().toLowerCase()
    if (q) out = out.filter((r) => r.name.toLowerCase().includes(q) || r.state_code.toLowerCase().includes(q))
    out.sort((a, b) => {
      let c = 0
      if (sortCol === 'state_code') c = a.state_code.localeCompare(b.state_code)
      else c = Number(a[sortCol]) - Number(b[sortCol])
      return sortDir === 'asc' ? c : -c
    })
    if (!q && view === 'worst') return out.filter((r) => !r.mapped).slice(0, 15)
    if (!q && view === 'best') return out.filter((r) => r.mapped).slice(0, 15)
    return out
  }, [enriched, search, sortCol, sortDir, view])

  const chartData = useMemo(() => {
    if (view === 'best') return [...enriched].filter((r) => r.mapped).slice(0, 20)
    return [...enriched].filter((r) => !r.mapped).slice(0, 20)
  }, [enriched, view])

  const toggleSort = (col: 'pct' | 'missing' | 'state_code') => {
    if (sortCol === col) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortCol(col)
      setSortDir(col === 'missing' ? 'desc' : 'asc')
    }
  }

  if (categories.length === 0) {
    return (
      <div className="jmq-placeholder">
        <strong>No state YouTube category rollup in JSON</strong>
        Re-run <code>export_jurisdiction_mapping_quality_json.py</code> after building{' '}
        <code>int_events_channels_registry</code>.
      </div>
    )
  }

  return (
    <div id="jmq-state-youtube-by-category" className="scroll-mt-24 space-y-4">
      <div className="jmq-card">
        <div className="jmq-card-title">
          YouTube URL mapping by state · {STATE_YOUTUBE_CATEGORY_LABELS[category]}
        </div>
        <p className="jmq-card-sub">
          Keyword match on channel title/description from{' '}
          <code>{rollup.explained?.source_table ?? 'int_events_channels_registry'}</code>. Local county/city
          meeting channels are excluded from agency categories.
        </p>
      </div>

      <div className="jmq-pill-row flex-wrap">
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            className={`jmq-pill text-xs ${category === cat ? 'jmq-pill--active' : ''}`}
            onClick={() => {
              setCategory(cat)
              setView('worst')
              setSearch('')
            }}
          >
            {STATE_YOUTUBE_CATEGORY_LABELS[cat]}
            {rollup.summary?.[cat] ? ` (${rollup.summary[cat].mapped}/${rollup.summary[cat].total_states})` : ''}
          </button>
        ))}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[
          { label: 'States', val: fmt(summary?.total_states ?? enriched.length) },
          { label: 'Mapped', val: fmt(summary?.mapped ?? enriched.filter((r) => r.mapped).length) },
          { label: 'Coverage', val: `${(summary?.pct_mapped ?? 0).toFixed(1)}%` },
          { label: 'Missing', val: fmt(summary?.missing ?? enriched.filter((r) => !r.mapped).length) },
        ].map((k) => (
          <div key={k.label} className="rounded-lg border border-[var(--jmq-border)] bg-[var(--jmq-surface2)] px-3 py-2">
            <div className="font-mono text-[10px] font-semibold uppercase tracking-wide text-[var(--jmq-text-muted)]">
              {k.label}
            </div>
            <div className="mt-1 font-mono text-sm font-bold text-[var(--jmq-text)]">{k.val}</div>
          </div>
        ))}
      </div>

      <div className="jmq-pill-row mb-3">
        {(
          [
            ['worst', '15 Missing'],
            ['best', '15 Mapped'],
            ['all', 'All states'],
          ] as const
        ).map(([id, lbl]) => (
          <button
            key={id}
            type="button"
            className={`jmq-pill text-xs ${view === id && !search ? 'jmq-pill--active' : ''}`}
            onClick={() => {
              setView(id)
              setSearch('')
              setSortCol('missing')
              setSortDir('desc')
            }}
          >
            {lbl}
          </button>
        ))}
        <input
          type="search"
          placeholder="Search state…"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value)
            setView('all')
          }}
          className="ml-auto w-44 rounded-md border border-[var(--jmq-border)] bg-[var(--jmq-surface)] px-2 py-1.5 text-xs text-[var(--jmq-text)]"
        />
      </div>

      <div className="jmq-card mb-4">
        <div className="jmq-card-title">
          {view === 'best' ? 'States with mapped channel' : 'States missing channel'} ·{' '}
          {STATE_YOUTUBE_CATEGORY_LABELS[category]}
        </div>
        <div className="h-56 w-full sm:h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} layout="horizontal" margin={{ top: 8, right: 12, bottom: 48, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--jmq-border)" />
              <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 9 }} />
              <YAxis type="category" dataKey="state_code" width={36} tick={{ fontSize: 9 }} />
              <Tooltip
                formatter={(_v: number, _n, p) => {
                  const row = (p as { payload?: EnrichedStateYoutubeCategoryRow }).payload
                  if (!row) return ['', 'Mapped']
                  return [
                    row.mapped ? 'Mapped' : 'Missing',
                    row.channel_title ?? STATE_YOUTUBE_CATEGORY_LABELS[category],
                  ]
                }}
              />
              <Bar dataKey="pct" radius={[0, 3, 3, 0]}>
                {chartData.map((d, i) => (
                  <Cell key={i} fill={d.mapped ? 'var(--jmq-teal)' : '#a40e26'} fillOpacity={0.85} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="jmq-card overflow-x-auto">
        <table className="jmq-table w-full min-w-[640px] text-left text-xs">
          <thead>
            <tr>
              <th>
                <button type="button" className="jmq-sort-btn" onClick={() => toggleSort('state_code')}>
                  State
                </button>
              </th>
              <th>Mapped</th>
              <th>Channel</th>
              <th>URL</th>
              <th>
                <button type="button" className="jmq-sort-btn" onClick={() => toggleSort('pct')}>
                  Score
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.state_code}>
                <td className="font-mono font-semibold">
                  {r.name} ({r.state_code})
                </td>
                <td>{r.mapped ? 'Yes' : 'No'}</td>
                <td className="max-w-[220px] truncate" title={r.channel_title ?? undefined}>
                  {r.channel_title ?? '—'}
                </td>
                <td>
                  {r.youtube_channel_url ? (
                    <a
                      href={r.youtube_channel_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[var(--jmq-teal)] underline-offset-2 hover:underline"
                    >
                      Open
                    </a>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="font-mono">{r.match_score != null ? r.match_score.toFixed(2) : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
