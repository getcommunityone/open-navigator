/**
 * useCpiAnnual — react-query wrapper around ``GET /api/cpi/annual``.
 *
 * Returns the annual-average CPI index map keyed by year-as-string plus the
 * latest year for which a stable annual index is available — exactly the
 * shape ``deflate(value, fromYear, toYear, byYear)`` consumes.
 *
 * Stale time is 6h because the underlying view is rebuilt on the BLS
 * monthly schedule; refetching more often is wasted work.
 */
import { useQuery } from '@tanstack/react-query'

import api from '../lib/api'
import type { CpiByYear } from '../utils/inflation'

export interface CpiAnnualPayload {
  series_id: string
  latest_year: number | null
  by_year: CpiByYear
  from_official_annual: Record<string, boolean>
}

const SIX_HOURS_MS = 6 * 60 * 60 * 1000

export function useCpiAnnual(seriesId: string = 'CUUR0000SA0') {
  return useQuery({
    queryKey: ['cpi-annual', seriesId],
    queryFn: async (): Promise<CpiAnnualPayload> => {
      const r = await api.get<CpiAnnualPayload>('/cpi/annual', {
        params: { series_id: seriesId },
      })
      return r.data
    },
    staleTime: SIX_HOURS_MS,
    // Don't retry forever on a broken backend — the page must still render
    // (Nominal mode works without CPI), so we degrade silently to nominal.
    retry: 1,
  })
}
