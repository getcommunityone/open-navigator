/**
 * useNationalStats — the national `GET /api/stats` rollup (no location), shared by Home, Analytics and the Explore
 * cards. The query key matches the one Home and Analytics already used, so they share one request and one cache entry.
 * `data` is undefined while loading and when the request fails; callers show "—" or no figure then.
 */
import { useQuery } from '@tanstack/react-query'

import api from '../lib/api'
import type { NationalStats } from '../utils/liveStats'

const THIRTY_MINUTES_MS = 30 * 60 * 1000

export function useNationalStats() {
  return useQuery<NationalStats | null>({
    queryKey: ['national-stats'],
    queryFn: async () => {
      const response = await api.get('/stats')
      return response.data
    },
    staleTime: THIRTY_MINUTES_MS, // Catalog totals barely move.
  })
}
