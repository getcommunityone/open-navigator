import { useEffect, useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { STATES_ALBERS_TOPO, fetchTopo, toFeats } from '../../lib/dotMatrix'
import { STATE_FIPS_TO_CODE } from '../../utils/stateFips'
import './MapSkeleton.css'

/** The national maps' box (the us-atlas Albers frame, 975 × 610). */
export const NATIONAL_MAP_ASPECT = 975 / 610

/**
 * A state's map box (width over height) from the national state shapes (the same cached query the national maps use), so a
 * state map's skeleton has the state's own shape box; about square until the shapes are known.
 */
export function useStateAspect(stateCode: string | null | undefined): number {
  const { data: topo } = useQuery({
    queryKey: ['us-atlas-states-albers'],
    queryFn: () => fetchTopo(STATES_ALBERS_TOPO),
    enabled: Boolean(stateCode),
    staleTime: 1000 * 60 * 60,
  })
  return useMemo(() => {
    if (!topo || !stateCode) return 1
    const f = toFeats(topo, 'states').find((x) => STATE_FIPS_TO_CODE[x.id] === stateCode)
    if (!f) return 1
    const w = f.bbox[2] - f.bbox[0]
    const h = f.bbox[3] - f.bbox[1]
    return h > 0 ? Math.min(3, Math.max(0.5, w / h)) : 1
  }, [topo, stateCode])
}

interface Props {
  /** Width over height of the map that will replace it, so nothing around it moves when it arrives. */
  aspect: number
  /** What a screen reader hears while it loads. */
  label?: string
  /** After this long, a calm "taking longer" line with Try again. */
  slowAfterMs?: number
  /** The load failed: the calm message and Try again at once. */
  error?: boolean
  /** Try again; by default every query on the page that is showing refetches. */
  onRetry?: () => void
}

/**
 * The box a story or home map holds while its shapes and counts load (#1328): its final size, a soft shimmer, and nothing
 * else: no numbers, caption, legend or card until the data they describe has arrived. A slow (8 s) or failed load says so
 * calmly with Try again, never a broken map.
 */
export default function MapSkeleton({ aspect, label = 'Loading the map', slowAfterMs = 8000, error = false, onRetry }: Props) {
  const qc = useQueryClient()
  const [slow, setSlow] = useState(false)
  useEffect(() => {
    if (error) return
    const t = setTimeout(() => setSlow(true), slowAfterMs)
    return () => clearTimeout(t)
  }, [error, slowAfterMs])
  const retry = () => {
    setSlow(false)
    if (onRetry) onRetry()
    else void qc.refetchQueries({ type: 'active' })
  }
  const stuck = error || slow
  return (
    <div className={`map-skeleton${stuck ? ' is-stuck' : ''}`} style={{ aspectRatio: String(aspect) }} role="status" aria-live="polite">
      {stuck ? (
        <div className="map-skeleton-msg">
          <p>{error ? 'The map could not be loaded right now.' : 'The map is taking longer than usual.'}</p>
          <button type="button" className="map-skeleton-retry" onClick={retry}>
            Try again
          </button>
        </div>
      ) : (
        <span className="sr-only">{label}…</span>
      )}
    </div>
  )
}
