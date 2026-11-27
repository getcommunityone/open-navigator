import { useMemo, useState } from 'react'
import type { AreaConcernsResponse } from '../../api/dataCenters'
import type { LoadState } from '../../utils/dataStory'
import { buildConcernRows, sortConcernRows, MIN_PLACE_MENTIONS, type ConcernSort } from '../../utils/concernDumbbell'
import { pctLabel, ppLabel } from '../../utils/storyTimeline'
import { DataTable } from '../matrix/SectionShell'
import DumbbellRows, { type DumbbellRow } from './DumbbellRows'
import './storyCharts.css'

const fmt = (n: number) => n.toLocaleString('en-US')
const mentions = (n: number) => `${fmt(n)} ${n === 1 ? 'mention' : 'mentions'}`
const andList = (xs: string[]) => (xs.length <= 1 ? xs.join('') : `${xs.slice(0, -1).join(', ')} and ${xs[xs.length - 1]}`)

interface Props {
  data: AreaConcernsResponse | null | undefined
  status: LoadState
  /** The scope's label ("Texas", "Tuscaloosa, Alabama"), or null nationally. */
  place: string | null
  idBase: string
}

/**
 * The Concerns screen (#1209), drawn like the vizjb12 dumbbell: each concern's share of the place's mentions (filled dot)
 * against its share of the nation's (hollow dot), the difference in points on the right. Nationally the mart has no
 * per-concern objection count to compare with, so each concern is one dot: its share of all mentions.
 */
export default function ConcernsDumbbell({ data, status, place, idBase }: Props) {
  const built = useMemo(() => buildConcernRows(data, place), [data, place])
  const [sortBy, setSortBy] = useState<ConcernSort>('place')
  const [tableOpen, setTableOpen] = useState(false)
  const sorted = useMemo(() => sortConcernRows(built.rows, sortBy), [built.rows, sortBy])
  const compare = built.mode === 'compare'
  const where = place ?? 'meeting records nationally'
  const title = compare ? `What ${place} raises about data centers, compared with the nation` : `What ${place ?? 'meeting records'} raise${place ? 's' : ''} about data centers, by share of mentions`

  if (status === 'loading' && !data) {
    return (
      <div className="sc-block">
        <p className="sc-h">{title}</p>
        <p className="sc-note" role="status">
          Loading the concerns…
        </p>
      </div>
    )
  }
  if (status === 'error' && !data) {
    return (
      <div className="sc-block">
        <p className="sc-h">{title}</p>
        <p className="sc-note">The concerns could not be loaded right now.</p>
      </div>
    )
  }
  if (built.placeTotal <= 0) {
    return (
      <div className="sc-block">
        <p className="sc-h">{title}</p>
        <p className="sc-note">No concerns are on record in {where} yet.</p>
      </div>
    )
  }

  const drawn: DumbbellRow[] = sorted.map((r) => {
    if (r.national == null) {
      return {
        key: r.key,
        label: r.label,
        a: null,
        b: r.place,
        right: pctLabel(r.place),
        ariaLabel: `${r.label}: ${pctLabel(r.place)} of mentions (${mentions(r.placeMentions)} of ${fmt(built.placeTotal)})`,
        tip: { cat: r.label, val: pctLabel(r.place), sub: `${mentions(r.placeMentions)} of ${fmt(built.placeTotal)}` },
      }
    }
    const pp = ppLabel(r.national, r.place)
    return {
      key: r.key,
      label: r.label,
      a: r.national,
      b: r.place,
      right: pp,
      negative: r.place < r.national,
      ariaLabel: `${r.label}: ${place} ${pctLabel(r.place)} of mentions (${mentions(r.placeMentions)} of ${fmt(built.placeTotal)}), nationally ${pctLabel(r.national)} (${fmt(r.nationalMentions)} of ${fmt(built.nationalTotal)}), difference ${pp.replace('pp', 'percentage points')}`,
      tip: {
        cat: r.label,
        val: `${pctLabel(r.national)} → ${pctLabel(r.place)}`,
        sub: `${mentions(r.placeMentions)} of ${fmt(built.placeTotal)} in ${place}; ${fmt(r.nationalMentions)} of ${fmt(built.nationalTotal)} nationally (${pp})`,
      },
    }
  })
  const n = built.hidden.length

  return (
    <div className="sc-block">
      <p className="sc-h">{title}</p>
      {compare && built.rows.length > 1 && (
        <div className="sc-controls">
          <div className="folio-seg" role="group" aria-label="Sort the concerns">
            {(
              [
                ['place', `By ${place}`],
                ['difference', 'By difference'],
                ['national', 'Nationally'],
              ] as Array<[ConcernSort, string]>
            ).map(([k, label]) => (
              <button key={k} type="button" aria-pressed={sortBy === k} onClick={() => setSortBy(k)}>
                {label}
              </button>
            ))}
          </div>
        </div>
      )}
      {drawn.length > 0 ? (
        <DumbbellRows
          rows={drawn}
          aName={compare ? 'Nationally' : undefined}
          bName={compare ? String(place) : 'Share of mentions'}
          ariaLabel={compare ? `Dumbbell chart, concerns in ${place} against the nation` : `Dot chart, concerns by share of mentions, ${where}`}
          unitPlural="concerns"
        />
      ) : (
        <p className="sc-note">No concern has {MIN_PLACE_MENTIONS} or more mentions in {where} yet.</p>
      )}
      <p className="sc-note" data-testid="concerns-dumbbell-key">
        {compare
          ? `Filled dot: the concern's share of the ${fmt(built.placeTotal)} concern mentions in ${place}. Hollow dot: its share of the ${fmt(built.nationalTotal)} nationally. The right column is the difference in percentage points.`
          : `Each dot is the concern's share of all ${fmt(built.placeTotal)} concern mentions${place ? ` in ${place}` : ''}. The records count objections in total, not by concern, so there is no second value to compare with here.`}
      </p>
      {n > 0 && (
        <p className="sc-note">
          Concerns with fewer than {MIN_PLACE_MENTIONS} mentions {place ? `in ${place}` : 'nationally'} are left out ({fmt(n)}: {andList(built.hidden)}).
        </p>
      )}
      <button type="button" className="folio-btn" aria-expanded={tableOpen} aria-controls={`${idBase}-concerns-table`} onClick={() => setTableOpen((o) => !o)}>
        {tableOpen ? 'Hide data table' : 'Show data table'} {tableOpen ? '↑' : '↓'}
      </button>
      {tableOpen && (
        <DataTable
          id={`${idBase}-concerns-table`}
          caption={`Data table: ${title}`}
          spec={
            compare
              ? {
                  columns: [
                    { label: 'Concern' },
                    { label: `${place} (%)`, numeric: true },
                    { label: 'Nationally (%)', numeric: true },
                    { label: 'Difference (pp)', numeric: true },
                    { label: `Mentions ${place} / nationally`, numeric: true },
                  ],
                  rows: sorted.map((r) => [r.label, pctLabel(r.place), pctLabel(r.national ?? 0), ppLabel(r.national ?? 0, r.place), `${fmt(r.placeMentions)} / ${fmt(r.nationalMentions)}`]),
                }
              : {
                  columns: [{ label: 'Concern' }, { label: 'Share of mentions (%)', numeric: true }, { label: 'Mentions', numeric: true }],
                  rows: sorted.map((r) => [r.label, pctLabel(r.place), fmt(r.placeMentions)]),
                }
          }
        />
      )}
    </div>
  )
}
