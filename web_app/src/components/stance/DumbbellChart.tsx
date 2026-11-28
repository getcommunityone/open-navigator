import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fetchPeriodCompare, type PeriodCompareResponse } from '../../api/topicTimeline'
import { pctLabel, ppLabel, sortDumbbell, type DumbbellSort } from '../../utils/storyTimeline'
import { DataTable } from '../matrix/SectionShell'
import DumbbellRows, { type DumbbellRow } from './DumbbellRows'
import './storyCharts.css'

const fmt = (n: number) => n.toLocaleString('en-US')
/** Rows drawn before "Show all". */
const FIRST_ROWS = 12

interface Props {
  topic: string
  stateCode?: string
  scopeLabel: string
  subject: string
  idBase: string
}

/**
 * Period dumbbell (#1140, the reference's §4.3): the topic's share of recorded meetings last year (hollow circle) and
 * this year (filled dot) for each state, or each town at state scope, with a ±pp change label. Sort by the later year,
 * by change or by the earlier year; rows slide to their new place (no motion with prefers-reduced-motion).
 */
export default function DumbbellChart({ topic, stateCode, scopeLabel, subject, idBase }: Props) {
  const q = useQuery<PeriodCompareResponse>({
    queryKey: ['topic-period-compare', topic, stateCode ?? 'national'],
    queryFn: () => fetchPeriodCompare(topic, stateCode),
    staleTime: 5 * 60_000,
    retry: 1,
  })
  const [sortBy, setSortBy] = useState<DumbbellSort>('later')
  const [tableOpen, setTableOpen] = useState(false)
  const rows = useMemo(() => q.data?.rows ?? [], [q.data])
  const sorted = useMemo(() => sortDumbbell(rows, sortBy), [rows, sortBy])

  // The section never disappears silently (#1192): loading, a failed request and a scope with nothing to compare each say so.
  const heading = (years: string) => (
    <p className="sc-h">
      Share of recorded meetings that discussed {subject}, {years} · {scopeLabel}
    </p>
  )
  if (q.isLoading) {
    return (
      <div className="sc-block">
        {heading('last year and this year')}
        <p className="sc-note" role="status">
          Loading the comparison…
        </p>
      </div>
    )
  }
  if (q.isError || !q.data) {
    return (
      <div className="sc-block">
        {heading('last year and this year')}
        <p className="sc-note">The year-over-year comparison could not be loaded right now.</p>
      </div>
    )
  }
  const d = q.data
  if (rows.length === 0 && d.hidden_rows === 0) {
    // No per-year counts of recorded meetings for the scope (recorded_meeting_year not loaded, #1194), or no meetings on
    // the topic in either year: there is no share to compare, and the chart says so instead of drawing nothing.
    return (
      <div className="sc-block">
        {heading(`${d.from_year} and ${d.to_year}`)}
        <p className="sc-note">
          No comparison to draw for {scopeLabel} yet: either no meetings on the topic are on record for {d.from_year} or{' '}
          {d.to_year}, or the yearly counts of recorded meetings per {d.grain === 'state' ? 'state' : 'town'} have not been loaded.
        </p>
      </div>
    )
  }
  if (rows.length === 0) {
    // Nothing clears the thresholds (often at state scope, where towns record few meetings a year): say so, never a blank.
    return d.hidden_rows > 0 ? (
      <div className="sc-block">
        <p className="sc-h">
          Share of recorded meetings that discussed {subject}, {d.from_year} and {d.to_year} · {scopeLabel}
        </p>
        <p className="sc-note">
          No {d.grain === 'state' ? 'state' : 'town'} here can be compared yet: {fmt(d.hidden_rows)}{' '}
          {d.grain === 'state' ? (d.hidden_rows === 1 ? 'state has' : 'states have') : d.hidden_rows === 1 ? 'town has' : 'towns have'} meetings on
          the topic, but none has at least {d.min_recorded_meetings} recorded meetings in both years and {d.min_topic_meetings} meetings on the
          topic across them.{d.grain === 'place' ? ' The national view compares states.' : ''}
        </p>
      </div>
    ) : null
  }
  const { from_year: y0, to_year: y1 } = d
  const place = d.grain === 'state' ? 'state' : 'town'
  const drawn: DumbbellRow[] = sorted.map((r) => {
    const pp = ppLabel(r.earlier_share, r.later_share)
    return {
      key: r.key,
      label: r.label,
      a: r.earlier_share,
      b: r.later_share,
      right: pp,
      negative: r.later_share < r.earlier_share,
      ariaLabel: `${r.label}: ${y0} ${pctLabel(r.earlier_share)} (${fmt(r.earlier_meetings)} of ${fmt(r.earlier_recorded)} meetings), ${y1} ${pctLabel(r.later_share)} (${fmt(r.later_meetings)} of ${fmt(r.later_recorded)}), change ${pp.replace('pp', 'percentage points')}`,
      tip: {
        cat: r.label,
        val: `${pctLabel(r.earlier_share)} → ${pctLabel(r.later_share)}`,
        sub: `${fmt(r.earlier_meetings)} of ${fmt(r.earlier_recorded)} in ${y0}; ${fmt(r.later_meetings)} of ${fmt(r.later_recorded)} in ${y1} (${pp})`,
      },
    }
  })

  return (
    <div className="sc-block">
      <div className="sc-controls">
        <div className="folio-seg sc-chips" role="group" aria-label="Sort the rows">
          {(
            [
              ['later', `By ${y1}`],
              ['change', 'By change'],
              ['earlier', `By ${y0}`],
            ] as Array<[DumbbellSort, string]>
          ).map(([k, label]) => (
            <button key={k} type="button" aria-pressed={sortBy === k} onClick={() => setSortBy(k)}>
              {label}
            </button>
          ))}
        </div>
      </div>
      <DumbbellRows
        title={`Share of recorded meetings that discussed ${subject}, ${y0} and ${y1}, by ${place} · ${scopeLabel}`}
        key={stateCode ?? 'national'}
        rows={drawn}
        aName={String(y0)}
        bName={String(y1)}
        ariaLabel={`Dumbbell chart, ${y0} against ${y1}, ${scopeLabel}`}
        firstRows={FIRST_ROWS}
        unitPlural={place === 'state' ? 'states' : 'towns'}
      />
      <p className="sc-note">
        Each row divides meetings that discussed {subject} by every recorded meeting in that {place} and year. {y1} is the
        year so far. Rows with fewer than {d.min_recorded_meetings} recorded meetings in either year, or fewer than{' '}
        {d.min_topic_meetings} meetings on the topic across both, are left out
        {d.hidden_rows > 0 ? ` (${fmt(d.hidden_rows)} ${d.hidden_rows === 1 ? place : `${place === 'state' ? 'states' : 'towns'}`})` : ''}.
      </p>
      <button type="button" className="folio-btn" aria-expanded={tableOpen} aria-controls={`${idBase}-db-table`} onClick={() => setTableOpen((o) => !o)}>
        {tableOpen ? 'Hide data table' : 'Show data table'} {tableOpen ? '↑' : '↓'}
      </button>
      {tableOpen && (
        <DataTable
          id={`${idBase}-db-table`}
          caption={`Data table: share of recorded meetings that discussed ${subject}, ${y0} and ${y1}, ${scopeLabel}`}
          spec={{
            columns: [
              { label: place === 'state' ? 'State' : 'Town' },
              { label: `${y0} (%)`, numeric: true },
              { label: `${y1} (%)`, numeric: true },
              { label: 'Change (pp)', numeric: true },
              { label: `Meetings ${y0} / ${y1}`, numeric: true },
            ],
            rows: sorted.map((r) => [
              r.label,
              pctLabel(r.earlier_share),
              pctLabel(r.later_share),
              ppLabel(r.earlier_share, r.later_share),
              `${fmt(r.earlier_meetings)} of ${fmt(r.earlier_recorded)} / ${fmt(r.later_meetings)} of ${fmt(r.later_recorded)}`,
            ]),
          }}
        />
      )}
    </div>
  )
}
