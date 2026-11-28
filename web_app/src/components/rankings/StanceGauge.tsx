import { useMemo } from 'react'
import type { RankingPlace } from '../../api/rankings'
import { assignLanes, gaugeX, placeAria, summarize, takeaway } from '../../utils/rankings'

interface Props {
  topicName: string
  places: RankingPlace[]
  /** Names the median in the legend; "National median" when no filter narrows the places. */
  medianLabel?: string
  selectedId?: string | number | null
  onSelect?: (p: RankingPlace) => void
  headingLevel?: 'h2' | 'h3'
}

const LANE_PX = 13
const HIT = 24

/**
 * One horizontal gauge per topic (#1438): "All against" on the left, "All for" on the right. Ranked places are solid dots
 * (shrunk share), places with too few speakers are hollow and lighter (raw share). The median of ranked places is a tick.
 * Counts in the title come from the places drawn, so the title always matches the filter.
 */
export default function StanceGauge({ topicName, places, medianLabel = 'National median', selectedId, onSelect, headingLevel = 'h3' }: Props) {
  const Heading = headingLevel
  const s = useMemo(() => summarize(places), [places])
  const placed = useMemo(() => {
    // Unranked first so ranked dots sit on top.
    const ordered = [...places].sort((a, b) => Number(a.is_ranked) - Number(b.is_ranked))
    const xs = ordered.map(gaugeX)
    const lanes = assignLanes(xs)
    return ordered.map((p, i) => ({ p, x: xs[i], lane: lanes[i] }))
  }, [places])
  const laneCount = placed.reduce((m, d) => Math.max(m, d.lane + 1), 1)
  const height = laneCount * LANE_PX + HIT
  const medianX = s.medianShrunk == null ? null : Math.min(1, Math.max(0, 1 - s.medianShrunk))
  const hasOfficials = places.some((p) => p.officials_side != null)
  const title = takeaway(topicName, s.ranked, s.against, s.for)

  return (
    <figure className="m-0 w-full min-w-0" data-testid="stance-gauge" aria-label={title}>
      <Heading className="mb-2 text-base font-semibold leading-snug text-gray-900 sm:text-lg">{title}</Heading>
      <div className="relative w-full" style={{ height: height + 22 }} data-testid="gauge-track">
        <div className="absolute left-0 right-0 top-0 rounded bg-gray-100" style={{ height, margin: '0 12px' }} aria-hidden />
        <div className="absolute" style={{ left: 12, right: 12, top: 0, height }}>
          <div className="absolute left-1/2 top-0 h-full border-l border-dashed border-gray-300" aria-hidden />
          {medianX != null && (
            <div
              className="absolute top-0 h-full"
              style={{ left: `${medianX * 100}%` }}
              data-testid="median-marker"
              role="img"
              aria-label={`${medianLabel}: ${Math.round((1 - medianX) * 100)}% against`}
            >
              <div className="h-full w-0.5 -translate-x-1/2 bg-gray-900" />
            </div>
          )}
          {placed.map(({ p, x, lane }) => {
            const sel = selectedId != null && String(selectedId) === String(p.jurisdiction_id)
            return (
              <button
                key={String(p.jurisdiction_id)}
                type="button"
                data-testid={p.is_ranked ? 'dot-ranked' : 'dot-unranked'}
                data-x={x.toFixed(3)}
                aria-label={placeAria(p)}
                aria-pressed={sel}
                onClick={() => onSelect?.(p)}
                className="absolute flex items-center justify-center rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-600"
                style={{ left: `${x * 100}%`, top: lane * LANE_PX + 2, width: HIT, height: HIT, transform: 'translateX(-50%)' }}
              >
                <span
                  className={`block rounded-full ${p.is_ranked ? 'border-2 border-teal-800 bg-teal-700' : 'border border-gray-500 bg-white opacity-70'} ${sel ? 'ring-2 ring-gray-900' : ''}`}
                  style={{ width: p.is_ranked ? 12 : 10, height: p.is_ranked ? 12 : 10 }}
                />
                {p.officials_side != null && (
                  <span className="absolute -right-0.5 -top-0.5 block h-2 w-2 rotate-45 border border-white bg-amber-600" data-testid="officials-badge" aria-hidden />
                )}
              </button>
            )
          })}
        </div>
        <div className="absolute bottom-0 left-0 right-0 flex justify-between text-xs font-medium text-gray-600" style={{ padding: '0 4px' }}>
          <span>All against</span>
          <span>All for</span>
        </div>
      </div>
      <ul className="mt-2 flex flex-wrap gap-x-4 gap-y-1 p-0 text-xs text-gray-700" style={{ listStyle: 'none' }} aria-label="Legend">
        <li className="flex items-center gap-1.5"><span className="inline-block h-3 w-3 rounded-full border-2 border-teal-800 bg-teal-700" aria-hidden />Ranked place</li>
        <li className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full border border-gray-500 bg-white opacity-70" aria-hidden />Too few speakers to rank</li>
        <li className="flex items-center gap-1.5"><span className="inline-block h-3.5 w-0.5 bg-gray-900" aria-hidden />{medianLabel} (ranked places)</li>
        {hasOfficials && (
          <li className="flex items-center gap-1.5"><span className="inline-block h-2 w-2 rotate-45 bg-amber-600" aria-hidden />Officials' side known (shown in the place panel)</li>
        )}
      </ul>
    </figure>
  )
}
