import { useQuery } from '@tanstack/react-query'
import api from '../../lib/api'
import { withSpan } from '../../instrumentation'
import type { JurisdictionBodies } from '../../lib/governingBodies'
import { OfficialsHeard, WhoGoverns } from './WhoGoverns'

/** Loads GET /api/jurisdictions/{id}/bodies for the place page and renders both sections (#1446). */
export default function PlaceGovernance({ jurisdictionId }: { jurisdictionId: string }) {
  const { data, isLoading, isError } = useQuery<JurisdictionBodies>({
    queryKey: ['jurisdiction-bodies', jurisdictionId],
    queryFn: () =>
      withSpan(
        'jurisdiction_bodies.load',
        async () => (await api.get<JurisdictionBodies>(`/jurisdictions/${encodeURIComponent(jurisdictionId)}/bodies`)).data,
        { 'jurisdiction.id': jurisdictionId },
      ),
    enabled: Boolean(jurisdictionId),
    staleTime: 1000 * 60 * 10,
  })
  if (isLoading) {
    return (
      <p className="mb-8 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600" aria-live="polite">
        Loading who governs this place…
      </p>
    )
  }
  if (isError || !data) {
    return (
      <p className="mb-8 rounded-lg border border-gray-200 bg-white p-4 text-sm text-gray-600">
        Governing bodies are unavailable right now.
      </p>
    )
  }
  return (
    <>
      <WhoGoverns data={data} />
      <OfficialsHeard data={data} />
    </>
  )
}
